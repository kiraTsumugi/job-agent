# 项目进度

## 当前阶段

项目处在 `AI_Agent_实习项目方案.md` 的 D2 收口阶段。

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

## 主要缺口

- 项目虚拟环境 `.venv` 已创建；默认依赖和测试依赖用于后端开发，ML 本地模型依赖需要单独安装 `.[ml]`。
- Eval runner 已有骨架，但依赖 Agent 和外部 LLM key。
- 前端还没有实现。

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
- `.venv/bin/python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl --export-run-id v2_prompt_mock_smoke_20260701 --archive --report-dir /tmp/job-agent-v2-report-smoke-2`
- FastAPI app 导入 smoke test
- AgentGraph 导入 smoke test
- Prompt `.format()` smoke test
- `scripts/ingest.py --help`

## 下一步方向

D2 的数据库、Qdrant、Agent mock 主链路、API/SSE 基础路径、最小会话上下文、DeepSeek smoke 验证、真实 JD 质量烟测、固定 eval cases、eval runner 上下文传递、DeepSeek-as-Judge、eval report 导出、report diff、prompt version 标记、报告归档约定和 v2 analyzer schema 已经收口。下一步应该用真实 DeepSeek 跑 v2 并比较 v1/v2：

1. 用 `--prompt-version v2` 跑 DeepSeek 主链路和 DeepSeek judge。
2. 导出 `prompt_v2` 归档报告。
3. 用 report diff 比较 v1/v2 的退化 case。
4. 再收紧 judge prompt，降低解释性废话和字段漂移。
5. 之后再做前端。
