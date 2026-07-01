# 项目进度

## 当前阶段

D12 部署闭环完成。线上 demo 已可访问。进 D13(README + demo 视频 + 博客)。

已完成：

- FastAPI 后端骨架。
- JD、简历、Trace、评测样本、评测结果的 PostgreSQL 模型。
- 基础 JD CRUD API。
- PDF/DOCX 简历上传解析。
- LangGraph 节点骨架。
- Prompt 版本文件。
- MCP 命令行工具骨架。

本轮推进：

- 将共享 Agent 状态移动到 `app/agent/state.py`，消除了 `graph.py` 与节点模块的循环导入。
- 上传简历现在会落库，`resume_token` 不再只是一个返回给前端的假 token。
- Analyzer 会根据 `resume_token` 和 `jd_id` 读取真实简历/JD 文本。
- 修复 Prompt 模板里的 JSON 大括号，避免 Python `.format()` 运行时报错。
- 将占位的 JD 搜索替换为基于数据库的 BM25 + phrase RRF 检索路径。
- 增加本地 reranker 开关，默认不加载重模型。
- `scripts/ingest.py` 默认把 `data/jds/*.json` 写入 PostgreSQL，向量入库改为显式 `--vectors`。
- 增加 `data/jds/sample_jds.json`，提供 3 条本地验证用 JD。
- 将 `sentence-transformers` 和 `FlagEmbedding` 从默认依赖拆到 `.[ml]`，避免普通后端测试拉取 PyTorch/CUDA 重依赖。
- Docker 基础设施已跑通：PostgreSQL、Qdrant、Redis 均可启动。
- 数据库链路已验证：`scripts/ingest.py` 可写入样例 JD，`/api/jds/search` 可返回相关 Top K。
- 增加可选数据库集成测试 `tests/test_db_integration.py`，通过 `RUN_DB_TESTS=1` 启用。
- Qdrant 向量入库已验证：`scripts/ingest.py --vectors` 可写入向量 points。
- `hybrid_search` 已扩展为 BM25 + phrase + Qdrant vector 的 RRF 融合，并在 Qdrant 不可用时降级。
- 增加可选向量集成测试 `tests/test_vector_integration.py`，通过 `RUN_VECTOR_TESTS=1` 启用。
- 增加 `LLM_BACKEND=mock`，无外部 API Key 时也能跑 Agent 主链路。
- 增加可选 Agent 集成测试 `tests/test_agent_integration.py`，覆盖 analyze 和 rewrite 路径。
- 增加可选 Chat SSE 集成测试 `tests/test_chat_integration.py`，覆盖 `/api/chat/stream` 的 analyze 和 rewrite 事件流。
- `/api/chat/stream` 已接入 Conversation 持久化，会创建/复用 `conversation_id` 并写入 user/assistant 消息。
- SSE 会先返回 `conversation` 事件，客户端可拿到当前 `conversation_id`。
- 增加 `GET /api/conversations` 和 `GET /api/conversations/{conversation_id}`，支持恢复历史对话。
- Agent 主链路会把最近用户历史传给 retriever/query rewrite；assistant JSON 输出不会被塞回检索 prompt。
- 增加 LLM JSON 解析辅助，兼容真实模型常见的 fenced JSON 代码块输出。
- 增加 `scripts/llm_smoke.py`，验证 planner/analyzer/rewriter/query rewrite 的真实 LLM 输出。
- 增加 `scripts/chat_smoke.py`，验证真实 LLM 下 `/api/chat/stream` 的 SSE 边界。
- 增加 `scripts/real_jd_quality_smoke.py`，从公开 job board API 抓取少量真实 JD 并跑 DeepSeek 质量烟测。
- 增加 `scripts/build_real_eval_cases.py`，将真实 JD 固化为 `data/eval/real_jd_cases.jsonl`。
- `scripts/eval_run.py` 已改为可加载/校验 eval JSONL，并支持幂等导入 PostgreSQL。
- 已生成 8 条真实 JD eval cases，并导入 `eval_cases` 表；重复导入会跳过已存在样例。
- Eval runner 已修正：Agent 评测会把 `EvalCase.resume_text` 和 `EvalCase.jd_text` 作为上下文传入，不再把 JD 当作 user message。
- 增加 `JUDGE_BACKEND=mock|openai|anthropic`，DeepSeek-as-Judge 可复用 OpenAI-compatible 配置。
- Judge 解析失败会用更强 JSON 约束重试一次，避免真实模型偶发非 JSON 输出直接记 0 分。
- 固定 8 条 eval cases 已跑通真实 DeepSeek 主链路 + DeepSeek judge。
- 增加 `app/eval/report.py`，支持按 `run_id` 导出 eval JSON/Markdown 报告。
- 已导出 `data/eval/reports/deepseek_judge_retry_smoke.json` 和 `.md`，包含模型配置、prompt 版本、均分和逐 case 分数。
- Eval report 支持按两个 `run_id` 或两个 report JSON 做差异比较，输出整体分数变化、退化 case、新增/缺失 case。
- 已生成 `data/eval/reports/diffs/deepseek_judge_smoke__vs__deepseek_judge_retry_smoke.diff.json` 和 `.md`。
- Agent 主链路现在会把统一的 core prompt version 传入 `plan/analyze/rewrite` 三个核心 prompt；eval runner 不再硬编码 v1。
- Prompt manifest 已进入 report config，包含 prompt 文件清单、逐文件 hash 和整体 fingerprint。
- `scripts/eval_run.py` 支持 `--prompt-version` 和 `--archive`；报告归档约定为 `data/eval/reports/prompt_<version>/...`，diff 归档约定为 `data/eval/reports/diffs/prompt_<baseline_version>__vs__prompt_<candidate_version>/...`。
- 已建立 `v2_plan.md`、`v2_analyze.md`、`v2_rewrite.md`。其中 `v2_analyze.md` 收紧为 `schema_version=v2_analyze`、固定 `decision`、`score_breakdown`、结构化 `gaps`、结构化 `strengths`、`risks` 和英文 gap 分类枚举。
- Mock LLM 已支持 v2 analyzer/rewrite schema，默认 `latest` prompt 解析到 v2。
- Eval report case 表已增加 `analysis_schema_version`、`decision`、`first_gap_category`，Markdown 报告可直接看 v2 gap 分类。
- D11 v1/v2 A/B 完成：v2 在 strict judge 下反超 v1（均分 4.25 vs 4.04），原退化是 judge 语言偏见。
  - v2 DeepSeek 主链路 + DeepSeek judge 跑通：`deepseek_v2_20260701`（归档 `data/eval/reports/prompt_v2/`）。
  - 收紧 `app/eval/judge.py` 的 JUDGE_PROMPT：加 1/3/5 锚点、`expected_gaps` checklist（≥60% 覆盖 → completeness ≥ 4）、语言一致性条款（JD 原文语言不扣分）、去掉 `comment` 字段。
  - 新增 `app/eval/runner.py::rejudge_run` + `eval_run.py --rejudge-from`，复用已存 `model_output` 只重跑 judge，避免重跑 agent。
  - 双向重判：`deepseek_v1_strict_judge_20260701`、`deepseek_v2_strict_judge_20260701`，归档到对应 `prompt_v1/`、`prompt_v2/`。
  - 新 judge 下 v1 vs v2 diff：`data/eval/reports/diffs/prompt_v1__vs__prompt_v2/deepseek_v1_strict_judge_20260701__vs__deepseek_v2_strict_judge_20260701.diff.md`。
  - 结果矩阵（均分）：v1 旧 judge 3.92 → 新 judge 4.04；v2 旧 judge 3.71 → 新 judge 4.25。v2 factuality +0.26、relevance +1.00、completeness -0.63。
  - 已知 v2 弱点：`completeness` 在 `expected_gaps` 较短（1-2 条）的简单 case 上偏弱（Case 6 Voice Recording、Case 4 Business Ops），原因待定位；Case 7 Founding Engineer 的 factuality 退化 1 分，单 case 调试未做。
