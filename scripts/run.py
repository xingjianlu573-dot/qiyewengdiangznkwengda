# -*- coding: utf-8 -*-
"""一键启动脚本：python scripts/run.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import uvicorn

from app.config import settings

if __name__ == "__main__":
    print(f"Enterprise Document Intelligence Assistant 启动中…")
    print(f"  Embedding: {settings.EMBEDDING_PROVIDER} | LLM: {settings.LLM_PROVIDER}")
    print(f"  知识库索引：{os.path.abspath(settings.INDEX_PATH)}")
    print(f"  访问地址：http://127.0.0.1:{settings.PORT}\n")
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)
