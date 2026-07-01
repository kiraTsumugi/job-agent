"""
MCP Server — 简历匹配 Tool 服务

让 Claude Code / Cursor 等 MCP 客户端可以直接调用 RAG 检索和简历分析能力。

启动方式:
  mcp dev mcp/server.py          # 本地调试
  mcp run mcp/server.py          # 生产模式（stdio transport）

或在 Claude Code 配置:
  {
    "mcpServers": {
      "job-agent": {
        "command": "python",
        "args": ["-m", "mcp.server", "--file", "mcp/server.py"]
      }
    }
  }
"""

from __future__ import annotations

import json
import logging

from app.rag.retriever import hybrid_search
from app.rag.query_rewriter import rewrite_query
from app.services.llm import llm_complete

logger = logging.getLogger(__name__)

# ─── MCP Tool 定义 ────────────────────────────────────

TOOLS = [
    {
        "name": "search_similar_jds",
        "description": "搜索与给定岗位名称或 JD 描述最相似的岗位。输入岗位名或 JD 片段，返回 Top5 相关 JD。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "岗位名称或 JD 描述片段"},
                "top_k": {"type": "integer", "description": "返回结果数 (1-20)", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "match_resume_to_jd",
        "description": "将简历与目标 JD 进行智能匹配分析，输出匹配分、gap 列表、改写建议。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resume_text": {"type": "string", "description": "简历全文"},
                "jd_text": {"type": "string", "description": "JD 全文"},
            },
            "required": ["resume_text", "jd_text"],
        },
    },
    {
        "name": "rewrite_resume_section",
        "description": "根据 JD 要求和用户指令改写简历的指定段落。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "section_text": {"type": "string", "description": "要改写的原始段落"},
                "instruction": {"type": "string", "description": "改写指令，如 '更突出RAG项目经验'"},
                "jd_context": {"type": "string", "description": "目标 JD 关键要求（可选）"},
            },
            "required": ["section_text", "instruction"],
        },
    },
]

# ─── Tool 实现 ────────────────────────────────────────

MATCH_PROMPT = """你是一个资深招聘顾问。请分析以下简历与 JD 的匹配度。

JD：
{jd_text}

简历：
{resume_text}

输出 JSON：
{{
  "match_score": 75,
  "gaps": [{{"category": "技能|经验|项目", "description": "...", "severity": "high|medium|low", "suggestion": "..."}}],
  "strengths": ["匹配点1"],
  "rewrite_suggestions": ["改写建议1"],
  "summary": "总体评价"
}}
"""


async def handle_tool_call(tool_name: str, arguments: dict) -> list[dict]:
    """MCP tool dispatch."""
    if tool_name == "search_similar_jds":
        query = arguments["query"]
        top_k = min(arguments.get("top_k", 5), 20)

        # 先改写查询
        rewritten = await rewrite_query(query)
        results = await hybrid_search(rewritten, top_k=top_k, use_rerank=True)

        return [
            {
                "type": "text",
                "text": json.dumps(
                    [{"id": r.id, "text": r.text[:500], "score": r.score} for r in results],
                    ensure_ascii=False,
                    indent=2,
                ),
            }
        ]

    elif tool_name == "match_resume_to_jd":
        resume = arguments["resume_text"][:4000]
        jd = arguments["jd_text"][:4000]

        prompt = MATCH_PROMPT.format(resume_text=resume, jd_text=jd)
        raw = await llm_complete(prompt=prompt, max_tokens=2000)

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            result = {"raw": raw}

        return [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]

    elif tool_name == "rewrite_resume_section":
        prompt = f"""你是一个专业简历写手。请根据以下要求改写简历段落。

改写指令：{arguments['instruction']}
JD 上下文：{arguments.get('jd_context', '无')}

原始段落：
{arguments['section_text'][:2000]}

请直接输出改写后的段落，不需要 JSON 包装。"""

        rewritten = await llm_complete(prompt=prompt, max_tokens=2000)
        return [{"type": "text", "text": rewritten}]

    else:
        return [{"type": "text", "text": f"Unknown tool: {tool_name}"}]


# ─── MCP Entry (简化版 — 实际接入通过 mcp CLI 框架) ───

if __name__ == "__main__":
    import asyncio
    import sys

    async def main():
        if len(sys.argv) < 2:
            print("Usage: python mcp/server.py <tool_name> '<json_args>'")
            sys.exit(1)

        tool_name = sys.argv[1]
        args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        results = await handle_tool_call(tool_name, args)
        for r in results:
            print(r["text"])

    asyncio.run(main())