- SiliconFlow bge-m3 embedding 已接入：`EMBEDDING_BACKEND=siliconflow`、`EMBEDDING_DIM=1024`。本地 `.env` 已切到新 Qdrant collection `job_agent_chunks_bge_m3_sf`，避免和旧 384 维 hash collection 冲突。
- 8 条 eval JD 已用 bge-m3 重新写入新 collection：`scripts/ingest_eval_jds.py --file data/eval/real_jd_cases.jsonl`，Qdrant 校验为 `points=16`、`vector_size=1024`。
- Reranker 最后一次短 query 机会已在 bge-m3 collection 上验证：`scripts/retrieval_ab.py --query-mode keywords --top-k-pool 20` 在 8 条 eval JD 上仍然负收益，baseline RRF `recall_at_3=0.3750 / recall_at_5=0.6250 / mrr=0.3397`，+ SiliconFlow rerank 降到 `0.1250 / 0.1250 / 0.1219`，报告为 `data/eval/reports/retrieval/retrieval_ab_20260701_123525.md`。结论：当前 reranker 不进入默认检索链路，保留为实验脚本。
- D12 第一批部署准备已完成：
  - 新增 `frontend/` Next.js 最小前端；因 Next 14 依赖审计存在运行时漏洞，前端已升级到 Next 16.2.9。当前支持上传简历、保存 JD、POST SSE 调用 `/api/chat/stream`、展示事件流和最终 JSON。
  - 新增 `GET /ready`，返回 PostgreSQL、Redis、Qdrant 诊断；`GET /health` 保持轻量 liveness。
  - `Dockerfile` 改为读取 `${PORT:-8000}`，适配 Railway/Fly.io 注入端口。
  - 新增 `docs/DEPLOYMENT.md`，记录 Railway/Fly.io 后端、Vercel 前端、环境变量和 smoke test 约定。
  - `.env.example` 增加生产 CORS 提示；仓库 `.gitignore` 排除 `node_modules/` 和 `.next/`。
