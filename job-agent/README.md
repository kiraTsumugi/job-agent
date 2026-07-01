# AI 求职助手 — 简历 × JD 智能匹配 Agent

基于 **RAG + LangGraph Agent + MCP** 的简历-JD 匹配与改写服务。

## 架构

```
用户 → FastAPI (SSE) → LangGraph Agent
                           ├── Planner (意图拆解)
                           ├── Retriever (Hybrid Search + Rerank)
                           ├── Analyzer (gap 分析)
                           └── Rewriter (简历改写)
                           ↓
                     Qdrant (向量) + PostgreSQL (结构化) + Redis (缓存)
                           
MCP Server → Claude Code / Cursor 可直接调用检索与匹配能力
```

## 快速启动

```bash
# 1. 安装依赖
pip install -e ".[dev]"

# 如需本地 bge-m3 / bge-reranker 模型，再安装重依赖
pip install -e ".[ml]"

# 2. 启动基础设施
docker compose up -d postgres qdrant redis

# 3. 配置环境变量
cp .env.example .env
# 默认 LLM_BACKEND=mock，可无 API Key 跑通本地主链路
# 接 DeepSeek/千问等 OpenAI-compatible 服务时，设置 LLM_BACKEND=openai 并配置 base_url/key/model

# 4. 启动 API
uvicorn app.main:app --reload --port 8000

# 5. 启动前端
cd frontend
npm install
npm run dev

# 6. (可选) 启动 MCP Server
python mcp/server.py
```

## API 文档

启动后访问 http://localhost:8000/docs 查看 Swagger UI。

前端默认访问 `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`。

| 端点 | 说明 |
|------|------|
| `POST /api/chat/stream` | SSE 流式对话 |
| `GET /api/conversations` | 列出历史对话 |
| `GET /api/conversations/{conversation_id}` | 读取单个对话消息 |
| `POST /api/upload` | 上传简历 PDF/DOCX |
| `POST /api/jds` | 创建 JD |
| `GET /api/jds` | 列出 JD |
| `POST /api/jds/search` | 混合检索 JD |
| `POST /api/eval/run` | 触发评测 |
| `GET /api/eval/results` | 查看评测结果 |
| `GET /health` | 存活检查 |
| `GET /ready` | PostgreSQL/Redis/Qdrant 就绪诊断 |

## 部署

部署约定见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。

## 评测

```bash
# 生成示例评测集
python scripts/eval_run.py

# 跑评测（需 PG 就绪）
curl -X POST http://localhost:8000/api/eval/run \
  -H "Content-Type: application/json" \
  -d '{"run_id": "run_001", "prompt_version": "v1", "chunking_strategy": "semantic"}'
```

## 本地测试

