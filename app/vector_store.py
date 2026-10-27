# -*- coding: utf-8 -*-
"""向量库：JSON 文件持久化 + 纯 Python 余弦相似度。

- 零外部依赖：不依赖向量数据库服务，单文件即可备份 / 迁移 / 恢复；
- 结构清晰：每条记录携带完整溯源元数据（文档名 / 章节 / 页码），供检索与引用；
- 支持按文档删除与重建（增量入库）。

并发与损坏防护（RAG-02 / RAG-03）：
- 写锁内先重新加载磁盘最新索引再修改保存，避免多个实例基于旧快照互相覆盖（lost update）；
- 索引损坏时先隔离备份原文件，再以空索引启动，绝不静默清空覆盖唯一副本。
"""
import json
import math
import os
import threading
import time
import uuid
from typing import List, Dict, Optional, Tuple

# 模块级写锁：串行化 add/delete/clear，防止多线程并发读写索引互相覆盖（lost update）
# 原子写入（tmp + os.replace）只保证不写坏文件，不保证并发语义；锁保证操作顺序。
# 注意：threading.Lock 只协调同一进程内的线程；多进程/多实例部署需升级为带事务语义的存储（如 SQLite）。
_WRITE_LOCK = threading.Lock()


class VectorStore:
    def __init__(self, index_path: str):
        self.index_path = index_path
        self.chunks: List[Dict] = []          # 全部切片记录
        self.documents: Dict[str, Dict] = {}  # doc_id -> 文档元信息
        self._load()

    # ---------------- 持久化 ----------------
    def _read_index(self) -> Dict:
        """读取磁盘索引原始数据；文件不存在时返回空结构。"""
        if not os.path.exists(self.index_path):
            return {"chunks": [], "documents": {}}
        with open(self.index_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load(self) -> None:
        try:
            data = self._read_index()
            self.chunks = data.get("chunks", [])
            self.documents = data.get("documents", {})
        except (json.JSONDecodeError, OSError) as exc:
            # 索引损坏：先隔离备份原文件，再以空索引启动，禁止静默覆盖唯一副本
            self._quarantine_corrupt(exc)
            self.chunks = []
            self.documents = {}

    def _quarantine_corrupt(self, exc: Exception) -> None:
        """把损坏/不可读的索引移到带时间戳的备份文件，保留现场供人工恢复。"""
        if not os.path.exists(self.index_path):
            return
        backup = f"{self.index_path}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}"
        try:
            os.replace(self.index_path, backup)
            print(
                f"[vector_store] 索引文件损坏（{exc}），原文件已备份为 {backup}；"
                f"将按空索引启动，如需恢复请先检查备份文件。"
            )
        except OSError as backup_exc:
            print(
                f"[vector_store] 索引文件损坏（{exc}），且备份失败（{backup_exc}），"
                f"请人工检查 {self.index_path} 后决定是否重建。"
            )

    def _reload_locked(self) -> None:
        """写锁内重新加载磁盘最新索引：防止旧实例快照覆盖其他实例刚写入的数据。"""
        try:
            data = self._read_index()
        except (json.JSONDecodeError, OSError) as exc:
            self._quarantine_corrupt(exc)
            data = {"chunks": [], "documents": {}}
        self.chunks = data.get("chunks", [])
        self.documents = data.get("documents", {})

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.index_path) or ".", exist_ok=True)
        payload = {
            "version": 1,
            "chunks": self.chunks,
            "documents": self.documents,
        }
        tmp = self.index_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, self.index_path)  # 原子写入，防止写一半损坏

    # ---------------- 入库 ----------------
    def add_document(self, doc_name: str, file_format: str, chunks: List[Dict],
                     embeddings: List[List[float]]) -> str:
        doc_id = uuid.uuid4().hex[:12]
        with _WRITE_LOCK:
            self._reload_locked()  # 合并最新磁盘索引，防止旧快照覆盖并发写入
            for chunk, emb in zip(chunks, embeddings):
                record = dict(chunk)
                record["doc_id"] = doc_id  # 覆盖切片阶段的占位 doc_id，保证按文档删除生效
                record["embedding"] = emb
                record["id"] = f"{doc_id}#{record['seq']}"
                self.chunks.append(record)
            self.documents[doc_id] = {
                "id": doc_id,
                "name": doc_name,
                "format": file_format,
                "chunk_count": len(chunks),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            self._save()
        return doc_id

    def delete_document(self, doc_id: str) -> bool:
        with _WRITE_LOCK:
            self._reload_locked()  # 合并最新磁盘索引，防止旧快照覆盖并发删除
            if doc_id not in self.documents:
                return False
            del self.documents[doc_id]
            self.chunks = [c for c in self.chunks if c["doc_id"] != doc_id]
            self._save()
        return True

    def clear(self) -> None:
        """彻底清空索引（重建场景使用）。"""
        with _WRITE_LOCK:
            self._reload_locked()  # 以最新磁盘索引为准清空，避免误覆盖其他实例的写入
            self.chunks = []
            self.documents = {}
            self._save()

    # ---------------- 检索 ----------------
    def search(self, query_embedding: List[float], top_k: int) -> List[Tuple[Dict, float]]:
        """返回 (chunk, 余弦相似度) 列表，按相似度降序。"""
        scored: List[Tuple[Dict, float]] = []
        for chunk in self.chunks:
            score = _cosine(query_embedding, chunk["embedding"])
            scored.append((chunk, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # ---------------- 统计 ----------------
    def stats(self) -> Dict:
        by_format: Dict[str, int] = {}
        for doc in self.documents.values():
            by_format[doc["format"]] = by_format.get(doc["format"], 0) + 1
        return {
            "doc_count": len(self.documents),
            "chunk_count": len(self.chunks),
            "documents": list(self.documents.values()),
            "by_format": by_format,
        }


def _cosine(a: List[float], b: List[float]) -> float:
    """纯 Python 余弦相似度（向量已归一化时等价于点积）。"""
    if not a or not b:
        return 0.0
    dot = 0.0
    for x, y in zip(a, b):
        dot += x * y
    # 防御：归一化向量点积理论在 [-1,1]，浮点误差收敛到 [0,1]
    return max(0.0, min(1.0, dot))
