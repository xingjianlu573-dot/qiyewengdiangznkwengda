# 🇨🇳 Enterprise Document Intelligence Assistant — 中国大陆部署指南（README_CN）

> 面向**中国大陆用户**的部署与使用指南：无需特殊网络环境，即可下载、部署、使用本系统。
> 英文总览见 [README.md](README.md)。

---

## 一、为什么这个项目适合国内部署

| 特性 | 说明 |
| --- | --- |
| 前端零外部依赖 | 无 CDN、无 npm、无第三方 JS，所有静态资源本地托管，国内访问无拦截 |
| 离线可用 | 免密钥演示模式开箱即用（内置引用模板 + 本地向量），内网/无网环境也可跑 |
| 国产大模型一键切换 | `MODEL_PROVIDER=qwen/zhipu/deepseek/moonshot/siliconflow`，全部国内直连 |
| 零外部数据依赖 | 无国外数据库/对象存储/向量库，数据全部本地 JSON 文件 |
| 单文件部署 | Docker Compose 一条命令启动 |

---

## 二、国内网络环境准备（一次性）

### 2.1 Docker 镜像加速（拉取基础镜像提速）

Linux 服务器上编辑 `/etc/docker/daemon.json`：

```json
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://dockerproxy.com",
    "https://docker.mirrors.ustc.edu.cn"
  ]
}
```

然后重启 Docker：

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

> 提示：若加速器仍不稳定，可将 `Dockerfile` 首行替换为国内可直接拉取的镜像：
> `FROM docker.m.daocloud.io/library/python:3.12-slim`

### 2.2 pip 依赖加速

本项目 `Dockerfile` 已内置清华 PyPI 镜像（`pypi.tuna.tsinghua.edu.cn/simple`），本地直接运行时可手动指定：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2.3 下载项目（GitHub 访问慢的替代方案）

- **方案一（推荐）**：将本仓库同步到 **Gitee（码云）**，国内克隆速度可达数 MB/s。在 Gitee 新建仓库后，于 Gitee 仓库页选择「导入已有仓库」，填入本仓库 GitHub 地址即可自动镜像。
- **方案二**：直接下载本仓库的 Release 压缩包（若已发布）。

---

## 三、部署方案

### 方案 A：国内云服务器部署（推荐，阿里云 / 腾讯云轻量服务器）

以腾讯云轻量应用服务器（2C2G 起）为例：

```bash
# 1. 安装 Docker（国内源）
curl -fsSL https://get.docker.com | sh -s -- --mirror Aliyun

# 2. 克隆项目（建议走 Gitee 镜像）
git clone https://gitee.com/你的用户名/本仓库.git
cd 本仓库

# 3. 配置 Docker 镜像加速（见上文 2.1）

# 4. 构建并启动
docker compose up -d --build

# 5. 访问
# 浏览器打开 http://服务器公网IP:8000
```

安全建议：在云厂商安全组放行 `8000` 端口，或将服务置于 Nginx 反向代理 + HTTPS 之后。

### 方案 B：国内云平台部署（宝塔面板 / 1Panel）

1. 在云服务器安装宝塔面板（国内直连）；
2. 安装 Docker 管理器插件，导入本仓库 `docker-compose.yml`；
3. 配置 Docker 镜像加速后一键构建启动；
4. 通过面板绑定域名、申请免费 HTTPS 证书，即可对外提供服务。

### 方案 C：本地 Docker 运行（个人电脑 / 内网）

```bash
git clone https://gitee.com/你的用户名/本仓库.git
cd 本仓库
docker compose up -d --build
# 打开 http://127.0.0.1:8000
```

### 方案 D：本地 Python 直接运行（无需 Docker）

```bash
# Windows / Linux / macOS
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python scripts/ingest.py --dir data/knowledge_base   # 灌入演示知识库（可选）
python scripts/run.py
# 打开 http://127.0.0.1:8000
```

---

## 四、国产大模型配置（一键切换）

系统内置 **AI Provider 抽象层**：只需设置 `MODEL_PROVIDER` 环境变量 + 对应密钥，无需修改任何代码。

| Provider | 厂商 | 默认模型 | Embedding | 网关（国内直连） |
| --- | --- | --- | --- | --- |
| `qwen` | 通义千问（阿里云百炼） | `qwen-plus` | text-embedding-v3 | dashscope.aliyuncs.com |
| `zhipu` | 智谱AI（GLM） | `glm-4-flash`（免费额度） | embedding-2 | open.bigmodel.cn |
| `deepseek` | DeepSeek | `deepseek-chat` | 自动回退本地向量 | api.deepseek.com |
| `moonshot` | 月之暗面 Kimi | `moonshot-v1-8k` | 自动回退本地向量 | api.moonshot.cn |
| `siliconflow` | 硅基流动（开源模型聚合） | `Qwen/Qwen2.5-7B-Instruct` | BAAI/bge-m3 | api.siliconflow.cn |
| `openai` | OpenAI（海外） | `gpt-4o-mini` | text-embedding-3-small | api.openai.com（需代理） |

### 配置方式

**方式一：.env 文件（推荐）**