```bash
# 单元测试（数据库集成测试默认跳过）
pytest -q

# 启动基础设施
docker compose up -d postgres qdrant redis

# 写入样例 JD 到 PostgreSQL
python scripts/ingest.py

# 同时写入 Qdrant 向量库（默认 hash embedding，安装 .[ml] 后可切 local 模型）
python scripts/ingest.py --vectors

# 数据库集成测试
RUN_DB_TESTS=1 pytest -q tests/test_db_integration.py

# Qdrant 向量集成测试
RUN_VECTOR_TESTS=1 pytest -q tests/test_vector_integration.py

# Agent 主链路集成测试（mock LLM，无需外部 API Key）
RUN_AGENT_TESTS=1 pytest -q tests/test_agent_integration.py

# Chat SSE API 集成测试（mock LLM，验证前端可消费事件流）
RUN_CHAT_TESTS=1 pytest -q tests/test_chat_integration.py

# 真实 LLM smoke test（需 .env 配好 DeepSeek/兼容 OpenAI API）
python scripts/llm_smoke.py --backend openai

# 真实 LLM + Chat SSE smoke test（需 PG/Qdrant/Redis 已启动）
python scripts/chat_smoke.py --backend openai

# 真实招聘 JD 质量烟测（抓取少量公开 job board API 样例）
python scripts/real_jd_quality_smoke.py --backend openai --limit 3

# 固化 8 条真实 JD eval cases 到 JSONL
python scripts/build_real_eval_cases.py --limit 8

# 读取并校验 eval cases
python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl

# 导入 eval cases 到 PostgreSQL（幂等，重复运行会跳过已存在样例）
python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl --import-db

# 用 mock LLM 跑 eval runner，验证 8 条 eval cases 的评测链路
LLM_BACKEND=mock python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl \
  --run-id runner_smoke_mock --prompt-version v1

# 用 v2 prompt 跑 mock eval，验证 analyzer 新 schema 和 gap 分类
LLM_BACKEND=mock JUDGE_BACKEND=mock python scripts/eval_run.py \
  --file data/eval/real_jd_cases.jsonl \
  --run-id v2_prompt_mock_smoke --prompt-version v2 \
  --export-report --archive

# 用 DeepSeek 同时跑主链路和 judge（复用 DeepSeek API）
LLM_BACKEND=openai JUDGE_BACKEND=openai JUDGE_MODEL=deepseek-chat \
  python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl \
  --run-id deepseek_judge_smoke --prompt-version v1

# 用 DeepSeek 跑 v2 prompt，生成可与 v1 对比的归档报告
LLM_BACKEND=openai JUDGE_BACKEND=openai JUDGE_MODEL=deepseek-chat \
  python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl \
  --run-id deepseek_judge_v2 --prompt-version v2 \
  --export-report --archive

# 导出已有 eval run 的 JSON/Markdown 报告；--archive 使用 prompt 版本归档目录
LLM_BACKEND=openai JUDGE_BACKEND=openai JUDGE_MODEL=deepseek-chat \
  python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl \
  --export-run-id deepseek_judge_smoke --archive

# 比较两个已有 run_id，输出分数变化和退化 case；--archive 使用 prompt 版本归档目录
python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl \
  --compare-run-ids deepseek_judge_smoke deepseek_judge_retry_smoke \
  --archive

# 或直接比较两个已导出的 report JSON
python scripts/eval_run.py --file data/eval/real_jd_cases.jsonl \
  --compare-reports \
  data/eval/reports/deepseek_judge_smoke.json \
  data/eval/reports/deepseek_judge_retry_smoke.json \
  --archive
```

Eval 报告归档约定：

- 普通导出保持兼容：`data/eval/reports/<run_id>.json|md`
- `--archive` 导出：`data/eval/reports/prompt_<version>/<run_id>.json|md`
- 普通 diff 保持兼容：`data/eval/reports/diffs/<baseline>__vs__<candidate>.diff.json|md`
- `--archive` diff：`data/eval/reports/diffs/prompt_<baseline_version>__vs__prompt_<candidate_version>/<baseline>__vs__<candidate>.diff.json|md`
- report 内会记录 `prompt_version`、prompt 文件清单和 prompt 指纹；显式指定不存在的 prompt version 会直接失败，不做静默 fallback。

## MCP 集成

在 Claude Code 配置中添加：

```json
{
  "mcpServers": {
    "job-agent": {
      "command": "python",
      "args": ["mcp/server.py"]
    }
  }
}
```

## 技术栈

- **Agent 编排**: LangGraph 状态机 + 4 个自定义 Tool
- **RAG**: bge-m3 嵌入 + Hybrid Search (BM25 + 向量 + RRF) + bge-reranker-v2-m3
- **后端**: FastAPI + Pydantic v2 + SQLAlchemy 2.0
- **向量库**: Qdrant
- **关系库**: PostgreSQL 16
- **评测**: LLM-as-Judge (Claude Haiku) + 自研 Trace 系统
- **MCP**: MCP Server 供 Claude Code/Cursor 调用
