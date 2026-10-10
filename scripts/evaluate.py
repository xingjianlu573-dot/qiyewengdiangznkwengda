# -*- coding: utf-8 -*-
"""检索评测脚本：命中率（Hit Rate）与库外拒答率。

用法：
    python scripts/evaluate.py                    # 用默认配置（RERANK_MODE=offline）
    python scripts/evaluate.py --rerank none      # 关闭重排（对比一阶段检索）
    python scripts/evaluate.py --rerank offline   # 离线精排
    python scripts/evaluate.py --rerank llm       # 大模型重排（需配 LLM_API_KEY）
    python scripts/evaluate.py --report docs/EVAL_REPORT.md   # 同时写报告文件

指标：
    hit@k      —— 期望文档出现在 Top-K 检索结果中的比例（每文档 + 总体）
    拒答率     —— 库外问题检索最高分 < MIN_SCORE（未被误召回）的比例
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.config import settings
from app.embeddings import get_embedding_provider
from app.retriever import hybrid_search
from app.reranker import OfflineReranker, LlmReranker, get_reranker


def main() -> int:
    parser = argparse.ArgumentParser(description="EDI 检索评测")
    parser.add_argument("--rerank", choices=["auto", "offline", "none", "llm"],
                        default="auto", help="重排模式（auto=读 RERANK_MODE 环境变量）")
    parser.add_argument("--top-k", type=int, default=None, help="Top-K（默认读 TOP_K）")
    parser.add_argument("--report", type=str, default="", help="评测报告输出路径（Markdown）")
    args = parser.parse_args()

    top_k = args.top_k or settings.TOP_K
    candidates_n = settings.RERANK_CANDIDATES
    min_score = settings.MIN_SCORE

    eval_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "eval_questions.json")
    with open(eval_path, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    # 选择重排器
    if args.rerank == "none":
        reranker = None
        rerank_label = "none（一阶段检索）"
    elif args.rerank == "llm":
        reranker = LlmReranker(settings.llm_base_url, settings.LLM_API_KEY,
                               settings.llm_model, timeout=settings.LLM_TIMEOUT)
        rerank_label = "llm（大模型重排）"
    elif args.rerank == "offline":
        reranker = OfflineReranker()
        rerank_label = "offline（离线精排）"
    else:
        reranker = get_reranker()
        rerank_label = f"auto（RERANK_MODE={settings.RERANK_MODE}）"

    provider = get_embedding_provider()
    store = _load_store()

    lines = []
    lines.append(f"# 检索评测报告（Hit Rate）")
    lines.append("")
    lines.append(f"- 评测集：{len(eval_data['queries'])} 个命中问题 + {len(eval_data['out_of_scope'])} 个库外问题")
    lines.append(f"- 参数：Top-K={top_k} | 粗排候选={candidates_n} | MIN_SCORE={min_score} | 重排={rerank_label}")
    lines.append(f"- 向量：{provider.__class__.__name__} | 知识库：{len(store.chunks)} 片段")
    lines.append("")

    # ---------- 命中率 ----------
    lines.append("## 命中率（hit@k）")
    lines.append("")
    lines.append("| 问题 | 期望文档 | 是否命中 | 最高分 | 命中位置 |")
    lines.append("| --- | --- | --- | --- | --- |")
    hits = 0
    per_doc = {}
    for q in eval_data["queries"]:
        expect = q["expect_doc"]
        evidence = _retrieve(provider, store, q["question"], reranker, top_k, candidates_n, min_score)
        hit = any(c["doc_name"] == expect for c in evidence)
        top_score = evidence[0]["score"] if evidence else 0.0
        position = next((i + 1 for i, c in enumerate(evidence) if c["doc_name"] == expect), None)
        hits += int(hit)
        per_doc.setdefault(expect, [0, 0])[0] += int(hit)
        per_doc[expect][1] += 1
        lines.append(f"| {q['question']} | {expect} | {'命中' if hit else '未命中'} | {top_score:.3f} | {position if position else '-'} |")
    lines.append("")

    overall = hits / len(eval_data["queries"]) if eval_data["queries"] else 0
    lines.append(f"**总体命中率：{overall:.0%}（{hits}/{len(eval_data['queries'])}）**")
    lines.append("")
    lines.append("### 按文档")
    for doc, (h, n) in per_doc.items():
        lines.append(f"- {doc}: {h}/{n}（{h / n:.0%}）")
    lines.append("")

    # ---------- 库外拒答 ----------
    lines.append("## 库外拒答率")
    lines.append("")
    lines.append("| 库外问题 | 检索最高分 | 是否低于阈值拒答 |")
    lines.append("| --- | --- | --- |")
    rejected = 0
    for q in eval_data["out_of_scope"]:
        evidence = _retrieve(provider, store, q, reranker, top_k, candidates_n, min_score)
        top_score = evidence[0]["score"] if evidence else 0.0
        ok = len(evidence) == 0 or top_score < min_score
        rejected += int(ok)
        lines.append(f"| {q} | {top_score:.3f} | {'是' if ok else '否'} |")
    lines.append("")
    rej_rate = rejected / len(eval_data["out_of_scope"]) if eval_data["out_of_scope"] else 0
    lines.append(f"**库外拒答率：{rej_rate:.0%}（{rejected}/{len(eval_data['out_of_scope'])}）**")
    lines.append("")

    report = "\n".join(lines)
    print(report)

    if args.report:
        rp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", args.report)
        os.makedirs(os.path.dirname(rp), exist_ok=True)
        with open(rp, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n[report] 已写入 {rp}")

    return 0


def _load_store():
    from app.vector_store import VectorStore
    return VectorStore(settings.INDEX_PATH)


def _retrieve(provider, store, query, reranker, top_k, candidates_n, min_score):
    q_emb = provider.embed_texts([query])[0]
    candidates = hybrid_search(
        query, store.chunks, q_emb,
        top_k=candidates_n, min_score=min_score,
        w_vector=settings.HYBRID_WEIGHT_VECTOR,
        w_lexical=settings.HYBRID_WEIGHT_LEXICAL,
    )
    if reranker and len(candidates) > top_k:
        candidates = reranker.rerank(query, candidates)
    return candidates[:top_k]


if __name__ == "__main__":
    sys.exit(main())