```bash
cp .env.example .env
# 编辑 .env：
#   MODEL_PROVIDER=qwen
#   LLM_API_KEY=sk-xxxxxxxx
# （Embedding 密钥建议同厂商填写：EMBEDDING_API_KEY=sk-xxxxxxxx）
python scripts/run.py
```

**方式二：环境变量**

```bash
MODEL_PROVIDER=qwen LLM_API_KEY=sk-xxxx python scripts/run.py
```

**方式三：Docker Compose**

编辑 `docker-compose.yml` 的 environment 段，将 `MODEL_PROVIDER=offline` 改为目标厂商并填入密钥，然后：

```bash
docker compose up -d --build
```

> 说明：DeepSeek / 月之暗面暂不提供 Embedding 接口，系统会自动使用本地离线向量（检索能力仍可用，推荐配合 `MIN_SCORE=0.24` 防幻觉阈值）。

### 检索重排序 Rerank 配置（紧跟主流 RAG 架构「检索→重排→生成」）

系统内置重排序层：先由混合检索粗排召回 Top-C 候选，再经 Rerank 精排后取 Top-K 交给大模型，进一步提升「喂给 LLM 的片段质量」→ 回答更准、引用更稳。

| 配置 | 取值 | 说明 |
| --- | --- | --- |
| `RERANK_MODE` | `offline`（默认） | 免密钥精排：查询词频 + 章节标题命中 + 位置加权，零成本 |
| `RERANK_MODE` | `llm` | 大模型按相关性重排（需 `LLM_API_KEY`，质量最高） |
| `RERANK_MODE` | `none` | 关闭重排（回到一阶段检索） |
| `RERANK_CANDIDATES` | `8`（默认） | 一阶段粗排召回候选数（默认 TOP_K×2） |

```bash
# 免密钥精排（默认，无需配置）
python scripts/run.py

# 大模型重排（企业正式使用）
# .env: RERANK_MODE=llm + LLM_API_KEY=sk-xxx
```

检索质量可量化评测：`python scripts/evaluate.py` 输出命中率 Hit Rate 与库外拒答率（内置 12 个命中问题 + 3 个库外问题），可用 `--rerank none/offline/llm` 对比不同模式。

> 提示：`MIN_SCORE=0.24` 阈值是按**离线向量**口径标定的；切换到 API 语义向量（如 text-embedding-v3）后，余弦分数分布不同，建议运行 `python scripts/evaluate.py` 观察命中/拒答情况，必要时调整 `MIN_SCORE`（如 0.30~0.40），保证"低相关片段不进回答"的门禁依然有效。

---

## 五、常见问题（FAQ）

**Q1：Docker 构建时拉取基础镜像很慢/失败？**
配置 Docker 镜像加速器（见 2.1），或将 Dockerfile 首行 `FROM` 替换为国内镜像仓库地址。

**Q2：pip install 很慢？**
已内置清华源；手动安装时可加 `-i https://pypi.tuna.tsinghua.edu.cn/simple`。

**Q3：GitHub 克隆/下载太慢？**
将仓库同步到 Gitee 后从 Gitee 克隆（见 2.3），速度可达数 MB/s。

**Q4：设置了 MODEL_PROVIDER 和密钥，为什么还是离线回答？**
检查密钥是否已写入生效的 .env（若同时存在系统环境变量与 .env，.env 优先级最高）；确认 `LLM_API_KEY` 非空；重启服务后生效。

**Q5：回答中出现乱码？**
服务端与浏览器均使用 UTF-8；若在 Windows 命令行直接运行时中文乱码，执行 `chcp 65001` 或使用 Docker 部署。

**Q6：如何知道当前用的是哪个模型？**
访问 `http://服务器IP:8000/api/health`，查看 `model_provider` / `llm_model` / `embedding_model` / `rerank_mode` 字段。

**Q7：能对接其他模型厂商吗？**
可以。所有国内厂商均为 OpenAI 兼容接口，设置 `MODEL_PROVIDER=openai` 并自定义 `LLM_BASE_URL` / `LLM_MODEL` 即可接入任意兼容网关（如讯飞星火、百川、Minimax 等）。

**Q8：Rerank 是什么？默认开着吗？**
Rerank 是对检索结果的二次精排：先粗排召回更多候选，再按更细粒度信号（词频/标题命中/位置，或大模型打分）把最相关的片段提到最前面，LLM 只吃到高质量 Top-K。默认 `RERANK_MODE=offline` 免密钥开启；想关掉设 `RERANK_MODE=none`，想用大模型重排设 `RERANK_MODE=llm` 并配 `LLM_API_KEY`。

**Q9：怎么验证检索效果？**
运行 `python scripts/evaluate.py`，输出 12 题命中率（当前 92%）与 3 个库外问题拒答率（当前 100%）；也可加 `--rerank none` 与默认 offline 对比，量化重排带来的变化。

---

## 六、中国大陆访问风险审查

完整风险清单与处理方案见 [docs/CHINA_ACCESS_REVIEW.md](docs/CHINA_ACCESS_REVIEW.md)：前端/后端零外部依赖为低风险；Docker 镜像源与 GitHub 访问链路为本指南已解决的高风险项。
