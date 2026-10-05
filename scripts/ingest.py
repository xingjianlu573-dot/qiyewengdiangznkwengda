# -*- coding: utf-8 -*-
"""离线灌库 CLI：把目录下的所有文档批量解析、切片、向量化并写入索引。

用法：
    python scripts/ingest.py --dir data/knowledge_base --reset
    python scripts/ingest.py --file data/knowledge_base/01-网络故障SOP.md
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app import pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="企业文档知识库灌库工具")
    parser.add_argument("--dir", help="批量入库的目录")
    parser.add_argument("--file", help="入库单个文件")
    parser.add_argument("--reset", action="store_true", help="入库前清空现有索引")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args()

    if args.file:
        result = pipeline.ingest_file(args.file)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else
              f"入库成功：{result['doc_name']}（{result['chunks']} 个片段）")
        return

    if not args.dir:
        parser.error("请提供 --dir 或 --file")

    result = pipeline.ingest_directory(args.dir, reset=args.reset)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    for item in result["ingested"]:
        print(f"  ✓ {item['doc_name']} —— {item['chunks']} 个片段")
    for err in result["errors"]:
        print(f"  ✗ {err['file']} —— {err['error']}")
    print(f"\n知识库统计：{result['stats']['doc_count']} 份文档，{result['stats']['chunk_count']} 个片段")


if __name__ == "__main__":
    main()
