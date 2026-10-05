# -*- coding: utf-8 -*-
"""AI Provider 抽象层测试：国产模型一键切换 + 引用一致性校验。

覆盖：
- PROVIDER_DEFAULTS 注册表完整性（openai/qwen/zhipu/deepseek/moonshot/siliconflow）
- config 解析：MODEL_PROVIDER 切换、网关/模型默认值、Embedding 能力推断
- ApiLlmClient：mock 请求，校验每个厂商的 base_url / model 与引用一致性
- 工厂：免密钥回退离线模式
"""
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import config as config_mod
from app.config import settings, PROVIDER_DEFAULTS, EMBEDDING_CAPABLE
from app.llm import get_llm_client, ApiLlmClient, OfflineAnswerer
from app.embeddings import get_embedding_provider, ApiEmbeddingProvider, LocalEmbeddingProvider

RESULTS = []
PASS = 0


def check(name, cond):
    global PASS
    RESULTS.append((name, bool(cond)))
    PASS += bool(cond)


def restore_settings():
    settings.MODEL_PROVIDER = "offline"
    settings.LLM_PROVIDER = "offline"
    settings.LLM_BASE_URL = ""
    settings.LLM_API_KEY = ""
    settings.LLM_MODEL = ""
    settings.EMBEDDING_PROVIDER = ""
    settings.EMBEDDING_BASE_URL = ""
    settings.EMBEDDING_API_KEY = ""
    settings.EMBEDDING_MODEL = ""


# ---------------------------------------------------------------- 1. 注册表
check("注册表含 openai", "openai" in PROVIDER_DEFAULTS)
check("注册表含 qwen", "qwen" in PROVIDER_DEFAULTS)
check("注册表含 zhipu", "zhipu" in PROVIDER_DEFAULTS)
check("注册表含 deepseek", "deepseek" in PROVIDER_DEFAULTS)
check("注册表含 moonshot", "moonshot" in PROVIDER_DEFAULTS)
check("注册表含 siliconflow", "siliconflow" in PROVIDER_DEFAULTS)

check("通义千问网关为国内地址", PROVIDER_DEFAULTS["qwen"]["llm_base_url"].startswith("https://dashscope.aliyuncs.com"))
check("智谱网关为国内地址", PROVIDER_DEFAULTS["zhipu"]["llm_base_url"].startswith("https://open.bigmodel.cn"))
check("DeepSeek 网关为国内地址", PROVIDER_DEFAULTS["deepseek"]["llm_base_url"].startswith("https://api.deepseek.com"))
check("月之暗面网关为国内地址", PROVIDER_DEFAULTS["moonshot"]["llm_base_url"].startswith("https://api.moonshot.cn"))
check("硅基流动网关为国内地址", PROVIDER_DEFAULTS["siliconflow"]["llm_base_url"].startswith("https://api.siliconflow.cn"))
check("国内厂商均提供默认模型名", all(
    PROVIDER_DEFAULTS[p]["llm_model"] for p in ("qwen", "zhipu", "deepseek", "moonshot", "siliconflow")))

# ---------------------------------------------------------------- 2. config 解析
settings.MODEL_PROVIDER = "qwen"
check("MODEL_PROVIDER=qwen 生效", settings.provider == "qwen")
check("qwen 默认 LLM 网关正确", settings.llm_base_url == PROVIDER_DEFAULTS["qwen"]["llm_base_url"])
check("qwen 默认 LLM 模型正确", settings.llm_model == "qwen-plus")
settings.LLM_API_KEY = "sk-test"
settings.EMBEDDING_API_KEY = "sk-test-emb"
check("配置密钥后启用真实 LLM", settings.using_real_llm)
check("qwen 具备 Embedding 能力", "qwen" in EMBEDDING_CAPABLE)
check("qwen 自动推断 Embedding=api", settings.embed_mode == "api")
check("qwen 默认 Embedding 模型", settings.embed_model == "text-embedding-v3")

