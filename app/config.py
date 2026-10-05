# -*- coding: utf-8 -*-
"""
全局配置：全部通过环境变量 / .env 注入，密钥不进代码。
"""
import os

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


class Settings:
    # ---------- 数据目录 ----------
    DATA_DIR: str = os.getenv("DATA_DIR", "data")
    KB_DIR: str = os.getenv("KB_DIR", os.path.join(DATA_DIR, "knowledge_base"))
    INDEX_PATH: str = os.getenv("INDEX_PATH", os.path.join(DATA_DIR, "vector_index.json"))

    # ---------- 解析 / 切片 ----------
    CHUNK_SIZE: int = _get_int("CHUNK_SIZE", 600)          # 每片最大字符数
    CHUNK_OVERLAP: int = _get_int("CHUNK_OVERLAP", 100)    # 片间重叠，保持上下文连贯

    # ---------- 向量化 ----------
    # provider: local（内置离线哈希向量，无需任何密钥）/ api（OpenAI 兼容 Embedding 接口）
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "local")
    EMBEDDING_BASE_URL: str = os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1")
    EMBEDDING_API_KEY: str = os.getenv("EMBEDDING_API_KEY", "")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    LOCAL_EMBED_DIM: int = _get_int("LOCAL_EMBED_DIM", 512)  # 离线向量的固定维度

    # ---------- 检索 ----------
    TOP_K: int = _get_int("TOP_K", 4)                       # 返回给 LLM 的片段数
    MIN_SCORE: float = _get_float("MIN_SCORE", 0.24)        # 相似度阈值：低于该值的片段不进答案（防幻觉核心）
    HYBRID_WEIGHT_VECTOR: float = _get_float("HYBRID_WEIGHT_VECTOR", 0.6)   # 语义分权重
    HYBRID_WEIGHT_LEXICAL: float = _get_float("HYBRID_WEIGHT_LEXICAL", 0.4)  # 词法分权重

    # ---------- LLM ----------
    # provider: offline（内置引用模板作答，无需密钥，用于演示）/ api（OpenAI 兼容 Chat 接口）
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "offline")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    LLM_TEMPERATURE: float = _get_float("LLM_TEMPERATURE", 0.2)
    LLM_TIMEOUT: int = _get_int("LLM_TIMEOUT", 60)

    # ---------- 服务 ----------
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = _get_int("PORT", 8000)
    MAX_UPLOAD_MB: int = _get_int("MAX_UPLOAD_MB", 30)

    # 支持的上传格式
    SUPPORTED_SUFFIXES: tuple = (".pdf", ".docx", ".doc", ".md", ".markdown", ".txt")

    @property
    def using_real_llm(self) -> bool:
        return self.LLM_PROVIDER == "api" and bool(self.LLM_API_KEY)

    @property
    def using_real_embedding(self) -> bool:
        return self.EMBEDDING_PROVIDER == "api" and bool(self.EMBEDDING_API_KEY)


settings = Settings()
