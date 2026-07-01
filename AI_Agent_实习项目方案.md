# AI Agent 实习求职 - 两周项目方案

> 整理日期:2026-05-25
> 基于 6 份 AI Agent 实习岗 JD 关键词共性提炼:**RAG、Agent 框架(LangGraph/LangChain)、Tool Calling/MCP、多轮对话+记忆、Prompt Engineering、评测/Badcase 分析、全栈落地**

---

## 目录

- [Part 1:5 个候选项目(按性价比排序)](#part-15-个候选项目按性价比排序)
- [Part 2:两周通用排期建议](#part-2两周通用排期建议)
- [Part 3:重点推荐项目 - AI 求职助手(完整方案)](#part-3重点推荐项目---ai-求职助手完整方案)
  - [一、技术选型](#一技术选型)
  - [二、目录结构](#二目录结构)
  - [三、Day-by-Day 任务清单](#三day-by-day-任务清单14-天)
  - [四、简历写法(倒推开发)](#四简历可以这样写提前写好倒推开发)
  - [五、必踩的坑](#五必踩的坑提前预警)

---

# Part 1:5 个候选项目(按性价比排序)

## 1. 垂直场景 RAG 助手 ⭐ 覆盖最广,强烈推荐

**选一个具体领域**:论文助手 / 法律咨询 / 简历对照 JD / 个人笔记 Second Brain。

- **技术点**:文档清洗 + 分块策略对比(固定/语义/递归) + 嵌入(bge-m3) + Milvus/Qdrant + Hybrid Search(BM25+向量) + Rerank(bge-reranker)+ Citation
- **加分**:做一个 30~50 条的 eval 集,对比不同 chunking/rerank 配置的命中率,产出一篇评测博客
- **栈**:FastAPI + Next.js + LangChain
- **对应 JD**:几乎覆盖图 1、图 6 全部要求

## 2. 多工具 Agent(对应"导购/导览/接待"场景)

做一个**电商导购 Agent** 或**旅行规划 Agent**。

- **技术点**:LangGraph 状态机 + 4~6 个 Tool(搜索、商品库查询、比价、下单 mock、推荐)+ 短期/长期记忆 + 异常处理(工具失败回退)
- **加分**:写 Planner-Executor 双 Agent 结构,记录完整 Trace
- **对应 JD**:图 1 "拆解任务、多轮对话、异常处理" 和图 5 "Badcase 分析"

## 3. 自己写一个 MCP Server + Claude Code 集成

- 比如 **GitHub PR Reviewer MCP** / **本地知识库 MCP** / **数据库查询 MCP**
- **技术点**:MCP 协议、JSON Schema、Tool 描述工程
- **加分**:开源到 GitHub,写清楚 README 和使用示例
- **对应 JD**:图 6 "MCP 协议" + 图 3 "深度用过 Claude Code/Cursor"

## 4. 轻量级 Agent 评测平台 ⭐ 差异化最强

做一个 mini Langfuse/Phoenix。

- **技术点**:Trace 采集(OpenTelemetry-style)+ Badcase 标注 UI + LLM-as-Judge + 多版本 Prompt A/B
- **栈**:FastAPI + Postgres + Next.js
- **对应 JD**:图 1、图 2、图 5 都强调的 "Case 设计、Trace 分析、失败样本标注"
- **这个最少人做,简历最亮眼**

## 5. 全栈 AI 小产品(对应图 3 创业团队)

**真的找一个用户痛点上线**:小红书爆文生成器、面经整理 Agent、英语口语陪练……

- **技术点**:Next.js 全栈 + Vercel/Railway 部署 + 真实用户反馈
- **加分**:写"从 0 到 1 拿到第一个用户"的复盘文,这就是图 3 说的"非课业产出"

---

# Part 2:两周通用排期建议

选 **1+3 组合**(垂直 RAG + MCP Server)性价比最高;如果想做单一深度项目,推荐 Part 3 的方案。

| 阶段 | 时间 | 主要任务 |
|---|---|---|
| 调研 + Demo | Day 1-2 | 跑通基础链路,选定数据源 |
| 核心开发 | Day 3-8 | 主功能、Agent/RAG 链路 |
| 评测优化 | Day 9-11 | Eval 集 + Badcase 分析 + Prompt 迭代 |
| 部署文档 | Day 12-13 | 部署 + README + 博客 |
| 发布推广 | Day 14 | demo 视频,推到 GitHub/小红书 |

---

# Part 3:重点推荐项目 - AI 求职助手(完整方案)

## 项目名

**AI 求职助手 - 简历 × JD 智能匹配与改写 Agent**

## 为什么选它

- 你自己 + 身边同学就是用户,容易拿到真实反馈(对应图 3 "非课业产出")
- 覆盖 RAG + Agent + Tool Calling + 评测,几乎命中所有 JD 关键词
- 可发小红书/掘金引流,验证"卖东西"能力
- 数据集好搞:爬 BOSS/拉勾 JD + 自己的简历变体

## 核心功能(MVP)

1. 上传简历 + 粘贴目标 JD → 输出**匹配分** + **逐条 gap 分析** + **改写建议**
2. 内置 JD 知识库(按岗位/公司检索同类 JD,提取高频要求)
3. 多轮对话改写:用户说"把项目 2 改得更突出 RAG 经验" → Agent 调用工具改写
4. **评测看板**:对比改写前后,LLM-as-Judge 打分

---

## 一、技术选型

### 后端

| 组件 | 选型 | 理由 |
|---|---|---|
| 语言 | Python 3.11 | JD 几乎都要求 |
| Web 框架 | **FastAPI** + Pydantic v2 | 图 6 明确点名;异步、自动 OpenAPI |
| Agent 编排 | **LangGraph**(主)+ LangChain(辅) | 状态机比 chain 更适合多轮 + 工具;图 1/6 都点名 |
| LLM | **DeepSeek-V3**(便宜)+ Claude Haiku 4.5(判官)+ Qwen-Plus(备份) | 国内可访问,成本低 |
| Embedding | **bge-m3** | 中英双语 SOTA,免费 |
| Rerank | **bge-reranker-v2-m3** | 配套,显著提点 |
| 向量库 | **Qdrant** | 轻量 Docker 一键起,API 干净;图 6 明确点名 |
| 关系库 | PostgreSQL 16 + SQLAlchemy 2.0 | 存用户/对话/Trace |
| 缓存 | Redis 7 | 会话 + Embedding 缓存 |
| 文档处理 | pymupdf(PDF)+ python-docx + unstructured | 简历 PDF/DOCX 都得支持 |
| 任务追踪 | 自研 Trace 表(写入 PG) | 不用 Langfuse,展示你能自己造轮子 |

### 前端

| 组件 | 选型 | 理由 |
|---|---|---|
| 框架 | **Next.js 14 App Router** + TS | 图 3 明确要求 |
| UI | Tailwind + **shadcn/ui** | 最快出"看起来不像学生作品"的产品 |
| 流式 | **SSE**(EventSource) | 比 WebSocket 简单,够用 |
| 状态 | Zustand + TanStack Query | 轻量 |
| Markdown | react-markdown + KaTeX + Shiki | 渲染简历改写结果 |

### 部署

- **Docker Compose**(本地一键起 5 个服务:api/web/postgres/qdrant/redis)
- **Railway / Fly.io**(后端)+ **Vercel**(前端)
- 总成本预算:< $10

---

## 二、目录结构

```
job-agent/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── core/
│   │   │   ├── config.py           # pydantic-settings
│   │   │   ├── logging.py
│   │   │   └── trace.py            # 自研 Trace(span/event)
│   │   ├── api/
│   │   │   ├── chat.py             # SSE 流式对话
│   │   │   ├── upload.py           # 简历上传
│   │   │   ├── jd.py               # JD CRUD
│   │   │   └── eval.py             # 评测 API
│   │   ├── agents/
│   │   │   ├── graph.py            # LangGraph 主状态机
│   │   │   ├── nodes/
│   │   │   │   ├── planner.py      # 任务拆解
│   │   │   │   ├── retriever.py    # RAG 节点
│   │   │   │   ├── analyzer.py     # 简历-JD gap 分析
│   │   │   │   └── rewriter.py     # 改写
│   │   │   └── prompts/            # 所有 prompt 集中管理,带版本号
│   │   │       ├── v1_analyze.md
│   │   │       └── v2_analyze.md
│   │   ├── rag/
│   │   │   ├── chunker.py          # 语义分块 + 固定分块
│   │   │   ├── embedder.py         # bge-m3 封装
│   │   │   ├── retriever.py        # Hybrid(BM25+向量)
│   │   │   ├── reranker.py         # bge-reranker
│   │   │   └── ingest.py           # 文档入库 pipeline
│   │   ├── tools/                  # Agent 可调用的工具
│   │   │   ├── search_jd.py        # 检索同类 JD
│   │   │   ├── extract_skills.py   # 抽取简历技能
│   │   │   ├── score_match.py      # 匹配打分
│   │   │   └── rewrite_section.py  # 改写某段
│   │   ├── eval/
│   │   │   ├── runner.py           # 跑评测集
│   │   │   ├── judge.py            # LLM-as-Judge
│   │   │   └── metrics.py          # 命中率/Recall@K
│   │   ├── models/
│   │   │   ├── db.py               # SQLAlchemy
│   │   │   └── schemas.py          # Pydantic
│   │   └── services/
│   │       ├── llm.py              # 多模型路由
│   │       └── parser.py           # PDF/DOCX 解析
│   ├── tests/
│   │   ├── test_rag.py
│   │   └── test_agent.py
│   ├── alembic/                    # 迁移
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── (chat)/page.tsx         # 主聊天界面
│   │   ├── upload/page.tsx         # 简历上传
│   │   ├── eval/page.tsx           # 评测看板
│   │   └── api/                    # Next.js BFF 转发
│   ├── components/
│   │   ├── chat/                   # 消息流、流式渲染
│   │   ├── resume/                 # 简历对照视图(diff)
│   │   └── eval/                   # Badcase 卡片
│   ├── lib/
│   │   ├── api.ts
│   │   └── sse.ts
│   └── package.json
├── data/
│   ├── jds/                        # 100+ 条爬取的 JD(json)
│   ├── resumes/                    # 5~10 份脱敏简历样本
│   └── eval_set.jsonl              # 30~50 条评测样本
├── scripts/
│   ├── crawl_jds.py                # 爬 JD(boss/拉勾)
│   ├── ingest.py                   # 一键入库
│   └── eval_run.py                 # 跑评测
├── docs/
│   ├── ARCHITECTURE.md             # 架构图(mermaid)
│   ├── EVAL_REPORT.md              # 评测报告(简历亮点!)
│   └── PROMPT_VERSIONS.md          # Prompt 演化记录
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 三、Day-by-Day 任务清单(14 天)

### Week 1:打通主链路(Day 1-7)

| 天 | 上午 | 下午 | 产出物 | 验收 |
|---|---|---|---|---|
| **D1** | 项目初始化:`uv init` + `pnpm create next-app` + docker-compose 起 PG/Qdrant/Redis | 爬 100+ 条 JD(`crawl_jds.py`),写 5 份脱敏简历样本 | 仓库结构 + 数据集 | `docker compose up` 全绿;`data/jds/` 有 100 条 |
| **D2** | RAG 基础:pymupdf 解析简历 → 固定分块 → bge-m3 嵌入 → Qdrant 入库 | FastAPI `/ingest` 接口 + 简单检索 `/search` | RAG v0 | curl 检索能拿到 Top5 相关 JD |
| **D3** | 加 BM25(rank_bm25)+ Hybrid Search(RRF 融合) | 加 bge-reranker 重排 | RAG v1 | 自测 5 个 query,Top3 命中率从 60% → 85% |
| **D4** | LangGraph 状态机骨架:`planner → retriever → analyzer → rewriter` | 定义 4 个 Tool(Pydantic schema)+ Tool 调用循环 | Agent 骨架 | CLI 跑通一次完整流程 |
| **D5** | 核心 Prompt v1:简历-JD gap 分析 + JSON 结构化输出 | 改写工具(指定 section + 用户指令)+ 异常处理 | Agent v1 | 输入简历+JD,输出 gap 列表+改写后段落 |
| **D6** | Next.js 聊天界面(shadcn/ui)+ SSE 流式对接 | 简历对照 diff 视图(左原文/右改写) | 前端 v1 | 浏览器能跑完整对话 |
| **D7** | 文档上传(拖拽)+ JD 输入 + 历史会话侧栏 | **里程碑:邀请 3 个同学试用,记录 bug** | MVP 上线 demo | 3 个真实用户跑通 |

### Week 2:评测、打磨、发布(Day 8-14)

| 天 | 上午 | 下午 | 产出物 | 验收 |
|---|---|---|---|---|
| **D8** | 构建评测集:30 条 `(简历, JD, 期望gap, 期望改写要点)` | 写 Trace 系统(每次 Agent 调用写入 PG,含 token/耗时/输入输出) | eval_set.jsonl + Trace 表 | 数据库能看到每次调用的完整链路 |
| **D9** | LLM-as-Judge(Claude Haiku 评分):事实性/相关性/完整性 3 个维度 | `scripts/eval_run.py` 一键跑全量 | 评测引擎 | 跑完 30 条产出 JSON 报告 |
| **D10** | 评测看板前端:badcase 卡片 + 过滤 + 标注按钮 | Prompt v2(基于 D9 badcase 改进) | 评测看板 + Prompt v2 | 看板能展示每条 case 的 trace |
| **D11** | A/B 对比:v1 vs v2 prompt,同一评测集跑 | 调 chunking(语义分块 vs 固定)再跑一遍对比 | 对比报告 | `EVAL_REPORT.md` 有 4 组数据 + 折线图 |
| **D12** | 部署:后端 Railway,前端 Vercel,Qdrant Cloud 免费档 | 加 Embedding 缓存(Redis),压测看 P95 | 线上可访问 URL | 朋友能用公网链接打开 |
| **D13** | README(架构图 mermaid + GIF demo + 一键启动) | 录 2 分钟 demo 视频,写技术博客(掘金/小红书) | README + 博客草稿 | README star-worthy |
| **D14** | 发 GitHub + 小红书 + 掘金 + 投简历 | 收集反馈,做 1 个版本的快速迭代 | **正式上线** | 至少 10 个外部用户 |

---

## 四、简历可以这样写(提前写好倒推开发)

> **AI 求职助手(全栈 RAG Agent 项目)** | [GitHub](url) | [Demo](url) | [博客](url)
>
> - 基于 LangGraph 设计 Planner-Analyzer-Rewriter 三节点状态机,集成 4 个自定义 Tool,支持多轮对话改写;
> - 实现 Hybrid Search(BM25+bge-m3 向量)+ bge-reranker 重排的 RAG 链路,**Top3 命中率从 62% 提升至 89%**;
> - 自研轻量级 Trace 系统 + LLM-as-Judge 评测平台,对 30 条评测集做 Prompt v1/v2 A/B,事实性得分 **3.4 → 4.2**;
> - 全栈技术栈:**FastAPI + LangGraph + Qdrant + Next.js 14 + Tailwind**,Docker 一键部署到 Railway/Vercel;
> - 真实用户 50+,小红书帖子 xxx 浏览,GitHub xx Star。

---

## 五、必踩的坑预警

1. **D1 别陷在爬虫**:JD 爬不下来就手动复制 50 条,**核心是 Agent 不是爬虫**
2. **D2-3 RAG 别用 LangChain 的 Document Loader**:自己写 pymupdf,可控性强 10 倍
3. **D5 改写工具最难**:输出一定要 JSON Schema 强约束,否则前端 diff 渲染会崩
4. **D8 评测集自己写最重要**:别用 GPT 生成,失去意义。30 条手工标注 > 300 条合成
5. **D12 部署前一定要加 rate limit**:API key 被刷会哭

---

## 下一步

如果决定开干,可以让 Claude 直接生成 **D1 的项目骨架代码**(docker-compose + FastAPI + Next.js 模板 + 数据库 schema),clone 即可跑通,省半天时间。
