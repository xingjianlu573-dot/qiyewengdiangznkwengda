# -*- coding: utf-8 -*-
"""切片层：章节感知 + 固定长度 + 重叠窗口。

策略（兼顾召回质量与工程简洁性）：
1. 以文档解析出的章节为单位，章节内部按 CHUNK_SIZE 字符切块；
2. 相邻块间保留 CHUNK_OVERLAP 字符的重叠，避免切断语义完整的句子；
3. 每个块携带完整溯源元数据：文档名 / 章节 / 页码 / 序号，供回答引用。
"""
from typing import List, Dict


def chunk_blocks(blocks: List[Dict], doc_name: str, doc_id: str,
                 chunk_size: int = 600, overlap: int = 100) -> List[Dict]:
    chunks: List[Dict] = []
    global_seq = 0

    for block in blocks:
        heading = block.get("heading") or doc_name
        text = block.get("text") or ""
        page = block.get("page")

        # 按块内顺序切分（优先在句号/换行处断开，保证语义完整）
        segments = _split_by_size(text, chunk_size, overlap)
        for i, seg in enumerate(segments, start=1):
            if not seg.strip():
                continue
            chunks.append({
                "id": f"{doc_id}#{global_seq}",
                "doc_id": doc_id,
                "doc_name": doc_name,
                "format": _fmt_of(doc_name),
                "section": heading,
                "page": page,
                "seq": global_seq,
                "text": seg.strip(),
            })
            global_seq += 1

    if not chunks:
        raise ValueError(f"文档 {doc_name} 切片后为空")
    return chunks


def _split_by_size(text: str, size: int, overlap: int) -> List[str]:
    """按目标大小切分，重叠 overlap 字符，优先在标点处断开。"""
    if len(text) <= size:
        return [text] if text.strip() else []

    segments: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            # 往前找一个合适的断点（句号/问号/感叹号/换行 > 逗号/分号 > 默认）
            cut = _find_break(text, start, end)
            if cut <= start:
                cut = end
            end = cut
        segments.append(text[start:end].strip())
        if end >= n:
            break
        start = max(start, end - overlap)
    return [s for s in segments if s]


def _find_break(text: str, start: int, end: int) -> int:
    window = text[start:end]
    for punct in ("。", "？", "！", "\n", ". ", "? ", "! "):
        idx = window.rfind(punct)
        if idx > 0:
            return start + idx + len(punct)
    for punct in ("；", "，", ";", ","):
        idx = window.rfind(punct)
        if idx > 0:
            return start + idx + 1
    return -1


def _fmt_of(doc_name: str) -> str:
    import os
    ext = os.path.splitext(doc_name)[1].lower()
    return {"pdf": "PDF", "docx": "Word", "doc": "Word",
            "md": "Markdown", "markdown": "Markdown", "txt": "文本"}.get(ext.lstrip("."), "文档")
