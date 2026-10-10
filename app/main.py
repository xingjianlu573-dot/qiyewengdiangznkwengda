# -*- coding: utf-8 -*-
"""FastAPI 入口：文档上传 / 管理 / 问答 API + 静态前端。

启动：
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
或：
    python scripts/run.py
"""
import os
import re
from typing import List

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import settings
from . import pipeline

app = FastAPI(
    title="Enterprise Document Intelligence Assistant",
    description="企业文档智能问答系统：上传 PDF / Word / Markdown，构建可溯源的知识问答。",
    version="1.1.0",
)

# 跨域支持：允许展示页（本地 file:// 或静态托管）直接调用 API。
# 生产环境建议收紧为固定域名（如 CORS_ALLOW_ORIGINS=https://kb.company.com）。
_cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(settings.DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class QueryBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="员工问题")


# ---------------------------------------------------------------- 健康检查
@app.get("/api/health")
def health() -> dict:
    stats = pipeline.list_documents()
    offline = not settings.using_real_llm
    return {
        "status": "ok",
        "model_provider": settings.provider,           # 实际生效的 AI 厂商
        "embedding_mode": settings.embed_mode,          # api / local
        "rerank_mode": settings.RERANK_MODE,            # offline / llm / none
        "llm_engine": "offline" if offline else "api",
        "llm_model": "offline（内置引用模板）" if offline else settings.llm_model,
        "embedding_model": "local-hash（免密钥）" if settings.embed_mode == "local" else settings.embed_model,
        "stats": stats,
    }


# ---------------------------------------------------------------- 文档管理
@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)) -> dict:
    """上传并解析入库一个文档（PDF / Word / Markdown）。"""
    filename = _safe_filename(file.filename or "unnamed")
    ext = os.path.splitext(filename)[1].lower()

    if ext not in settings.SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=f"不支持的格式：{ext}（支持 {', '.join(settings.SUPPORTED_SUFFIXES)}）",
        )
    if ext == ".doc":
        # python-docx 仅支持 .docx；旧版 .doc 给出明确转存指引，避免"Package not found"式报错
        raise HTTPException(
            status_code=400,
            detail="旧版 .doc 格式暂不支持：请在 Word 中另存为 .docx 后再上传",
        )

    # 重名检查：同名文档已存在时提示先删除，避免索引里出现两份同名文档
    existing = pipeline.list_documents().get("documents", [])
    if any(d["name"] == filename for d in existing):
        raise HTTPException(
            status_code=409,
            detail=f"知识库已存在同名文档《{filename}》：如需更新，请先删除旧文档再上传",
        )

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"文件超过大小限制（{settings.MAX_UPLOAD_MB}MB）",
        )
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")

    # 写入临时路径后走统一入库管线（保证与离线灌库同一套代码路径）
    tmp_path = os.path.join(UPLOAD_DIR, f"upload_{filename}")
    try:
        with open(tmp_path, "wb") as f:
            f.write(content)
        try:
            result = pipeline.ingest_file(tmp_path, filename)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "message": f"文档《{filename}》入库成功", **result}
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


@app.get("/api/documents")
def list_documents() -> dict:
    return pipeline.list_documents()


@app.delete("/api/documents/{doc_id}")
def remove_document(doc_id: str) -> dict:
    if not pipeline.delete_document(doc_id):
        raise HTTPException(status_code=404, detail=f"文档不存在：{doc_id}")
    return {"status": "ok", "message": f"已删除文档 {doc_id}"}


# ---------------------------------------------------------------- 问答
@app.post("/api/query")
def query_knowledge(body: QueryBody) -> dict:
    """企业文档问答：检索 → 过滤 → LLM 作答 → 引用来源。"""
    try:
        return pipeline.ask(body.query)
    except RuntimeError as exc:
        # LLM/Embedding API 失败时给出明确提示，不返回伪造答案
        return JSONResponse(
            status_code=502,
            content={
                "answer": f"知识服务暂时不可用：{exc}",
                "citations": [], "grounded": False, "mode": settings.provider,
            },
        )


# ---------------------------------------------------------------- 静态前端
def _safe_filename(filename: str) -> str:
    """防路径穿越：只保留文件名部分，去掉非法字符。"""
    filename = os.path.basename(filename).replace("\\", "/").split("/")[-1]
    filename = re.sub(r"[^\w\u4e00-\u9fff.\-()（） ]", "_", filename)
    filename = filename.strip()
    if not filename:
        filename = "unnamed"
    return filename


# 挂载前端静态资源（需在路由定义之后，避免覆盖 /api）
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
app.mount("/", StaticFiles(directory=os.path.abspath(static_dir), html=True), name="static")
