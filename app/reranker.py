# -*- coding: utf-8 -*-
"""重排序层（Rerank）：对粗排候选取精排，紧跟主流 RAG 架构「检索 → 重排 → 生成」。

为什么需要 Rerank：
- 一阶段混合检索（hybrid_search）召回 Top-C 个候选，靠 0.6 语义 + 0.4 词法粗排；
- 粗排候选里可能混入"相关但顺序不对"或"部分相关"的片段；
- 重排用更细粒度的信号（查询词频覆盖、标题命中、位置加权 / LLM 相关性打分）把
  真正有用的片段提到最前面，LLM 只吃到高质量 Top-K → 回答质量与引用准确率提升。

双模式：
- offline（默认，免密钥）：细粒度词法 + 结构信号精排，适合演示/内网；
- llm（API 模式）：调用大模型按相关性重排候选，质量最高；
- none：关闭重排（回到一阶段结果）。

统一接口：rerank(query, candidates) -> List[Dict]（带 score_rerank 字段）
"""
import re
from typing import List, Dict, Optional
from abc import ABC, abstractmethod

import requests

from .config import settings


# ---------------------------------------------------------------- 基类
class Reranker(ABC):
    @abstractmethod
    def rerank(self, query: str, candidates: List[Dict]) -> List[Dict]:
        """按相关性重排候选，返回带 score_rerank 的结果（降序）。"""
        raise NotImplementedError


# ---------------------------------------------------------------- 离线精排（默认）
class OfflineReranker(Reranker):
    """免密钥精排：查询词覆盖 + 标题命中 + 位置加权。

    比一阶段 BM25-lite 更细：
    - BM25-lite 只看"查询词是否出现在文本中"（覆盖度）；
    - 离线精排统计每个查询词的出现次数（词频）、是否命中章节标题、命中位置靠前程度，
      更接近真实相关性排序。
    """

    TITLE_WEIGHT = 1.5   # 查询词命中章节标题的加权
    POSITION_TAU = 0.3   # 位置平滑系数：越靠前的命中贡献越大

    def rerank(self, query: str, candidates: List[Dict]) -> List[Dict]:
        scored: List[Dict] = []
        for c in candidates:
            s = self._score(query, c)
            if s is not None:
                scored.append({**c, "score_rerank": round(s, 4)})
        scored.sort(key=lambda x: -x["score_rerank"])
        return scored

    def _score(self, query: str, candidate: Dict) -> Optional[float]:
        text = (candidate.get("text") or "").lower()
        section = (candidate.get("section") or "").lower()
        terms = _query_terms(query)
        if not terms or not text:
            return 0.0

        total = 0.0
        for term in terms:
            hits = text.count(term)
            if hits <= 0:
                continue
            # 词频贡献（对数压缩，避免长文档刷分）
            total += min(3.0, 1.0 + hits * 0.5)
            # 标题命中加权（章节标题是强相关信号）
            if term in section:
                total += self.TITLE_WEIGHT
            # 位置加权：首次出现越靠前越相关
            first = text.find(term)
            rel = first / max(len(text), 1)
            total += max(0.0, 1.0 - rel / self.POSITION_TAU) * 0.5
        return total


# ---------------------------------------------------------------- LLM 重排（API 模式）
class LlmReranker(Reranker):
    """调用大模型按相关性重排候选（OpenAI 兼容接口）。

    prompt 要求模型只返回按相关性降序的候选编号序列（如 "3 1 4 2"），
    解析失败或请求失败时自动回退到离线精排（容错，不中断问答）。
    """

    def __init__(self, base_url: str, api_key: str, model: str,
                 timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._fallback = OfflineReranker()

    def rerank(self, query: str, candidates: List[Dict]) -> List[Dict]:
        if len(candidates) <= 1:
            return [dict(c, score_rerank=c.get("score", 0.0)) for c in candidates]

        try:
            order = self._ask_llm(query, candidates)
        except RuntimeError:
            order = None
        if not order:
            return self._fallback.rerank(query, candidates)

        # 按模型返回的编号顺序重排；编号越界/重复的忽略
        by_index = {i: c for i, c in enumerate(candidates)}
        ranked: List[Dict] = []
        seen = set()
        for idx in order:
            if idx in by_index and idx not in seen:
                seen.add(idx)
                ranked.append(dict(by_index[idx], score_rerank=len(ranked)))
        # 补上模型漏掉的候选（放在末尾，避免丢内容）
        for i, c in enumerate(candidates):
            if i not in seen:
                ranked.append(dict(c, score_rerank=len(ranked)))
        return ranked

    def _ask_llm(self, query: str, candidates: List[Dict]) -> List[int]:
        lines = []
        for i, c in enumerate(candidates):
            loc = f"{c['doc_name']}｜{c['section']}" if c.get("section") else c["doc_name"]
            snippet = (c.get("text") or "")[:220]
            lines.append(f"[{i}] {loc}\n{snippet}")
        user_msg = (
            f"下面是从企业知识库检索到的 {len(candidates)} 个候选片段。\n"
            f"用户问题：{query}\n\n"
            f"{chr(10).join(lines)}\n\n"
            "请只输出这些候选片段与问题相关度的排序：从最相关到最不相关，"
            "输出编号序列，编号之间用空格分隔，例如：2 0 3 1。不要输出任何其他文字。"
        )
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是检索重排序助手，只输出编号序列。"},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.0,
            "stream": False,
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, IndexError) as exc:
            raise RuntimeError(f"LLM Rerank 调用失败：{exc}") from exc

        nums = [int(m) for m in re.findall(r"\d+", content)]
        return nums


# ---------------------------------------------------------------- 工具
def _query_terms(query: str) -> List[str]:
    """中英混合查询词：中文单字+双字，英文单词+数字。与 retriever 一致。"""
    q = query.lower()
    terms: List[str] = []
    cjk = re.findall(r"[\u4e00-\u9fff]", q)
    terms.extend(cjk)
    terms.extend("".join(cjk[i:i + 2]) for i in range(len(cjk) - 1))
    terms.extend(w for w in re.findall(r"[a-z0-9]+", q) if len(w) <= 20)
    # 去重（词频统计在 _score 内做）
    seen = set()
    out = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


# ---------------------------------------------------------------- 工厂
def get_reranker() -> Optional[Reranker]:
    """按 RERANK_MODE 解析重排器；LLM 模式无密钥时自动回退离线精排。"""
    mode = (settings.RERANK_MODE or "").strip().lower()
    if mode == "none":
        return None
    if mode == "llm" and settings.using_real_llm:
        return LlmReranker(
            settings.llm_base_url,
            settings.LLM_API_KEY,
            settings.llm_model,
            timeout=settings.LLM_TIMEOUT,
        )
    # offline 默认；llm 无密钥 / 未知值 → 离线精排兜底
    return OfflineReranker()