- D12 第二批代码改动（rate limit + 历史会话侧栏）：
  - 新增 `app/core/rate_limit.py`：自研滑动窗口限流器（in-memory，无新依赖）+ `client_ip` 工具（识别 `X-Forwarded-For` / `X-Real-IP`）。`app/main.py` 注册中间件：`/api/chat` 与 `/api/upload` 走 heavy limiter（默认 30 req/min/IP），其他 `/api/*` 走 general limiter（默认 120 req/min/IP），`/health` 和 `/ready` 豁免。超限返回 429 + `Retry-After`。
  - 新增 `RATE_LIMIT_ENABLED` / `RATE_LIMIT_HEAVY_PER_MIN` / `RATE_LIMIT_GENERAL_PER_MIN` 三个 settings；`.env.example` 同步。
  - 新增 `tests/test_rate_limit.py` 覆盖 health 豁免、heavy 端点超限 429、429 响应 schema；后端测试 48 passed。
  - 前端新增左侧历史会话侧栏：`lib/api.ts` 加 `listConversations` / `getConversation`；`page.tsx` 改 4 列 grid，初始加载 + chat 完成后刷新列表，点击 conversation 拉取详情填充 messages，"New chat" 按钮重置状态。
  - 后端 + 前端联调 smoke：`/health`、`/ready`、`/api/conversations`、`/api/upload`（非法格式正确返回 400 + 中文错误），rate limit 中间件按预期豁免 `/health` / `/ready`。
