# -*- coding: utf-8 -*-
"""LLM 层：回答生成 + 引用约束 + 幻觉抑制。

双模式：
- offline（默认，免密钥）：内置“引用模板生成器”，把检索到的证据片段组织成
  带 [来源编号] 的回答。适合演示 / 离线内网；回答质量=证据质量，天然可溯源。
- api（推荐企业正式环境）：OpenAI 兼容 Chat 接口。通过强约束 System Prompt
  强制“仅依据文档片段作答 + 标注来源编号 + 不确定就明说”。

两种模式输出统一 Answer 结构，前端渲染方式一致。
"""
import re
from typing import List, Dict, Optional
from abc import ABC, abstractmethod

import requests

from .config import settings

# 约束提示词（防幻觉核心，两种模式共用）
GROUNDING_SYSTEM_PROMPT = """你是企业内部的「文档智能问答助手」。你的唯一职责是依据下面提供的【文档片段】回答员工的问题。

【必须遵守的规则】
1. 只能使用【文档片段】中的信息作答；不得编造内容，不得使用片段之外的背景知识。
2. 每一个关键结论、操作步骤或数据后，必须用 [来源编号] 标注出处，编号与【文档片段】的序号一一对应，例如 [1][2]。
3. 如果【文档片段】不足以回答用户问题，必须直接回答：“知识库中没有找到相关内容”，并建议用户更换关键词或上传相关文档。绝对不要猜测或编造。
4. 回答使用简体中文，面向企业员工，条理清晰、步骤明确。"""


class Answer:
    """统一回答结构。"""

    def __init__(self, answer: str, citations: List[Dict], grounded: bool, mode: str):
        self.answer = answer
        self.citations = citations      # 与回答中 [n] 编号一一对应
        self.grounded = grounded        # 是否基于知识库作答
        self.mode = mode                # offline / api

    def to_dict(self) -> Dict:
        return {
            "answer": self.answer,
            "citations": self.citations,
            "grounded": self.grounded,
            "mode": self.mode,
        }


# ---------------------------------------------------------------- 基类
class LlmClient(ABC):
    @abstractmethod
    def answer(self, query: str, evidence: List[Dict]) -> Answer:
        raise NotImplementedError


# ---------------------------------------------------------------- 离线引用模板
class OfflineAnswerer(LlmClient):
    """免密钥演示模式：从证据片段提炼关键句 + 引用标注。"""

    def answer(self, query: str, evidence: List[Dict]) -> Answer:
        if not evidence:
            return Answer(
                answer=f"知识库中没有找到与「{query}」相关的内容。\n\n"
                       f"建议：更换关键词重试，或先上传相关文档再提问。"
                       f"（本回答未引用任何文档，以避免凭空编造）",
                citations=[],
                grounded=False,
                mode="offline",
            )

        lines = [f"根据知识库中的 {len(evidence)} 份相关文档，回答如下："]
        for idx, ev in enumerate(evidence, start=1):
            snippet = _pick_sentences(ev["text"], query, max_len=180)
            loc = f"{ev['doc_name']}（{ev['section']}）" if ev["section"] and ev["section"] != ev["doc_name"] \
                else ev["doc_name"]
            # 编号用纯数字 [n]，与引用卡片编号一致（API 模式同为 [n]）
            lines.append(f"[{idx}] {loc}：{snippet}")
        answer = "\n\n".join(lines)
        return Answer(answer=answer, citations=evidence, grounded=True, mode="offline")


# ---------------------------------------------------------------- API LLM
class ApiLlmClient(LlmClient):
    def __init__(self, base_url: str, api_key: str, model: str,
                 temperature: float = 0.2, timeout: int = 60, mode: str = "api"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.mode = mode or "api"   # 标识实际厂商：qwen/zhipu/deepseek/moonshot/siliconflow/openai

    def answer(self, query: str, evidence: List[Dict]) -> Answer:
        if not evidence:
            return Answer(
                answer=f"知识库中没有找到与「{query}」相关的内容。\n\n"
                       f"建议：更换关键词重试，或先上传相关文档再提问。",
                citations=[],
                grounded=False,
                mode=self.mode,
            )

        docs_block = self._build_context(evidence)
        user_msg = f"【文档片段】\n{docs_block}\n\n【用户问题】\n{query}"

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": GROUNDING_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "temperature": self.temperature,
            "stream": False,
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"LLM API 调用失败：{exc}") from exc

        # 解析保护：厂商返回非 OpenAI 兼容结构时，给出明确错误而非 500
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"LLM API 返回格式异常（期望 OpenAI 兼容响应）：{exc}") from exc

        # 引用一致性校验：回答中出现的 [n] 必须对应真实证据；无任何引用时补标
        used_indices = _extract_citation_indices(content)
        if used_indices and max(used_indices) > len(evidence):
            raise RuntimeError("LLM 引用了超出证据范围的来源编号，已拦截（防幻觉校验）")
        if evidence and not used_indices:
            content = content + f"\n\n（依据来源：[1] {evidence[0]['doc_name']}）"

        return Answer(answer=content, citations=evidence, grounded=True, mode=self.mode)

    @staticmethod
    def _build_context(evidence: List[Dict]) -> str:
        parts = []
        for idx, ev in enumerate(evidence, start=1):
            loc = f"{ev['doc_name']}｜{ev['section']}" if ev["section"] else ev["doc_name"]
            if ev.get("page"):
                loc += f"｜第 {ev['page']} 页"
            parts.append(f"[{idx}] 出处：{loc}\n{ev['text']}")
        return "\n\n".join(parts)


# ---------------------------------------------------------------- 工具
def _extract_citation_indices(text: str) -> List[int]:
    """提取回答中形如 [1] [2] 的来源编号。"""
    return [int(m) for m in re.findall(r"\[(\d+)\]", text)]


def _pick_sentences(text: str, query: str, max_len: int = 180) -> str:
    """从证据文本中挑出与查询最相关的 1~2 句（离线模板用）。"""
    sentences = re.split(r"(?<=[。！？!?])", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return text[:max_len]

    query_terms = [t for t in re.findall(r"[\u4e00-\u9fff]{1,2}|[a-z0-9]+", query.lower()) if t]
    scored = []
    for s in sentences:
        score = sum(1 for t in set(query_terms) if t in s.lower())
        scored.append((score, len(s), s))
    scored.sort(key=lambda x: (-x[0], x[1]))

    picked = []
    total = 0
    for _, _, s in scored:
        if total + len(s) > max_len and picked:
            break
        picked.append(s)
        total += len(s)
        if len(picked) >= 2:
            break
    if not picked:
        picked = [sentences[0][:max_len]]
    return "".join(picked)


# ---------------------------------------------------------------- 工厂
def get_llm_client() -> LlmClient:
    """按 MODEL_PROVIDER 解析实际厂商并实例化客户端（免密钥时回退离线模式）。"""
    if settings.using_real_llm:
        return ApiLlmClient(
            settings.llm_base_url,
            settings.LLM_API_KEY,
            settings.llm_model,
            temperature=settings.LLM_TEMPERATURE,
            timeout=settings.LLM_TIMEOUT,
            mode=settings.provider,
        )
    return OfflineAnswerer()
