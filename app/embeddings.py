# -*- coding: utf-8 -*-
"""向量化层：Embedding 提供商抽象。

- local：内置离线向量（字符 n-gram 哈希 + TF 加权，无任何密钥即可运行），
        适合演示 / 内网离线部署；语义能力有限，但配合词法分可完成关键词检索。
- api：  OpenAI 兼容 Embedding 接口（SiliconFlow / DashScope / OpenAI / 任意兼容网关），
        推荐企业正式环境使用，获取真实语义向量。

统一接口：embed_texts(texts) -> List[List[float]]
"""
import hashlib
import math
import re
from typing import List
from abc import ABC, abstractmethod

import requests

from .config import settings


# ---------------------------------------------------------------- 基类
class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """把一批文本转成向量（批量调用，降低 API 次数）。"""
        raise NotImplementedError


# ---------------------------------------------------------------- 离线向量（默认）
class LocalEmbeddingProvider(EmbeddingProvider):
    """确定性字符 n-gram 哈希向量。

    设计要点：
    - 用 hashlib.md5 而非内置 hash()，保证跨进程结果一致（可持久化、可复现）；
    - 中文按单字 + 双字 shingle 切分，英文按 2~3 字符 shingle，兼顾两种语言；
    - TF 加权 + L2 归一化，与 API 向量同口径比较。
    """

    def __init__(self, dim: int = 512):
        self.dim = dim

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        for token in self._tokens(text):
            bucket = self._hash(token) % self.dim
            vec[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    @staticmethod
    def _tokens(text: str) -> List[str]:
        text = text.lower()
        tokens: List[str] = []
        # 中文字符：单字 + 相邻双字
        cjk = re.findall(r"[\u4e00-\u9fff]", text)
        tokens.extend(cjk)
        tokens.extend("".join(cjk[i:i + 2]) for i in range(len(cjk) - 1))
        # 英文 / 数字：按 2、3 字符 shingle
        words = re.findall(r"[a-z0-9]+", text)
        for w in words:
            if len(w) <= 3:
                tokens.append(w)
            else:
                tokens.extend(w[i:i + 2] for i in range(len(w) - 1))
                tokens.extend(w[i:i + 3] for i in range(len(w) - 2))
        return tokens

    @staticmethod
    def _hash(token: str) -> int:
        return int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16)


# ---------------------------------------------------------------- API 向量
class ApiEmbeddingProvider(EmbeddingProvider):
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.model, "input": texts}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"Embedding API 调用失败：{exc}") from exc
        data = resp.json()
        # 兼容两种返回结构：data[i].embedding / data[i]["embedding"]
        items = data.get("data", [])
        items.sort(key=lambda it: it.get("index", 0))
        return [it["embedding"] for it in items]


# ---------------------------------------------------------------- 工厂
def get_embedding_provider() -> EmbeddingProvider:
    if settings.using_real_embedding:
        return ApiEmbeddingProvider(
            settings.EMBEDDING_BASE_URL,
            settings.EMBEDDING_API_KEY,
            settings.EMBEDDING_MODEL,
            timeout=settings.LLM_TIMEOUT,
        )
    return LocalEmbeddingProvider(dim=settings.LOCAL_EMBED_DIM)
