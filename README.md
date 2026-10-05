# 📚 Enterprise Document Intelligence Assistant 企业文档智能问答系统

> **面向企业员工的文档知识问答助手**：上传 PDF / Word / Markdown，自动完成「解析 → 切片 → 向量化 → 检索 → AI 回答 → 引用溯源」，并内置三重防幻觉机制。
>
> 本项目由开源项目 **n8n-rag-chatbot**（n8n + Qdrant + Gemini 原型）改造而来：从可视化工作流升级为**可独立部署、可离线演示、可接入任意大模型网关**的企业级 RAG 应用。

---

## ✨ 核心能力

| 能力 | 说明 |
| --- | --- |
| 📤 多格式上传 | PDF / Word（.docx）/ Markdown（.md / .txt），拖拽或选择文件，自动入库 |
| 🔄 完整 RAG 管线 | 文档解析 → 章节感知切片 → 向量化 → 混合检索 → LLM 回答，全链路代码实现 |
| 📌 引用溯源 | 每条回答标注 **[来源编号]**，前端展示来源卡片：文档名、章节、页码、匹配度、原文片段 |
| 🛡️ 防幻觉三重机制 | ① 相似度阈值过滤低相关片段 ② 强约束提示词「仅依据文档作答，不知道就明说」③ 库外问题直接拒答并给出建议 |
| 🧠 双模式引擎 | **离线演示模式**（免密钥，开箱即用） + **API 模式**（接入任意 OpenAI 兼容的 LLM / Embedding 网关） |
| 🗄️ 零依赖向量库 | JSON 文件持久化 + 纯 Python 余弦相似度，无需数据库服务，单文件备份/迁移/恢复 |
| 🧹 文档生命周期 | 在线查看文档列表、按文档删除并同步清理索引片段 |

## 📸 演示截图

| 首页与知识库 | 检索问答与引用 |
| --- | --- |
| ![首页](docs/screenshots/01-home.png) | ![问答引用](docs/screenshots/02-chat-answer-network.png) |

| 引用原文溯源 | 多文档回答 | 防幻觉拒答 | 文档上传入库 |
| --- | --- | --- | --- |
| ![引用溯源](docs/screenshots/03-citation-source.png) | ![邮件问答](docs/screenshots/04-chat-answer-mail.png) | ![拒答演示](docs/screenshots/05-hallucination-rejection.png) | ![上传入库](docs/screenshots/06-upload-document.png) |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Web 前端（静态单页）                         │
│        上传拖拽区 · 知识库文档管理 · 对话区 · 引用来源卡片             │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ REST API
┌───────────────────────────────▼─────────────────────────────────────┐
│                     FastAPI 后端（app/）                              │
│                                                                      │
│  ┌──────────┐  ┌───────────┐  ┌────────────┐  ┌──────────────────┐  │
│  │ 解析层    │→ │  切片层    │→ │  向量化层   │→ │   向量库（JSON）  │  │
│  │ PDF/Word │  │ 章节感知   │  │ local/api  │  │ + 溯源元数据持久化│  │
│  │ Markdown │  │ +重叠窗口  │  │  Embedding │  │                  │  │
│  └──────────┘  └───────────┘  └────────────┘  └──────────────────┘  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │  检索层：混合检索（语义余弦 60% + 词法 BM25-lite 40%）            │   │
│  │          ↓ 相似度阈值过滤（MIN_SCORE=0.24）↓ Top-K=4            │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                          ↓ 证据片段 + 溯源元数据                      │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │  LLM 层：引用约束提示词（系统级防幻觉）+ [来源编号] 一致性校验    │   │
│  │          offline 引用模板  /  api OpenAI 兼容 Chat 接口          │   │
│  └───────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**RAG 问答链路（一次完整请求）：**

```
员工提问
   │
   ▼
Embedding(问题) ──► 混合检索：语义余弦 + 词法分
   │                     │
   │              相似度 < 0.24 → 过滤（不进入回答，防止低质引用）
   │                     │
   │              保留 Top-4 证据片段（文档名/章节/页码/匹配度）
   │                     ▼
   └──► LLM 依据证据作答，强制 [来源编号] 标注
               │
               ▼
        前端渲染：回答 + 引用来源卡片 + 原文片段
```

