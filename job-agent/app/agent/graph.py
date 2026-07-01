"""
LangGraph Agent 主状态机

Graph: planner → retriever → analyzer → (rewriter | END)
一次完整流程：拆解用户意图 → 检索相关 JD → 简历-JD gap 分析 → 改写建议
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from langgraph.graph import StateGraph, END

from app.core.trace import Tracer
from app.agent.state import AgentState
from app.agent.nodes.planner import planner_node
from app.agent.nodes.retriever import retriever_node
from app.agent.nodes.analyzer import analyzer_node
from app.agent.nodes.rewriter import rewriter_node
from app.agent.prompts import resolve_prompt_version

logger = logging.getLogger(__name__)


class AgentGraph:
    """封装 LangGraph 执行，对外提供 astream 接口."""

    def __init__(self, tracer: Tracer | None = None):
        self.tracer = tracer

        graph = StateGraph(AgentState)
        graph.add_node("planner", self._wrap(planner_node))
        graph.add_node("retriever", self._wrap(retriever_node))
        graph.add_node("analyzer", self._wrap(analyzer_node))
        graph.add_node("rewriter", self._wrap(rewriter_node))

        graph.set_entry_point("planner")
        graph.add_edge("planner", "retriever")
        graph.add_edge("retriever", "analyzer")
        graph.add_conditional_edges(
            "analyzer",
            lambda s: "rewriter" if s.get("plan", {}).get("intent") == "rewrite" else END,
            {"rewriter": "rewriter", END: END},
        )
        graph.add_edge("rewriter", END)

        self._graph = graph.compile()

    def _wrap(self, fn):
        """为每个节点包装 trace span."""
        async def wrapped(state: AgentState) -> dict:
            node_name = fn.__name__.replace("_node", "")
            span = None
            if self.tracer:
                span = self.tracer.span(node_name)
                await span.start(state.get("user_message"))
            try:
                result = await fn(state)
                if span:
                    await span.end(result)
                return result
            except Exception as e:
                logger.exception("Node %s failed", node_name)
                if span:
                    await span.end(error=str(e))
                return {"error": str(e)}
        return wrapped

    async def astream(
        self,
        message: str,
        resume_token: str | None = None,
        jd_id: str | None = None,
        conversation_history: list[dict] | None = None,
        resume_text: str | None = None,
        jd_text: str | None = None,
        prompt_version: str | None = None,
    ) -> AsyncIterator[dict]:
        """流式执行 Agent，每个节点完成后 yield 事件."""
        resolved_prompt_version = resolve_prompt_version(prompt_version)
        initial_state: AgentState = {
            "user_message": message,
            "resume_token": resume_token,
            "jd_id": jd_id,
            "conversation_history": conversation_history or [],
            "prompt_version": resolved_prompt_version,
            "resume_text": resume_text,
            "jd_text": jd_text,
            "plan": {},
            "retrieved_jds": [],
            "gap_analysis": {},
            "rewritten": None,
            "error": None,
        }

        async for event in self._graph.astream(initial_state):
            node_name = list(event.keys())[0]
            yield {"type": f"node:{node_name}", "data": event[node_name]}

        yield {"type": "complete", "data": event.get(list(event.keys())[-1], {}) if event else {}}
