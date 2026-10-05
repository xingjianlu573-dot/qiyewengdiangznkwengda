# -*- coding: utf-8 -*-
"""Markdown / 纯文本解析：按标题（# / ## / ###）切分章节。"""
import re
from typing import List, Dict


def parse_markdown(file_path: str, doc_name: str) -> List[Dict]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        # 兼容 GBK 编码的旧文件
        with open(file_path, "r", encoding="gbk", errors="replace") as f:
            text = f.read()
    except Exception as exc:
        raise ValueError(f"无法读取 Markdown 文件：{exc}")

    lines = text.splitlines()
    blocks: List[Dict] = []
    current_heading = doc_name
    current_texts: List[str] = []
    order = 0

    heading_re = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
    fenced = False  # 代码块内不解析标题

    def flush():
        nonlocal current_texts
        body = "\n".join(t for t in current_texts if t.strip())
        if body:
            blocks.append({
                "heading": current_heading,
                "text": body,
                "page": None,
                "order": order,
            })
        current_texts = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            fenced = not fenced
            current_texts.append(line)
            continue
        if not fenced:
            m = heading_re.match(stripped)
            if m:
                flush()
                current_heading = m.group(2).strip()
                order += 1
                continue
        current_texts.append(line)

    flush()

    if not blocks:
        raise ValueError("Markdown 文件中未提取到任何文本内容")
    return blocks