---

## 🚀 快速开始

### 方式一：本地运行（免密钥，离线演示）

```bash
# 1. 安装依赖（Python 3.10+）
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 2. 灌入演示知识库（IT 运维：网络故障SOP / Windows故障 / VPN配置 / 邮箱问题）
python scripts/ingest.py --dir data/knowledge_base --reset

# 3. 启动服务
python scripts/run.py
# 浏览器打开 http://127.0.0.1:8000
```

> 默认 `EMBEDDING_PROVIDER=local` + `LLM_PROVIDER=offline`，**无需任何 API Key** 即可体验完整 RAG 问答与引用溯源。

### 方式二：Docker 一键部署

```bash
docker compose up -d --build
# 访问 http://localhost:8000
```

### 接入真实大模型（推荐企业正式使用）

复制 `.env.example` 为 `.env`，配置 Embedding 与 LLM（任选一家 OpenAI 兼容网关，如 SiliconFlow / DashScope / OpenAI）：

```ini
EMBEDDING_PROVIDER=api
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_MODEL=BAAI/bge-m3

LLM_PROVIDER=api
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
```

重启后回答将由真实 LLM 生成，引用约束提示词自动生效。

---

## 🧪 演示知识库：IT 运维知识库

内置 4 份演示文档（覆盖三种格式），可直接用于演示与面试讲解：

| 文档 | 格式 | 内容 |
| --- | --- | --- |
| 01-网络故障SOP.md | Markdown | 故障分级、逐层排查流程（物理→链路→网络→传输→应用）、DNS/DHCP/IP 冲突速查、恢复验证清单 |
| 02-Windows故障处理.md | Markdown | 蓝屏代码速查表（0x7B/0x0A/0x1E/0xD1）、电脑变慢、无法开机、打印机、系统更新失败 |
| 03-VPN配置.docx | Word | 客户端安装、首次连接配置、常见错误处理（认证失败/无法连接/掉线）、MFA、安全规范 |
| 04-邮箱问题.pdf | PDF | Outlook 无法收发、密码锁定、发送延迟、附件限制、容量满、垃圾邮件、手机端配置 |

**可直接演示的问题：**

- 「电脑蓝屏代码 0x0000007B 怎么处理」→ 命中 Windows 手册蓝屏速查表
- 「公司网络突然断网，应该按什么顺序排查」→ 命中网络故障 SOP 逐层排查流程
- 「VPN 提示认证失败怎么办」→ 命中 VPN 配置手册
- 「Outlook 收不到邮件怎么排查」→ 命中邮箱问题 PDF
- 「怎么申请年假和报销差旅费」→ **拒答**（知识库外问题，验证防幻觉）

---

## 🏢 RAG 企业落地能力清单

本项目面向企业知识管理场景设计，重点解决 RAG 落地的三个核心问题：

### 1. 可信 —— 回答可溯源
- 每个答案片段带 `[来源编号]`，前端同步展示**来源文档、章节、页码、匹配度、原文片段**；
- 员工可一键核对「AI 说的」与「文档原话」，从机制上建立信任。

### 2. 可控 —— 降低幻觉
| 机制 | 实现 |
| --- | --- |
| 检索质量门禁 | 混合检索 + `MIN_SCORE` 阈值：低相关片段根本不进回答，从源头切断幻觉 |
| 强约束提示词 | 系统级 Prompt：只准用文档片段作答、不得编造、不确定必须明说（见 `app/llm.py`） |
| 引用一致性校验 | LLM 输出的 `[n]` 编号必须落在真实证据范围内，越界即拦截（API 模式） |
| 知识库外拒答 | 检索不到足够相关内容时明确告知，不生成「看似合理」的编造答案 |
| 免责声明 | 前端固定提示「回答仅供参考，重要操作以原始文档为准」 |

### 3. 可部署 —— 适配企业 IT 环境
- **零外部服务依赖**：向量库即 JSON 文件，不要求部署 Qdrant/Milvus 等数据库，单机即可跑通；
- **双模式引擎**：无外网/无密钥的内网环境用离线模式，接入网关后平滑升级语义检索；
- **格式治理**：PDF（含页内章节识别）、Word（标题样式 + 表格）、Markdown（标题层级）统一解析；
- **数据安全**：密钥仅存 `.env`（已 gitignore），支持自定义 `DATA_DIR`，索引文件可整体备份迁移。

