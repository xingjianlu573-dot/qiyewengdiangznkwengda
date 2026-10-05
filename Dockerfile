# Enterprise Document Intelligence Assistant
FROM python:3.12-slim

WORKDIR /app

# 系统依赖（PyMuPDF 需要的基础库）
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 容器内数据目录（与宿主机挂载 data/ 卷）
ENV DATA_DIR=/app/data
ENV KB_DIR=/app/data/knowledge_base
ENV INDEX_PATH=/app/data/vector_index.json

EXPOSE 8000

# 启动前自动灌入演示知识库（幂等：文档已存在则跳过）
CMD ["sh", "-c", "python scripts/ingest.py --dir data/knowledge_base && python scripts/run.py"]
