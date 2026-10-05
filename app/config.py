# -*- coding: utf-8 -*-
"""
全局配置：全部通过环境变量 / .env 注入，密钥不进代码。

AI 服务采用「Provider 抽象」设计（国产模型适配核心）：
    MODEL_PROVIDER=offline|openai|qwen|zhipu|deepseek|moonshot|siliconflow

- 每个 Provider 内置默认网关地址与模型名（全部为国内可直连的 OpenAI 兼容接口）；
- 环境变量 LLM_BASE_URL / LLM_MODEL / EMBEDDING_* 可覆盖默认值（向后兼容）；
- 无需修改任何代码，仅改环境变量即可切换大模型厂商。
"""
import os
from typing import Dict

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # python-dotenv 未安装时静默跳过，直接读系统环境变量
    pass


def _get_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# ============================================================
# AI Provider 注册表（国内可直连，均支持 OpenAI 兼容协议）
# ============================================================
PROVIDER_DEFAULTS: Dict[str, Dict[str, str]] = {
    # OpenAI（海外；国内访问需代理，仅作兼容保留）
    "openai": {
        "llm_base_url": "https://api.openai.com/v1",
        "llm_model": "gpt-4o-mini",
        "embed_base_url": "https://api.openai.com/v1",
        "embed_model": "text-embedding-3-small",
    },
    # 通义千问（阿里云百炼）：国内直连，Embedding 用 text-embedding-v3
    "qwen": {
        "llm_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "llm_model": "qwen-plus",
        "embed_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "embed_model": "text-embedding-v3",
    },
    # 智谱AI（GLM）：国内直连，Embedding 用 embedding-2
    "zhipu": {
        "llm_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "llm_model": "glm-4-flash",
        "embed_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "embed_model": "embedding-2",
    },
    # DeepSeek：国内直连；暂不提供 Embedding（自动回退离线向量）
    "deepseek": {
        "llm_base_url": "https://api.deepseek.com/v1",
        "llm_model": "deepseek-chat",
        "embed_base_url": "",
        "embed_model": "",
    },
    # 月之暗面 Kimi：国内直连；暂不提供 Embedding（自动回退离线向量）
    "moonshot": {
        "llm_base_url": "https://api.moonshot.cn/v1",
        "llm_model": "moonshot-v1-8k",
        "embed_base_url": "",
        "embed_model": "",
    },
    # SiliconFlow（硅基流动）：国内直连，聚合多家开源模型 + BGE 向量
    "siliconflow": {
        "llm_base_url": "https://api.siliconflow.cn/v1",
        "llm_model": "Qwen/Qwen2.5-7B-Instruct",
        "embed_base_url": "https://api.siliconflow.cn/v1",
        "embed_model": "BAAI/bge-m3",
    },
}

# 提供 Embedding 服务的 Provider（其余自动回退本地离线向量）
EMBEDDING_CAPABLE = ("openai", "qwen", "zhipu", "siliconflow")