---

## 🔌 API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/documents` | 上传文档（multipart，白名单校验 .pdf/.docx/.doc/.md/.markdown/.txt，限流 30MB，防路径穿越） |
| GET | `/api/documents` | 知识库文档列表（含片段数与格式统计） |
| DELETE | `/api/documents/{doc_id}` | 删除文档并同步清理索引片段 |
| POST | `/api/query` | 文档问答：`{"query": "..."}` → 回答 + 引用来源 |
| GET | `/api/health` | 健康检查（引擎模式 + 知识库统计） |

示例：

```bash
curl -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "电脑蓝屏代码 0x0000007B 怎么处理"}'
```

---

## 📂 项目结构

```
enterprise-document-intelligence/
├── app/                      # 后端分层实现
│   ├── main.py               # FastAPI 入口：上传/管理/问答 API + 静态前端
│   ├── config.py             # .env 配置（密钥不进代码）
│   ├── parsers/              # 解析层：PDF(页内章节) / Word(标题+表格) / Markdown(标题)
│   ├── chunker.py            # 切片层：章节感知 + 固定长度 + 重叠窗口 + 溯源元数据
│   ├── embeddings.py         # 向量化层：离线哈希向量 / OpenAI 兼容 Embedding
│   ├── vector_store.py       # 向量库：JSON 持久化 + 原子写入 + 按文档删除
│   ├── retriever.py          # 检索层：混合检索（语义 60% + 词法 40%）+ 阈值过滤
│   ├── llm.py                # LLM 层：引用约束提示词 + 离线引用模板 + 一致性校验
│   └── pipeline.py           # 管线编排：入库与问答的统一入口
├── static/                   # 前端（原生 HTML/CSS/JS，无框架依赖）
├── data/
│   ├── knowledge_base/       # 演示知识库（IT 运维，PDF/Word/Markdown）
│   └── vector_index.json     # 向量索引（入库后生成）
├── scripts/
│   ├── run.py                # 一键启动
│   ├── ingest.py             # 离线灌库 CLI（--dir / --file / --reset）
│   ├── build_demo_kb.py      # 生成演示 Word/PDF 文档
│   └── api_smoke_test.py     # API 冒烟验证
├── tests/test_pipeline.py    # 管线端到端自测（33 项断言）
├── docs/screenshots/         # 演示截图
├── Dockerfile / docker-compose.yml
├── .env.example              # 配置模板
└── README.md / DEPLOYMENT.md
```

---

## ✅ 测试与验证

```bash
python tests/test_pipeline.py      # 管线端到端自测（33 项断言，全部通过）
python scripts/api_smoke_test.py   # 在线 API 冒烟验证（需服务已启动）
```

覆盖范围：三种格式解析、切片与元数据、入库持久化、四类典型问题检索命中、引用编号与证据一致、**库外问题拒答（幻觉抑制）**、文档删除与索引清理、非法格式拦截。

---

## 🔭 路线图

- [ ] Rerank 重排序（bge-reranker）提升检索精度
- [ ] 会话记忆（多轮上下文）
- [ ] 流式回答（SSE）
- [ ] 用户权限与文档级 ACL（企业多部门隔离）
- [ ] 索引增量更新与版本化
- [ ] 评测集（Recall / Precision / Faithfulness）

---

## 💻 技术栈

- **后端**：Python · FastAPI · Uvicorn
- **解析**：PyMuPDF（PDF）· python-docx（Word）
- **检索**：纯 Python 混合检索（语义余弦 + BM25-lite）
- **LLM / Embedding**：OpenAI 兼容接口（SiliconFlow / DashScope / OpenAI 等）+ 内置离线模式
- **前端**：原生 HTML / CSS / JavaScript（单页应用，零构建）
- **部署**：本地一键启动 / Docker Compose

## 📄 License

MIT —— 基于 [n8n-rag-chatbot](https://github.com/syedshahidashiqali/n8n-rag-chatbot)（MIT）改造，自由使用、修改、分发。