settings.MODEL_PROVIDER = "deepseek"
check("DeepSeek 不提供 Embedding 能力", "deepseek" not in EMBEDDING_CAPABLE)
check("DeepSeek 自动回退离线向量", settings.embed_mode == "local")
check("DeepSeek 默认模型 deepseek-chat", settings.llm_model == "deepseek-chat")

settings.MODEL_PROVIDER = "zhipu"
settings.EMBEDDING_API_KEY = "sk-test"
check("智谱自动推断 Embedding=api", settings.embed_mode == "api")
check("智谱默认 Embedding 模型 embedding-2", settings.embed_model == "embedding-2")

settings.MODEL_PROVIDER = "moonshot"
check("月之暗面自动回退离线向量", settings.embed_mode == "local")

# 显式覆盖优先
settings.MODEL_PROVIDER = "qwen"
settings.LLM_BASE_URL = "https://my-gateway.example/v1"
settings.LLM_MODEL = "my-model"
check("显式 LLM_BASE_URL 覆盖默认", settings.llm_base_url == "https://my-gateway.example/v1")
check("显式 LLM_MODEL 覆盖默认", settings.llm_model == "my-model")

# 旧配置兼容
settings.MODEL_PROVIDER = ""
settings.LLM_PROVIDER = "api"
settings.LLM_API_KEY = "sk-test"
check("旧 LLM_PROVIDER=api 兼容为 openai", settings.provider == "openai")
restore_settings()
check("默认 provider=offline", settings.provider == "offline")
check("默认不使用真实 LLM", not settings.using_real_llm)

# ---------------------------------------------------------------- 3. ApiLlmClient mock
import app.llm as llm_mod
import app.embeddings as emb_mod

FAKE_CHAT = {
    "choices": [{"message": {"content": "根据文档[1]，Windows 蓝屏请先进入安全模式。[1]"}}]
}
FAKE_EMBED = {"data": [{"index": 0, "embedding": [0.1] * 8}, {"index": 1, "embedding": [0.2] * 8}]}

captured = {}


def fake_post(url, json=None, headers=None, timeout=None):
    """统一 mock：按 URL 区分 LLM 与 Embedding 请求（两模块共享同一 requests 实例）。"""
    captured["url"] = url
    captured["model"] = json["model"]
    captured["auth"] = (headers or {}).get("Authorization", "")
    if url.endswith("/embeddings"):
        return _FakeResp(FAKE_EMBED)
    return _FakeResp(FAKE_CHAT)


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


_orig_post = llm_mod.requests.post
llm_mod.requests.post = fake_post  # 两模块共享 requests 实例，只补丁一次

evidence = [{"doc_name": "02-Windows故障处理.md", "section": "蓝屏处理", "page": 1, "text": "Windows 蓝屏请先进入安全模式。"}]

