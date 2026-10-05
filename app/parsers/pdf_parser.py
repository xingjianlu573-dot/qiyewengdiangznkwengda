# -*- coding: utf-8 -*-
"""PDF 解析：使用 PyMuPDF（fitz）按页抽取文本，并在页内识别章节标题。"""
import re
from typing import List, Dict

import fitz  # PyMuPDF

# 识别常见章节标题：一、二、三…（中文序号）或 1. 2. 3. 或「第 X 章/节」
_HEADING_RE = re.compile(
    r"^\s*(?:[一二三四五六七八九十百]+、|[0-9]+[\.、]|第[一二三四五六七八九十0-9]+[章节部分])\s*.+"
)


def parse_pdf(file_path: str, doc_name: str) -> List[Dict]:
    """解析 PDF，返回按页 + 页内章节组织的文本块列表。"""
    blocks: List[Dict] = []
    try:
        doc = fitz.open(file_path)
    except Exception as exc:
        raise ValueError(f"无法打开 PDF 文件（可能已损坏或加密）：{exc}")

    try:
        for page_index, page in enumerate(doc, start=1):
            text = page.get_text("text")
            text = _clean(text)
            if not text:
                continue
            blocks.extend(_split_by_heading(text, page_index))
    finally:
        doc.close()

    if not blocks:
        raise ValueError("PDF 中未提取到任何文本（可能是扫描件/纯图片，暂不支持 OCR）")
    return blocks


def _split_by_heading(text: str, page: int) -> List[Dict]:
    """在页内按章节标题切分；无标题时整页作为一块。"""
    lines = text.splitlines()
    sections: List[Dict] = []
    current_heading = f"第 {page} 页"
    current_lines: List[str] = []
    order = 0

    def flush():
        nonlocal current_lines
        body = "\n".join(ln for ln in current_lines if ln.strip())
        if body:
            sections.append({
                "heading": current_heading,
                "text": body,
                "page": page,
                "order": order,
            })
        current_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped and _HEADING_RE.match(stripped) and len(stripped) <= 40:
            flush()
            current_heading = stripped
            order += 1
        else:
            current_lines.append(line)

    flush()
    return sections


def _clean(text: str) -> str:
    """清洗文本：合并空白行、压缩多余空白、去掉孤立页码行。"""
    lines = [ln.strip() for ln in text.splitlines()]
    # 去掉纯数字页码行
    lines = [ln for ln in lines if not (ln.isdigit() and len(ln) <= 4)]
    cleaned = "\n".join(ln for ln in lines if ln)
    return cleaned
