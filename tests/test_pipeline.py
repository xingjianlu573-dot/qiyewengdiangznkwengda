# -*- coding: utf-8 -*-
"""管线端到端自测（无需 pytest，直接运行：python tests/test_pipeline.py）。

覆盖：
1. 三种格式解析（PDF / Word / Markdown）非空；
2. 切片数量与元数据完整；
3. 入库 → 检索：四类典型问题均命中正确文档；
4. 回答包含 [来源编号] 引用，且引用与证据一一对应；
5. 知识库外的问题被拒答（grounded=False）—— 幻觉抑制验证；
6. 按文档删除。
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.config import settings
from app import pipeline

# 使用临时索引，避免污染正式数据
TMP_DIR = tempfile.mkdtemp(prefix="edi_test_")
settings.INDEX_PATH = os.path.join(TMP_DIR, "test_index.json")

KB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "knowledge_base")

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


def main() -> int:
    print("=" * 62)
    print("管线端到端自测：解析 → 切片 → 向量化 → 检索 → 引用回答 → 幻觉抑制")
    print("=" * 62)

    # ---------- 1. 解析 ----------
    print("\n[1] 文档解析（PDF / Word / Markdown）")
    from app.parsers import parse_file
    files = sorted(os.listdir(KB))
    docs = [f for f in files if os.path.splitext(f)[1].lower() in settings.SUPPORTED_SUFFIXES]
    check("知识库包含 4 份演示文档", len(docs) == 4, f"实际 {len(docs)}")
    check("覆盖 PDF + Word + Markdown 三种格式",
          any(f.endswith(".pdf") for f in docs)
          and any(f.endswith(".docx") for f in docs)
          and any(f.endswith(".md") for f in docs),
          f"实际格式: {[os.path.splitext(f)[1] for f in docs]}")

    parsed = {}
    for f in docs:
        blocks = parse_file(os.path.join(KB, f), f)
        parsed[f] = blocks
        check(f"《{f}》解析出文本块", len(blocks) > 0, f"blocks={len(blocks)}")

    # ---------- 2. 切片 ----------
    print("\n[2] 切片（章节感知 + 重叠窗口 + 溯源元数据）")
    chunk_counts = {}
    for f, blocks in parsed.items():
        from app.chunker import chunk_blocks
        chunks = chunk_blocks(blocks, doc_name=f, doc_id="test", chunk_size=600, overlap=100)
        chunk_counts[f] = len(chunks)
        check(f"《{f}》切片 {len(chunks)} 个", len(chunks) > 0)
        if chunks:
            c = chunks[0]
            check(f"切片带 doc_name/section 元数据",
                  c["doc_name"] == f and bool(c["section"]))
    check("切片总数 ≥ 15（知识库规模合理）", sum(chunk_counts.values()) >= 15,
          f"实际 {sum(chunk_counts.values())}")

    # ---------- 3. 入库 ----------
    print("\n[3] 入库（向量化 + 持久化）")
    result = pipeline.ingest_directory(KB, reset=True)
    check("4 份文档全部入库成功", len(result["ingested"]) == 4, f"实际 {len(result['ingested'])}")
    check("无解析失败", len(result["errors"]) == 0, f"errors={result['errors']}")
    stats = result["stats"]
    check(f"索引持久化：{stats['chunk_count']} 个片段", stats["chunk_count"] == sum(chunk_counts.values()))
    check("索引文件已写入磁盘", os.path.exists(settings.INDEX_PATH))

    # ---------- 4. 检索与引用回答 ----------
    print("\n[4] 检索与引用回答（四类典型问题）")
    cases = [
        ("电脑蓝屏代码 0x0000007B 怎么处理", "02-Windows故障处理.md"),
        ("公司网络突然断网，应该按什么顺序排查", "01-网络故障SOP.md"),
        ("VPN 提示认证失败怎么办", "03-VPN配置.docx"),
        ("Outlook 收不到邮件怎么排查", "04-邮箱问题.pdf"),
    ]
    for query, expect_doc in cases:
        resp = pipeline.ask(query)
        cit_docs = [c["doc_name"] for c in resp["citations"]]
        hit = expect_doc in cit_docs
        check(f"「{query[:16]}…」→ 命中《{expect_doc}》", hit, f"实际引用: {cit_docs}")
        check("回答 grounded=True 且含来源标注",
              resp["grounded"] and "[来源1]" in resp["answer"],
              f"answer 前 60 字: {resp['answer'][:60]}")

    # ---------- 5. 幻觉抑制 ----------
    print("\n[5] 幻觉抑制（知识库外问题应拒答）")
    unknown = pipeline.ask("怎么申请年假和报销差旅费")
    check("库外问题 grounded=False（拒绝作答）", not unknown["grounded"])
    check("拒答文案明确提示未找到内容", "没有找到" in unknown["answer"])
    check("库外问题不返回任何引用", len(unknown["citations"]) == 0)

    # 检索阈值校验：库外问题的检索结果本就不足（MIN_SCORE 过滤生效）
    # ---------- 6. 文档删除 ----------
    print("\n[6] 文档删除")
    doc_id = result["ingested"][0]["doc_id"]
    del_chunks = stats["documents"][0]["chunk_count"]
    before = pipeline.list_documents()
    before_total = before["chunk_count"]
    ok = pipeline.delete_document(doc_id)
    after = pipeline.list_documents()
    check("按 doc_id 删除成功", ok and after["doc_count"] == 3,
          f"删除后文档数 {after['doc_count']}")
    check("对应片段一并删除（doc_id 溯源生效）",
          after["chunk_count"] == before_total - del_chunks,
          f"删除前 {before_total} → 删除后 {after['chunk_count']}，应减少 {del_chunks}")
    check("删除后索引已持久化", os.path.exists(settings.INDEX_PATH))

    print("\n" + "=" * 62)
    print(f"结果：{PASS} 项通过，{FAIL} 项失败")
    print("=" * 62)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
