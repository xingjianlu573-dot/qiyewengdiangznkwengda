# -*- coding: utf-8 -*-
"""检索层：混合检索（语义向量 + 词法 BM25-lite）+ 阈值过滤。

为什么混合：
- 语义向量（API 或离线哈希）能召回“表述不同但意思相近”的内容；
- 词法分对关键词（VPN、蓝屏、0x0000007B、SOP 编号等）敏感，弥补小样本下语义向量的不足；
- 两者归一化后加权合并，得分低于 MIN_SCORE 的片段一律不进答案 → 直接降低幻觉来源。

返回证据（Evidence）：
    {"chunk_id", "doc_id", "doc_name", "format", "section", "page",
     "text", "score", "score_vector", "score_lexical"}
"""
import math
import re
from typing import List, Dict, Tuple

from .config import settings


def hybrid_search(query: str, chunks: List[Dict], query_embedding: List[float],
                  top_k: int = 4, min_score: float = 0.22,
                  w_vector: float = 0.6, w_lexical: float = 0.4) -> List[Dict]:
    """混合检索：合并语义分与词法分，过滤低分，返回带证据元数据的 Top-K。"""
    query_terms = _tokenize(query)
    scored: List[Tuple[Dict, float, float, float]] = []

    for chunk in chunks:
        cos = _cosine(query_embedding, chunk["embedding"])
        lex = _bm25_lite(query_terms, chunk["text"])
        final = w_vector * cos + w_lexical * lex
        scored.append((chunk, final, cos, lex))

    scored.sort(key=lambda x: x[1], reverse=True)

    evidence: List[Dict] = []
    for chunk, final, cos, lex in scored:
        if final < min_score:
            continue
        evidence.append({
            "chunk_id": chunk["id"],
            "doc_id": chunk["doc_id"],
            "doc_name": chunk["doc_name"],
            "format": chunk["format"],
            "section": chunk["section"],
            "page": chunk["page"],
            "text": chunk["text"][:800],  # 证据预览，限制长度
            "score": round(final, 4),
            "score_vector": round(cos, 4),
            "score_lexical": round(lex, 4),
        })
        if len(evidence) >= top_k:
            break
    return evidence


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return max(0.0, min(1.0, dot))


# ---------------------------------------------------------------- 词法分
def _tokenize(text: str) -> List[str]:
    """中英混合切词：中文单字+双字，英文单词+数字。"""
    text = text.lower()
    tokens: List[str] = []
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    tokens.extend(cjk)
    tokens.extend("".join(cjk[i:i + 2]) for i in range(len(cjk) - 1))
    words = re.findall(r"[a-z0-9]+", text)
    tokens.extend(w for w in words if len(w) <= 20)
    return tokens


def _bm25_lite(query_terms: List[str], doc_text: str) -> float:
    """轻量 BM25：只统计查询词在文档中的命中覆盖度，归一化到 [0,1]。"""
    if not query_terms:
        return 0.0
    doc_lower = doc_text.lower()
    hit = 0
    for term in set(query_terms):
        if term in doc_lower:
            hit += 1
    return hit / len(set(query_terms))
