# 🚢 部署说明 Deployment Guide

Enterprise Document Intelligence Assistant 支持三种部署形态：**本地开发**、**Docker 容器**、**企业服务器（进程守护 + Nginx）**。本文档覆盖完整步骤、配置参数与故障排查。

> 🇨🇳 **中国大陆部署**（镜像加速 / 国产大模型配置 / 常见问题）见 **[README_CN.md](README_CN.md)**。

---

## 1. 环境要求

| 项 | 要求 |
| --- | --- |
| Python | 3.10+（开发/本地部署）；或 Docker 20+（容器部署） |
| 内存 | ≥ 1GB（离线模式非常轻量） |
| 磁盘 | ≥ 500MB（含 Python 环境与演示数据） |
| 网络 | 离线模式无需外网；API 模式需能访问所配置的 LLM/Embedding 网关 |

---

## 2. 本地部署（Windows / Linux / macOS）

```bash
# 2.1 创建虚拟环境并安装依赖
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2.2 灌入知识库（首次 / 数据变更后）
python scripts/ingest.py --dir data/knowledge_base --reset

# 2.3 配置（可选）：复制 .env.example 为 .env，按需修改
cp .env.example .env

# 2.4 启动
python scripts/run.py
```

启动后访问 `http://127.0.0.1:8000`。

**常用运维命令：**

```bash
python scripts/ingest.py --dir data/knowledge_base            # 增量入库（已有文档不重复）
python scripts/ingest.py --file 某文档.pdf                    # 入库单个文件
python scripts/ingest.py --reset                              # 清空重建索引
python tests/test_pipeline.py                                # 管线自测
```

---

## 3. Docker 部署

```bash
# 3.1 构建并启动（首次会自动灌入演示知识库）
docker compose up -d --build

# 3.2 查看状态与日志
docker compose ps
docker compose logs -f edi

# 3.3 停止 / 重建
docker compose down
docker compose up -d --build
```

`docker-compose.yml` 将宿主机 `./data` 挂载到容器 `/app/data`，**知识库索引持久化在宿主机**，重建容器不丢数据。

---

## 4. 企业服务器部署（进程守护 + 反向代理）

### 4.1 以服务方式常驻运行（Linux systemd）

创建 `/etc/systemd/system/edi.service`：

```ini
[Unit]
Description=Enterprise Document Intelligence Assistant
After=network.target

[Service]
Type=simple
User=edi
WorkingDirectory=/opt/edi
ExecStart=/opt/edi/.venv/bin/python scripts/run.py
Restart=always
RestartSec=5
Environment=DATA_DIR=/opt/edi/data

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now edi
```

### 4.2 Nginx 反向代理 + HTTPS

```nginx
server {
    listen 80;
    server_name kb.company.com;
    # 生产环境建议配置 HTTPS（certbot / 企业证书）

    client_max_body_size 30m;          # 与 MAX_UPLOAD_MB 对齐

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

> 提示：如企业要求上传鉴权，可在 Nginx 层接入统一认证（如 LDAP / OAuth 网关）。

---

## 5. 配置参数说明（.env）

### 5.1 AI Provider 抽象层（核心：国产模型一键切换）

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `MODEL_PROVIDER` | `offline` | 厂商切换：`offline` / `openai` / `qwen` / `zhipu` / `deepseek` / `moonshot` / `siliconflow` |
| `LLM_API_KEY` | 空 | 对应厂商的 API 密钥（配置后即启用真实大模型） |
| `LLM_BASE_URL` / `LLM_MODEL` | 空（用厂商默认） | 可选覆盖：自定义网关地址 / 模型名 |
| `EMBEDDING_PROVIDER` | 空（自动推断） | `api` 显式启用语义向量 / `local` 强制离线向量 |
| `EMBEDDING_API_KEY` | 空 | Embedding 密钥（DeepSeek / 月之暗面无 Embedding，自动回退离线） |

> 示例：`MODEL_PROVIDER=qwen` + `LLM_API_KEY=sk-xxx` 即可启用通义千问，网关与模型名自动使用国内默认值。

### 5.2 完整参数表

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `DATA_DIR` | `data` | 数据根目录（索引、上传临时区） |
| `KB_DIR` | `data/knowledge_base` | 演示知识库目录 |
| `INDEX_PATH` | `data/vector_index.json` | 向量索引文件路径 |
| `CHUNK_SIZE` | `600` | 切片最大字符数 |
| `CHUNK_OVERLAP` | `100` | 切片重叠字符数 |
| `EMBEDDING_BASE_URL` | 厂商默认 | OpenAI 兼容 Embedding 网关 |
| `EMBEDDING_MODEL` | 厂商默认 | Embedding 模型 |
| `TOP_K` | `4` | 返回给 LLM 的证据片段数 |
| `MIN_SCORE` | `0.24` | **检索阈值**：低于该值的片段不进答案（防幻觉核心参数） |
| `HYBRID_WEIGHT_VECTOR` | `0.6` | 语义分权重（混合检索） |
| `HYBRID_WEIGHT_LEXICAL` | `0.4` | 词法分权重（混合检索） |
| `LLM_TEMPERATURE` | `0.2` | 采样温度（越低越稳定） |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | 监听地址与端口 |
| `MAX_UPLOAD_MB` | `30` | 上传文件大小上限 |

**调参建议：**

- 知识库较大 / 文档较长：适当调大 `CHUNK_SIZE`（如 800~1000），`CHUNK_OVERLAP` 保持 15%~20%；
- 幻觉敏感场景：调高 `MIN_SCORE`（如 0.28~0.32），宁少勿错；
- 回答偏发散：调低 `LLM_TEMPERATURE` 至 0.1~0.2。

---

## 6. 数据备份与迁移

向量索引为**单 JSON 文件**，备份即复制：

```bash
cp data/vector_index.json backup_$(date +%F).json
```

迁移到新服务器：拷贝整个 `data/` 目录即可，无需重建；重建索引使用：

```bash
python scripts/ingest.py --dir data/knowledge_base --reset
```

---

## 7. 故障排查 FAQ

| 现象 | 排查 |
| --- | --- |
| 启动报 `Form data requires python-multipart` | 重新执行 `pip install -r requirements.txt` |
| 端口被占用 | 修改 `.env` 中 `PORT`，或 `netstat -ano | grep 8000` 定位占用进程 |
| 上传失败「文件超过大小限制」 | 调整 `MAX_UPLOAD_MB`，并同步调整 Nginx `client_max_body_size` |
| 上传 PDF 提示「未提取到文本」 | 扫描件/纯图片 PDF 暂不支持 OCR，请提供可复制文本的 PDF |
| API 模式回答报错 | 检查 `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` 是否与网关匹配，网关是否可达 |
| 回答经常「没有找到相关内容」 | ① 降低 `MIN_SCORE` ② 上传更多相关文档 ③ 检查切片是否过粗（`CHUNK_SIZE`） |
| 回答引用了不相关文档 | 调高 `MIN_SCORE`，或使用 API Embedding 提升语义精度 |
| 删除文档后片段数不变 | 确认删除的是最新版本索引（`INDEX_PATH` 指向一致） |
