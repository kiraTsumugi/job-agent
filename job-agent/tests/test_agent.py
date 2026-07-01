"""Agent 模块单元测试."""

import pytest


class TestAgentGraph:
    """Agent 状态机测试（需 mock LLM 调用）."""

    def test_graph_import(self):
        from app.agent.graph import AgentGraph
        assert AgentGraph is not None

    def test_state_initialization(self):
        from app.agent.graph import AgentState

        state: AgentState = {
            "user_message": "帮我看看这份简历和 JD 匹配吗",
            "resume_token": None,
            "jd_id": None,
            "plan": {},
            "retrieved_jds": [],
            "gap_analysis": {},
            "rewritten": None,
            "error": None,
        }
        assert state["user_message"] is not None
        assert state["error"] is None


class TestPrompts:
    def test_prompt_loading(self):
        from app.agent.prompts import load_prompt

        plan = load_prompt("plan")
        assert "intent" in plan
        assert "analyze" in plan

        analyze = load_prompt("analyze")
        assert "match_score" in analyze
        assert "gaps" in analyze

        rewrite = load_prompt("rewrite")
        assert "sections" in rewrite

    def test_prompt_version_resolution_and_manifest(self):
        from app.agent.prompts import build_prompt_manifest, resolve_prompt_version

        assert resolve_prompt_version("v1") == "v1"
        assert resolve_prompt_version("v2") == "v2"
        assert resolve_prompt_version("latest") == "v2"

        manifest = build_prompt_manifest("v2")

        assert manifest["version"] == "v2"
        assert len(manifest["fingerprint"]) == 64
        assert manifest["files"] == {
            "plan": "v2_plan.md",
            "analyze": "v2_analyze.md",
            "rewrite": "v2_rewrite.md",
        }

    def test_missing_explicit_prompt_version_fails(self):
        from app.agent.prompts import resolve_prompt_version

        with pytest.raises(FileNotFoundError):
            resolve_prompt_version("v999")

    def test_v2_analyzer_prompt_has_strict_gap_schema(self):
        from app.agent.prompts import load_prompt

        prompt = load_prompt("analyze", "v2")

        assert '"schema_version": "v2_analyze"' in prompt
        assert "must_have_skill" in prompt
        assert "preferred_skill" in prompt
        assert "domain_experience" in prompt
        assert "seniority_scope" in prompt
        assert "project_evidence" in prompt
        assert "evidence_status" in prompt
        assert "rewrite_action" in prompt
        assert "不要编造简历事实" in prompt

        rendered = prompt.format(
            jd_context="岗位要求：Python, FastAPI",
            resume_text="简历：Python 后端",
            user_message="分析匹配度",
        )
        assert "{jd_context}" not in rendered
        assert "{resume_text}" not in rendered
        assert "{user_message}" not in rendered
