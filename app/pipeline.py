# -*- coding: utf-8 -*-
"""管线编排层：文档入库与问答的统一入口。

入库：解析 → 切片 → 向量化 → 写入向量库（原子持久化）
问答：检索（混合分 + 阈值）→ 证据 → LLM 作答（引用约束）→ 统一 Answer
"""
import os
import tempfile
from typing import Dict, List

from .config import settings
from .parsers import parse_file
from .chunker import chunk_blocks
from .embeddings import get_embedding_provider
from .vector_store import VectorStore
from .retriever import hybrid_search
from .reranker import get_reranker
from .llm import get_llm_client, Answer


def _store() -> VectorStore:
    return VectorStore(settings.INDEX_PATH)


# ---------------------------------------------------------------- 入库
def ingest_file(file_path: str, doc_name: str = None) -> Dict:
    """解析单个文件并写入向量库，返回入库结果。"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在：{file_path}")
    doc_name = doc_name or os.path.basename(file_path)

    store = _store()

    # 1. 解析
    blocks = parse_file(file_path, doc_name)

    # 2. 切片
    chunks = chunk_blocks(
        blocks, doc_name=doc_name, doc_id="pending",
        chunk_size=settings.CHUNK_SIZE, overlap=settings.CHUNK_OVERLAP,
    )

    # 3. 向量化（批量）
    provider = get_embedding_provider()
    embeddings = provider.embed_texts([c["text"] for c in chunks])

    # 4. 入库
    doc_id = store.add_document(doc_name, chunks[0]["format"], chunks, embeddings)
    return {
        "doc_id": doc_id,
        "doc_name": doc_name,
        "chunks": len(chunks),
        "embedding_provider": provider.__class__.__name__,
    }


def ingest_directory(directory: str, reset: bool = False) -> Dict:
    """批量入库目录下所有支持的文档。"""
    store = _store()
    if reset:
        # 彻底清空（兼容历史损坏索引），保证重建后无残留片段
        store.clear()

    results, errors = [], []
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        ext = os.path.splitext(name)[1].lower()
        if not os.path.isfile(path) or ext not in settings.SUPPORTED_SUFFIXES:
            continue
        try:
            results.append(ingest_file(path, name))
        except Exception as exc:  # noqa: BLE001 单文档失败不阻塞整批
            errors.append({"file": name, "error": str(exc)})

    # 重新读取磁盘索引获取最新统计（避免使用入库前的旧对象）
    return {"ingested": results, "errors": errors, "stats": _store().stats()}


def delete_document(doc_id: str) -> bool:
    return _store().delete_document(doc_id)


def list_documents() -> Dict:
    return _store().stats()


# ---------------------------------------------------------------- 问答
def ask(query: str) -> Dict:
    """完整问答链路：检索 → 过滤 → LLM → 引用。"""
    store = _store()
    if not store.chunks:
        return Answer(
            answer="知识库为空：请先上传文档（PDF / Word / Markdown）后再提问。",
            citations=[], grounded=False, mode="none",
        ).to_dict()

    # 1. 查询向量化
    provider = get_embedding_provider()
    q_embedding = provider.embed_texts([query])[0]

    # 2. 混合检索（粗排：召回更多候选）+ 阈值过滤
    candidates = hybrid_search(
        query, store.chunks, q_embedding,
        top_k=settings.RERANK_CANDIDATES,
        min_score=settings.MIN_SCORE,
        w_vector=settings.HYBRID_WEIGHT_VECTOR,
        w_lexical=settings.HYBRID_WEIGHT_LEXICAL,
    )

    # 2.5 重排序（精排）：粗排候选 → Rerank → 取 Top-K（主流 RAG 架构「检索→重排→生成」）
    reranker = get_reranker()
    if reranker and len(candidates) > settings.TOP_K:
        candidates = reranker.rerank(query, candidates)
    evidence = candidates[:settings.TOP_K]

    # 3. LLM 作答（引用约束）
    llm = get_llm_client()
    answer = llm.answer(query, evidence)
    result = answer.to_dict()
    result["retrieved_count"] = len(evidence)
    result["rerank_mode"] = settings.RERANK_MODE
    return result
