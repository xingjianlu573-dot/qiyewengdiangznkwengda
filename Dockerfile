# ============================================================
# Enterprise Document Intelligence Assistant
# 国内部署优化版：
#   1. pip 使用清华镜像源（PyPI 官方源国内拉取慢）
#   2. 基础镜像国内拉取加速：配置 Docker 镜像加速器即可（见 README_CN.md）
#   3. 依赖分层缓存：requirements.txt 单独 COPY，命中缓存时秒级重建
# ============================================================
# 国内可用的 python:3.12-slim 替代方案（任选其一，需将 FROM 行替换）：
#   FROM docker.m.daocloud.io/library/python:3.12-slim
#   FROM dockerpull.org/library/python:3.12-slim
#   FROM registry.cn-hangzhou.aliyuncs.com/library/python:3.12-slim
FROM python:3.12-slim

WORKDIR /app

# 系统依赖（PyMuPDF 需要的基础库）
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 依赖分层缓存：requirements.txt 不变时，此层可复用，构建提速
COPY requirements.txt .
# 国内 pip 镜像源（清华 TUNA；可按需替换为阿里云 mirrors.aliyun.com/pypi/simple）
RUN pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt

COPY . .

# 容器内数据目录（与宿主机挂载 data/ 卷）
ENV DATA_DIR=/app/data
ENV KB_DIR=/app/data/knowledge_base
ENV INDEX_PATH=/app/data/vector_index.json

EXPOSE 8000

# 启动前自动灌入演示知识库（幂等：文档已存在则跳过）
CMD ["sh", "-c", "python scripts/ingest.py --dir data/knowledge_base && python scripts/run.py"]