class Settings:
    # ---------- 数据目录 ----------
    DATA_DIR: str = os.getenv("DATA_DIR", "data")
    KB_DIR: str = os.getenv("KB_DIR", os.path.join(DATA_DIR, "knowledge_base"))
    INDEX_PATH: str = os.getenv("INDEX_PATH", os.path.join(DATA_DIR, "vector_index.json"))

    # ---------- 解析 / 切片 ----------
    CHUNK_SIZE: int = _get_int("CHUNK_SIZE", 600)          # 每片最大字符数
    CHUNK_OVERLAP: int = _get_int("CHUNK_OVERLAP", 100)    # 片间重叠，保持上下文连贯

    # ---------- AI Provider 抽象（国产模型切换入口） ----------
    # 取值：offline | openai | qwen | zhipu | deepseek | moonshot | siliconflow
    MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "offline")
    # 向后兼容：未设置 MODEL_PROVIDER 时，沿用旧的 LLM_PROVIDER 语义
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "offline")

    # ---------- 向量化 ----------
    # local: 内置离线哈希向量（免密钥）/ api: 调用 Provider 的 Embedding 接口
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "")
    EMBEDDING_BASE_URL: str = os.getenv("EMBEDDING_BASE_URL", "")
    EMBEDDING_API_KEY: str = os.getenv("EMBEDDING_API_KEY", "")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "")
    LOCAL_EMBED_DIM: int = _get_int("LOCAL_EMBED_DIM", 512)  # 离线向量的固定维度

    # ---------- 检索 ----------
    TOP_K: int = _get_int("TOP_K", 4)                       # 返回给 LLM 的片段数
    MIN_SCORE: float = _get_float("MIN_SCORE", 0.24)        # 相似度阈值：低于该值的片段不进答案（防幻觉核心）
    HYBRID_WEIGHT_VECTOR: float = _get_float("HYBRID_WEIGHT_VECTOR", 0.6)   # 语义分权重
    HYBRID_WEIGHT_LEXICAL: float = _get_float("HYBRID_WEIGHT_LEXICAL", 0.4)  # 词法分权重

    # ---------- LLM 显式覆盖（可选；未设置时使用 Provider 默认值） ----------
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "")
    LLM_TEMPERATURE: float = _get_float("LLM_TEMPERATURE", 0.2)
    LLM_TIMEOUT: int = _get_int("LLM_TIMEOUT", 60)

    # ---------- 服务 ----------
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = _get_int("PORT", 8000)
    MAX_UPLOAD_MB: int = _get_int("MAX_UPLOAD_MB", 30)

    # 支持的上传格式
    SUPPORTED_SUFFIXES: tuple = (".pdf", ".docx", ".doc", ".md", ".markdown", ".txt")

    # ========================================================
    # 解析逻辑
    # ========================================================
    @property
    def provider(self) -> str:
        """最终生效的 AI Provider：MODEL_PROVIDER 优先，其次兼容旧 LLM_PROVIDER。"""
        mp = (self.MODEL_PROVIDER or "").strip().lower()
        if mp and mp != "auto":
            return mp
        # 旧配置兼容：LLM_PROVIDER=api 视为通用 openai 兼容接口
        return "openai" if self.LLM_PROVIDER == "api" else "offline"

    @property
    def provider_defaults(self) -> Dict[str, str]:
        return PROVIDER_DEFAULTS.get(self.provider, PROVIDER_DEFAULTS["openai"])

    @property
    def llm_base_url(self) -> str:
        return self.LLM_BASE_URL or self.provider_defaults.get("llm_base_url", "")

    @property
    def llm_model(self) -> str:
        return self.LLM_MODEL or self.provider_defaults.get("llm_model", "")

    @property
    def using_real_llm(self) -> bool:
        """离线模式 or 未配置密钥 → 使用内置引用模板；否则调用真实大模型。"""
        if self.provider == "offline":
            return False
        return bool(self.LLM_API_KEY)

    # ---- Embedding 解析（跟随 Provider 或显式指定） ----
    @property
    def embed_mode(self) -> str:
        """api / local。显式 EMBEDDING_PROVIDER 优先；未显式时按 Provider 能力推断。"""
        ep = (self.EMBEDDING_PROVIDER or "").strip().lower()
        if ep in ("api", "local"):
            return ep
        # 未显式指定：当前 Provider 提供 Embedding 且有密钥 → api，否则 local
        if self.provider in EMBEDDING_CAPABLE and self.EMBEDDING_API_KEY:
            return "api"
        return "local"

    @property
    def embed_base_url(self) -> str:
        return self.EMBEDDING_BASE_URL or self.provider_defaults.get("embed_base_url", "")

    @property
    def embed_model(self) -> str:
        return self.EMBEDDING_MODEL or self.provider_defaults.get("embed_model", "")

    @property
    def using_real_embedding(self) -> bool:
        return self.embed_mode == "api" and bool(self.EMBEDDING_API_KEY) and bool(self.embed_base_url)


settings = Settings()
