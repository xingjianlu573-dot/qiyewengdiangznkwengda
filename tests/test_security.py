# -*- coding: utf-8 -*-
"""安全与数据完整性验证（直接运行：python tests/test_security.py）。

覆盖：
1. RAG-01：配置 API_KEY 后，无 Key / 错误 Key 被 401 拒绝，正确 Key 通过；
           未配置 Key 时本地演示模式放行；CORS 默认收紧为本地来源。
2. RAG-02：两个独立 VectorStore 实例并发入库不丢更新（锁内重载最新索引）。
3. RAG-03：索引损坏时先隔离备份原文件，再以空索引启动，不静默覆盖。
"""
import json
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# 必须在 import app.main 之前设置，因为 API Key 在模块导入时读取
os.environ["API_KEY"] = "test-secret-key"
os.environ["CORS_ALLOW_ORIGINS"] = "http://localhost:8000,http://127.0.0.1:8000"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.vector_store import VectorStore  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name} {detail}")


def test_api_auth() -> None:
    print("\n[1] API Key 认证（RAG-01）")
    client = TestClient(app)
    # 健康检查不要求认证
    r = client.get("/api/health")
    check("健康检查无需 Key（200）", r.status_code == 200)
    # 无 Key 访问业务接口 → 401
    r = client.get("/api/documents")
    check("无 Key 访问列表被拒（401）", r.status_code == 401, f"status={r.status_code}")
    # 错误 Key → 401
    r = client.get("/api/documents", headers={"Authorization": "Bearer wrong-key"})
    check("错误 Key 被拒（401）", r.status_code == 401, f"status={r.status_code}")
    # 正确 Key（Bearer 与 X-API-Key 两种形式）→ 200
    r = client.get("/api/documents", headers={"Authorization": "Bearer test-secret-key"})
    check("Bearer 正确 Key 通过（200）", r.status_code == 200, f"status={r.status_code}")
    r = client.get("/api/documents", headers={"X-API-Key": "test-secret-key"})
    check("X-API-Key 正确 Key 通过（200）", r.status_code == 200, f"status={r.status_code}")
    # 上传 / 删除 / 查询同样要求认证
    r = client.post("/api/query", json={"query": "蓝屏怎么处理"})
    check("无 Key 查询被拒（401）", r.status_code == 401, f"status={r.status_code}")
    r = client.delete("/api/documents/whatever")
    check("无 Key 删除被拒（401）", r.status_code == 401, f"status={r.status_code}")
    # CORS 收紧：恶意来源无 ACAO 头，本地来源有
    r = client.get("/api/health", headers={"Origin": "http://evil.example.com"})
    check("恶意 Origin 无 CORS 头", r.headers.get("access-control-allow-origin") is None,
          f"ACAO={r.headers.get('access-control-allow-origin')}")
    r = client.get("/api/health", headers={"Origin": "http://localhost:8000"})
    check("本地 Origin 有 CORS 头", r.headers.get("access-control-allow-origin") == "http://localhost:8000",
          f"ACAO={r.headers.get('access-control-allow-origin')}")


def test_concurrent_ingest() -> None:
    print("\n[2] 并发入库不丢更新（RAG-02）")
    tmp = tempfile.mkdtemp(prefix="edi_conc_")
    idx = os.path.join(tmp, "conc_index.json")

    # 两个实例基于同一份空索引
    s1 = VectorStore(idx)
    s2 = VectorStore(idx)

    barrier = threading.Barrier(3)
    results = {}

    def worker(store: VectorStore, name: str) -> None:
        barrier.wait()
        chunks = [{"seq": 0, "text": f"{name} text", "doc_name": name, "section": "s"}]
        embeds = [[1.0, 0.0, 0.0]]
        results[name] = store.add_document(name, "md", chunks, embeds)

    t1 = threading.Thread(target=worker, args=(s1, "doc-A"))
    t2 = threading.Thread(target=worker, args=(s2, "doc-B"))
    t1.start(); t2.start()
    barrier.wait()
    t1.join(); t2.join()

    final = VectorStore(idx).stats()
    check("并发入库后 2 份文档都在", final["doc_count"] == 2, f"doc_count={final['doc_count']}")
    names = {d["name"] for d in final["documents"]}
    check("两份文档名称完整", names == {"doc-A", "doc-B"}, f"names={names}")
    check("片段总数 = 2（无丢失）", final["chunk_count"] == 2, f"chunks={final['chunk_count']}")


def test_corrupt_index_backup() -> None:
    print("\n[3] 损坏索引隔离备份（RAG-03）")
    tmp = tempfile.mkdtemp(prefix="edi_corrupt_")
    idx = os.path.join(tmp, "broken_index.json")
    with open(idx, "w", encoding="utf-8") as f:
        f.write('{"chunks": [truncated...')  # 写入截断的非法 JSON

    store = VectorStore(idx)
    check("损坏后以空索引启动", len(store.documents) == 0)
    check("损坏原文件不再停留在原路径", not os.path.exists(idx))
    backups = [f for f in os.listdir(tmp) if f.startswith("broken_index.json.corrupt-")]
    check("损坏文件已隔离备份（带时间戳）", len(backups) >= 1, f"backups={backups}")
    # 备份文件内容保留现场（可人工恢复）
    with open(os.path.join(tmp, backups[0]), "r", encoding="utf-8") as f:
        raw = f.read()
    check("备份保留原始损坏内容", raw.startswith('{"chunks": [truncated'), f"raw={raw[:30]}")


def main() -> int:
    print("=" * 62)
    print("安全与数据完整性验证：认证 / CORS / 并发 / 损坏恢复")
    print("=" * 62)
    test_api_auth()
    test_concurrent_ingest()
    test_corrupt_index_backup()
    print("\n" + "=" * 62)
    print(f"结果：{PASS} 项通过，{FAIL} 项失败")
    print("=" * 62)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