- D12 线上部署完成（Railway + Qdrant Cloud + Vercel）：
  - Qdrant Cloud Free 1GB（GCP Australia Southeast 1）。
  - Railway 后端：`job-agent-production-014d.up.railway.app`；PostgreSQL（internal + public proxy）+ Redis；18 个 env vars；`/health` `/ready` 公网可达。
  - 解决 3 个部署阻塞：
    - `CORS_ORIGINS` 解析：用 `Annotated[list[str], NoDecode]` 跳过 EnvSettingsSource 的 JSON 预解析（commit `8ab8dd6`）。
    - `.dockerignore` 排除 `scripts/` 跟 `COPY scripts/` 冲突：改为只排 `scripts/__pycache__`（commit `bdc346f`）。
    - 本地无法直连 Railway public PG proxy（国内 GFW 丢包）：Dockerfile CMD 启动时跑 `scripts/ingest.py --vectors && scripts/ingest_eval_jds.py && uvicorn ...`，容器内走 `postgres.railway.internal`（commit `50500f5`）。
  - Vercel 前端：`job-agent-one-peach.vercel.app`；Root Directory = `job-agent/frontend`；Framework Preset 必须显式选 **Next.js**（默认 `Other` 会导致 404）。
  - 生产数据：PG `JD` 表 11 条（3 sample + 8 eval）；Qdrant collection `job_agent_chunks_bge_m3_sf` 写入 16 个 chunks；每次 redeploy 自动幂等重灌。
  - 端到端冒烟通过：上传 PDF/DOCX → JD → SSE 流（`conversation → planner → retriever → analyzer → complete → done`）→ 历史会话侧栏加载 → 多轮 rewrite 节点触发；样例简历对 SAMPLE_JD 给出 match_score=80。

## 已知安全问题（D12 上线后发现，未修复）

线上 demo 公网可达后，发现 3 类端点缺乏访问控制，会泄漏用户数据或被滥用：

### HIGH-1：`GET /api/conversations` + `GET /api/conversations/{id}` 全量泄漏简历分析结果

- **现象**：任何人（无认证）访问 `https://job-agent-production-014d.up.railway.app/api/conversations` 可拿到所有 conversation 列表，含完整 `messages`（user message 含简历原文，assistant message 含 gap/strengths/risks 分析）。
- **根因**：`app/api/chat.py::list_conversations` 用 `WHERE user_id == DEFAULT_USER_ID` 查询，`DEFAULT_USER_ID` 是全局常量，所有人共享。`Conversation` 表已有 `user_id` 字段，但代码偷懒没让请求带身份。
- **影响**：简历包含真实姓名、邮箱、电话、教育、工作经历；公网任何人可读。
- **当前暴露数据**：2 条 conversation（含测试时的 SAMPLE_JD 分析 + "把项目 2 改突出 RAG 经验" rewrite），需手动清理。
- **修复方案**：浏览器 session_id 隔离。前端首次访问生成 UUID 存 `localStorage['session_id']`，所有请求带 `X-Session-Id` header；后端把 `DEFAULT_USER_ID` 替换为 `request.headers["X-Session-Id"]`，缺失返回 403。无登录体验，清缓存丢历史（可接受）。
- **影响代码**：`app/api/chat.py`（list_conversations / get_conversation / chat_stream），`app/services/conversation.py`，`frontend/lib/api.ts`，`frontend/app/page.tsx`。

### HIGH-2：`POST /api/eval/run` + `POST /api/eval/cases` 可被陌生人触发，烧 LLM 配额

- **现象**：公网任何人 `POST /api/eval/run` 可触发全量评测跑分，会循环调用 DeepSeek 主链路 + DeepSeek judge（8 cases × ~5 次 LLM 调用 = 40 次 DeepSeek 请求 / 次），烧 API 配额。
- **根因**：`app/api/eval.py` 路由无鉴权，`run_eval` 直接调 `app.eval.runner.run_evaluation`。
- **影响**：DoS / 经济攻击；他人可恶意反复触发耗尽 DeepSeek 余额。
- **修复方案**：加 `EVAL_ADMIN_TOKEN` 环境变量，`POST /api/eval/*` 路由检查 `X-Admin-Token` header，缺失或不匹配返回 403。本地评测时带上 token。
- **影响代码**：`app/api/eval.py`，新增 `app/core/auth.py`（admin token 工具）。

