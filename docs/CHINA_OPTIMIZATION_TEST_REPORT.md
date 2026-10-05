# 中国大陆访问优化 —— 测试报告

> 项目：Enterprise Document Intelligence Assistant
> 测试日期：2026-10-05　|　测试范围：国内网络适配 / Docker / 核心功能 / AI 接口
> 说明：本机当前位于境外网络（华沙），**中国大陆网络无法在本机真实复现**；凡涉及"国内网络"的验证以「资源本地化核查 + 国内镜像配置验证 + 可复现步骤」替代实测，结果如实标注验证方式，不冒充实测。

---

## 一、国内网络环境访问（适配性核查）

### 1.1 前端资源本地化核查 ✅

| 检查项 | 方法 | 结果 |
| --- | --- | --- |
| static/ 外部 URL | 正则扫描全部静态文件（index.html / app.js / styles.css） | **0 处外部引用**，全部本地同源 |
| CDN / npm 依赖 | 项目依赖清单核对 | 无 npm、无构建链、无 CDN |
| 图片资源 | 截图存于仓库 docs/screenshots，随仓库分发 | 本地化，无外部图床 |
| 第三方 JS | 静态文件内容核查 | 无 |

> 结论：应用前端零外部依赖，部署于国内服务器后访问不受境外资源影响。

### 1.2 后端 / 数据本地化核查 ✅

| 检查项 | 方法 | 结果 |
| --- | --- | --- |
| 后端 API | 代码核查：全部为本地 FastAPI 路由 | 同源服务，无外部调用 |
| 向量库 | 依赖清单：无 qdrant/milvus/redis 等外部服务 | JSON 文件本地持久化 |
| 默认 AI 网关 | config.py PROVIDER_DEFAULTS | 默认 SiliconFlow（国内直连）；国产厂商全部国内网关 |

### 1.3 国内镜像配置验证 ✅（可复现，未在本机实测拉取）

| 配置项 | 位置 | 内容 |
| --- | --- | --- |
| pip 清华源 | Dockerfile | `-i https://pypi.tuna.tsinghua.edu.cn/simple` |
| Docker 镜像加速 | README_CN.md 2.1 | daemon.json 加速器配置 + 国内基础镜像备选（daocloud / dockerpull.org / 阿里云 registry） |
| 国内下载通道 | README_CN.md 2.3 | Gitee（码云）镜像仓库同步步骤 |

> 验证方式：配置语法与文档步骤已静态核对；实际拉取速度依赖部署环境网络，需在目标服务器验证。

---

## 二、Docker 启动

| 检查项 | 状态 | 说明 |
| --- | --- | --- |
| 本机 Docker 实测 | ⚠️ 未执行 | 本机未安装 Docker，无法实测 `docker compose up` |
| Dockerfile 静态验证 | ✅ | 分层缓存（requirements 独立 COPY）、清华 pip 源、启动命令幂等 |
| docker-compose.yml 静态验证 | ✅ | MODEL_PROVIDER 环境变量注入、data 卷挂载、端口映射正确 |
| 可复现步骤 | ✅ | README_CN.md 方案 A/C 提供完整命令；在具备 Docker 的国内服务器执行 `docker compose up -d --build` 即可复现 |

---

## 三、核心功能（自动化测试全量通过）✅

| 测试套件 | 断言数 | 结果 | 覆盖 |
| --- | --- | --- | --- |
| `tests/test_pipeline.py` | 33 | **33/33 通过** | 三种格式解析、切片元数据、入库持久化、四类典型问题检索命中、引用一致性、库外拒答、按文档删除、索引清理、非法格式拦截 |
| `tests/test_providers.py` | 50 | **50/50 通过** | 六家厂商注册表、MODEL_PROVIDER 切换、网关/模型默认值解析、Embedding 能力推断、显式覆盖优先、旧配置兼容、越界引用拦截、无引用补标、免密钥回退 |
| `scripts/api_smoke_test.py` | 18 项 | **全部通过** | 健康检查、知识库 4 文档/33 片段、四类问题命中正确文档、库外拒答、上传/删除/415 拦截/索引恢复 |

**检索命中基线（优化后复测）**：

| 问题 | 命中文档 | 结果 |
| --- | --- | --- |
| 电脑蓝屏代码 0x0000007B | 02-Windows故障处理.md | ✓ |
| 公司网络突然断网排查顺序 | 01-网络故障SOP.md | ✓ |
| VPN 提示认证失败 | 03-VPN配置.docx | ✓ |
| Outlook 收不到邮件 | 04-邮箱问题.pdf | ✓ |
| 怎么申请年假和报销差旅费 | —— | 正确拒答（grounded=False） |

---

## 四、AI 接口调用（Provider 抽象层）✅

> 说明：本机无真实厂商 API Key，接口调用以 **mock 验证请求构造** 完成；验证内容与真实调用一致（URL / model / Authorization / payload 结构）。

| 厂商 | 网关验证 | 模型验证 | 引用校验 | Embedding |
| --- | --- | --- | --- | --- |
| qwen（通义千问） | dashscope.aliyuncs.com ✓ | qwen-plus ✓ | 越界拦截 ✓ | text-embedding-v3 ✓ |
| zhipu（智谱AI） | open.bigmodel.cn ✓ | glm-4-flash ✓ | ✓ | embedding-2 ✓ |
| deepseek | api.deepseek.com ✓ | deepseek-chat ✓ | ✓ | 自动回退本地向量 ✓ |
| moonshot（月之暗面） | api.moonshot.cn ✓ | moonshot-v1-8k ✓ | ✓ | 自动回退本地向量 ✓ |
| siliconflow（硅基流动） | api.siliconflow.cn ✓ | Qwen/Qwen2.5-7B-Instruct ✓ | ✓ | BAAI/bge-m3 ✓ |
| openai | api.openai.com ✓ | gpt-4o-mini ✓ | ✓ | text-embedding-3-small ✓ |

**真实调用步骤（可复现）**：在 `.env` 设置 `MODEL_PROVIDER=qwen` + `LLM_API_KEY=sk-xxx`（对应厂商密钥），重启服务后访问 `http://<host>:8000/api/health` 确认 `llm_engine=api`，提问即可看到真实模型带引用的回答。

---

## 五、结论

| 维度 | 结论 |
| --- | --- |
| 国内网络适配 | 前端/数据完全本地化，配置项齐全（pip 镜像、Docker 加速、Gitee 通道），无架构级风险 |
| Docker | 配置已就绪，本机无 Docker 未实测（如实标注），部署服务器可按文档复现 |
| 核心功能 | 83 项断言 + 18 项冒烟全部通过，功能无回归 |
| AI 接口 | 六家厂商请求构造验证通过，真实调用需密钥，步骤已文档化 |

**残留缺口**：① 国内网络/Docker 实测需在目标环境执行；② 真实厂商 API 调用需用户密钥；③ Gitee 镜像同步需用户账号操作（步骤已在 README_CN 提供）。