try:
    settings.MODEL_PROVIDER = "qwen"
    settings.LLM_API_KEY = "sk-qwen"
    settings.LLM_BASE_URL = ""
    settings.LLM_MODEL = ""
    client = get_llm_client()
    check("qwen 工厂返回 ApiLlmClient", isinstance(client, ApiLlmClient))
    ans = client.answer("Windows 蓝屏怎么办", evidence)
    check("qwen 请求打到正确网关", captured["url"] == f"{PROVIDER_DEFAULTS['qwen']['llm_base_url']}/chat/completions")
    check("qwen 请求使用默认模型", captured["model"] == "qwen-plus")
    check("请求携带 Bearer 密钥", captured["auth"] == "Bearer sk-qwen")
    check("回答 grounded=True", ans.grounded)
    check("回答 mode=qwen", ans.mode == "qwen")
    check("引用与证据一致", len(ans.citations) == 1)

    settings.MODEL_PROVIDER = "deepseek"
    settings.LLM_API_KEY = "sk-ds"
    client = get_llm_client()
    ans = client.answer("VPN 如何配置", evidence)
    check("deepseek 请求打到正确网关", captured["url"].startswith("https://api.deepseek.com"))
    check("deepseek 使用默认模型", captured["model"] == "deepseek-chat")

    settings.MODEL_PROVIDER = "zhipu"
    settings.LLM_API_KEY = "sk-zp"
    client = get_llm_client()
    ans = client.answer("邮箱无法登录", evidence)
    check("zhipu 请求打到正确网关", captured["url"].startswith("https://open.bigmodel.cn"))

    settings.MODEL_PROVIDER = "moonshot"
    settings.LLM_API_KEY = "sk-ms"
    client = get_llm_client()
    ans = client.answer("网络断线", evidence)
    check("moonshot 请求打到正确网关", captured["url"].startswith("https://api.moonshot.cn"))

    settings.MODEL_PROVIDER = "siliconflow"
    settings.LLM_API_KEY = "sk-sf"
    client = get_llm_client()
    ans = client.answer("打印机故障", evidence)
    check("siliconflow 请求打到正确网关", captured["url"].startswith("https://api.siliconflow.cn"))

    # 引用一致性：LLM 引用超出证据范围的编号 → 拦截
    llm_mod.requests.post = lambda url, json=None, headers=None, timeout=None: _FakeResp(
        {"choices": [{"message": {"content": "引用 [9] 的超范围内容"}}]})
    settings.MODEL_PROVIDER = "qwen"
    settings.LLM_API_KEY = "sk-qwen"
    try:
        get_llm_client().answer("越界引用测试", evidence)
        check("越界引用被拦截", False)
    except RuntimeError:
        check("越界引用被拦截", True)

    # 无引用时自动补标
    llm_mod.requests.post = lambda url, json=None, headers=None, timeout=None: _FakeResp(
        {"choices": [{"message": {"content": "回答未带引用"}}]})
    ans = get_llm_client().answer("无引用测试", evidence)
    check("无引用时自动补标来源", "[1]" in ans.answer)

    # 库外问题（无证据）→ 拒答且不调用 API
    calls_before = len(captured)
    ans = get_llm_client().answer("怎么申请年假", [])
    check("库外问题直接拒答", not ans.grounded and "没有找到" in ans.answer)

    # Embedding 工厂（恢复统一 mock：按 URL 区分 LLM/Embedding）
    llm_mod.requests.post = fake_post
    settings.MODEL_PROVIDER = "qwen"
    settings.EMBEDDING_API_KEY = "sk-qwen-emb"
    settings.EMBEDDING_PROVIDER = ""
    provider = get_embedding_provider()
    check("qwen 工厂返回 ApiEmbeddingProvider", isinstance(provider, ApiEmbeddingProvider))
    vecs = provider.embed_texts(["测试文本", "另一段"])
    check("Embedding 请求打到 qwen 网关", captured["url"].startswith("https://dashscope.aliyuncs.com"))
    check("Embedding 返回向量数量正确", len(vecs) == 2 and len(vecs[0]) == 8)

    settings.MODEL_PROVIDER = "deepseek"
    settings.EMBEDDING_API_KEY = ""
    provider = get_embedding_provider()
    check("DeepSeek 回退本地离线向量", isinstance(provider, LocalEmbeddingProvider))

    # 免密钥 → 离线
    settings.MODEL_PROVIDER = "offline"
    settings.LLM_API_KEY = ""
    check("免密钥回退 OfflineAnswerer", isinstance(get_llm_client(), OfflineAnswerer))
finally:
    llm_mod.requests.post = _orig_post
    restore_settings()

# ---------------------------------------------------------------- 汇总
print(f"\nProvider 抽象层测试：{PASS}/{len(RESULTS)} 通过\n")
for name, ok in RESULTS:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
print(f"\n总计 {PASS}/{len(RESULTS)} 通过")
sys.exit(0 if PASS == len(RESULTS) else 1)