### MEDIUM-3：`GET /api/jds` 全量返回，用户保存的 JD 共享

- **现象**：任何人 `GET /api/jds` 可拿到所有用户保存的 JD（含 `raw_text`）。
- **根因**：跟 HIGH-1 类似，无 `user_id` 隔离。但 `JD` 表当前没有 `user_id` 字段。
- **影响**：JD 主要是公开招聘信息，泄漏敏感度低于简历；但用户手动保存的 JD 仍属个人数据。
- **修复方案**：`JD` 表加 `user_id` 字段；sample/eval JD（`eval_real_jd_*`、`sample_*`）打 `is_public=True` 标记，所有用户可见；其他 JD 按 session_id 隔离。
- **影响代码**：`app/models/db.py`（加字段），`app/api/jd.py`，`scripts/ingest.py`、`scripts/ingest_eval_jds.py`（默认 `is_public=True`），需要 DB migration 或 `Base.metadata.create_all` 自动加列。

### LOW：`GET /api/eval/cases` + `GET /api/eval/results` 公开

- 评测数据本来就是项目 showcase 一部分，可保持公开；但 `/eval/run` 修复后，陌生人无法再触发新评测。

### 临时缓解

- **不要把 Vercel URL（`https://job-agent-one-peach.vercel.app`）分享给任何人**，已分享请撤回。
- 不要在简历/博客中放后端 Railway URL，避免被直接调 API。

### 修复优先级

1. **P0**：HIGH-1 session_id 隔离 + 清理已有 2 条泄漏 conversation。
2. **P0**：HIGH-2 admin token。
3. **P1**：MEDIUM-3 JD 隔离（加 `is_public` 标记 + user_id）。
4. **P2**：完整认证系统（注册/登录 + JWT，demo 项目暂不需要）。

### 修复时注意

- session_id 隔离改 API 行为契约（加 header），按 commit strategy 需在 push 前 commit 当前快照。
- `Base.metadata.create_all` 不会自动加新列到已存在的表，JD 表加 `user_id` 需要手动 migration 或 drop/recreate（生产 drop 不可接受，必须用 alembic 或手动 `ALTER TABLE`）。


## 主要缺口

- 项目虚拟环境 `.venv` 已创建；默认依赖和测试依赖用于后端开发，ML 本地模型依赖需要单独安装 `.[ml]`。
- Eval runner 已有骨架，但依赖 Agent 和外部 LLM key。
- 前端已有最小可部署 MVP，但还没有历史会话侧栏、评测看板和 diff 视图。

## 本地验证

已在 `.venv` 中通过：

