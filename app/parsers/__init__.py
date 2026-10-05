# -*- coding: utf-8 -*-
"""文档解析层：把不同格式的文档统一解析为「带章节标题的文本块」。

统一输出结构（Block）：
    {"heading": str,          # 章节标题（无标题时为文档名）
     "text": str,             # 该章节下的正文文本
     "page": int|None,        # 起始页码（PDF 有，其他格式为 None）
     "order": int}            # 文档内出现顺序
"""
import os
from typing import List, Dict

from .pdf_parser import parse_pdf
from .docx_parser import parse_docx
from .markdown_parser import parse_markdown


def parse_file(file_path: str, doc_name: str) -> List[Dict]:
    """按扩展名分发解析器。doc_name 用于无章节标题时兜底。"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return parse_pdf(file_path, doc_name)
    if ext in (".docx", ".doc"):
        return parse_docx(file_path, doc_name)
    if ext in (".md", ".markdown", ".txt"):
        return parse_markdown(file_path, doc_name)
    raise ValueError(f"不支持的文档格式：{ext}")