- `.venv/bin/python -m pip check`
- `.venv/bin/python -m compileall -q app tests scripts mcp`
- `.venv/bin/python -m pytest -q`
- `RUN_DB_TESTS=1 .venv/bin/python -m pytest -q tests/test_db_integration.py`
- `RUN_VECTOR_TESTS=1 .venv/bin/python -m pytest -q tests/test_vector_integration.py`
- `RUN_AGENT_TESTS=1 .venv/bin/python -m pytest -q tests/test_agent_integration.py`
- `RUN_CHAT_TESTS=1 .venv/bin/python -m pytest -q tests/test_chat_integration.py`
- `.venv/bin/python scripts/llm_smoke.py --backend openai`
- `LLM_BACKEND=openai RUN_AGENT_TESTS=1 .venv/bin/python -m pytest -q tests/test_agent_integration.py`
- `.venv/bin/python scripts/chat_smoke.py --backend openai`
- `.venv/bin/python scripts/real_jd_quality_smoke.py --backend openai --limit 3`
- `.venv/bin/python scripts/build_real_eval_cases.py --limit 8`
- `.venv/bin/python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl`
- `.venv/bin/python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl --import-db`
- `LLM_BACKEND=mock .venv/bin/python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl --run-id runner_smoke_mock_cli_analyze`
- `LLM_BACKEND=openai JUDGE_BACKEND=openai JUDGE_MODEL=deepseek-chat .venv/bin/python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl --run-id deepseek_judge_retry_smoke`
- `LLM_BACKEND=openai JUDGE_BACKEND=openai JUDGE_MODEL=deepseek-chat .venv/bin/python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl --export-run-id deepseek_judge_retry_smoke`
- `.venv/bin/python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl --compare-run-ids deepseek_judge_smoke deepseek_judge_retry_smoke`
- `.venv/bin/python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl --compare-reports data/eval/reports/deepseek_judge_smoke.json data/eval/reports/deepseek_judge_retry_smoke.json`
- `.venv/bin/python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl --export-run-id deepseek_judge_retry_smoke --archive --report-dir /tmp/job-agent-report-archive-smoke`
- `.venv/bin/python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl --compare-reports data/eval/reports/deepseek_judge_smoke.json data/eval/reports/deepseek_judge_retry_smoke.json --archive --diff-dir /tmp/job-agent-diff-archive-smoke`
- `.venv/bin/python scripts/llm_smoke.py --backend mock`
- `LLM_BACKEND=mock JUDGE_BACKEND=mock .venv/bin/python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl --run-id v2_prompt_mock_smoke_20260701 --prompt-version v2 --export-report --archive --report-dir /tmp/job-agent-v2-report-smoke`
- `LLM_BACKEND=openai JUDGE_BACKEND=openai JUDGE_MODEL=deepseek-chat .venv/bin/python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl --run-id deepseek_v2_20260701 --prompt-version v2 --export-report --archive`
- `JUDGE_BACKEND=openai JUDGE_MODEL=deepseek-chat .venv/bin/python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl --rejudge-from deepseek_judge_retry_smoke --run-id deepseek_v1_strict_judge_20260701 --export-report --archive`
- `JUDGE_BACKEND=openai JUDGE_MODEL=deepseek-chat .venv/bin/python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl --rejudge-from deepseek_v2_20260701 --run-id deepseek_v2_strict_judge_20260701 --export-report --archive`
- `.venv/bin/python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl --compare-run-ids deepseek_v1_strict_judge_20260701 deepseek_v2_strict_judge_20260701 --archive`
- `.venv/bin/python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl --export-run-id v2_prompt_mock_smoke_20260701 --archive --report-dir /tmp/job-agent-v2-report-smoke-2`
- `.venv/bin/python -m pytest -q tests/test_health.py tests/test_rag.py`
- `.venv/bin/python -m compileall -q app tests scripts`
- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `cd frontend && npm audit`
- `.venv/bin/python -m pytest -q tests/test_rate_limit.py`
- `unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy; .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8217`，然后 curl `/health` `/ready` `/api/conversations` `/api/upload` 全部符合预期（注意：`http_proxy=127.0.0.1:7897` 会截本地端口的请求，必须 unset 或设 `NO_PROXY=127.0.0.1,localhost`）。
- FastAPI app 导入 smoke test
- AgentGraph 导入 smoke test
- Prompt `.format()` smoke test
- `scripts/ingest.py --help`

## 下一步方向

D12 完成。线上 demo 已可访问。下一步进 D13（README + demo 视频 + 博客）：

1. **README**：加架构图（mermaid）、一键启动说明、demo 截图/GIF、评测报告亮点（v2 + strict judge 反超、reranker 负结果）。
2. **2 分钟 demo 视频**：覆盖上传 → 分析 → 改写 → 历史 4 个核心场景；旁白讲技术亮点（LangGraph 状态机 / Hybrid Search / LLM-as-Judge）。
3. **博客**：掘金/小红书发技术复盘；重点写 3 个故事：(a) v2 prompt + strict judge 反超，(b) reranker 评测负收益放弃集成，(c) Railway 部署踩坑实录。
4. （可选优化）v2 `completeness` 弱点排查；前端补评测报告入口和 JD/简历 diff 视图；加 Redis Embedding 缓存。
5. （可选优化）扩展 eval set 到 30 条，复用 `scripts/build_real_eval_cases.py` 流程。
