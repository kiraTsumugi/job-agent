"""Eval runner tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.eval import runner


@pytest.mark.asyncio
async def test_run_agent_for_case_passes_resume_and_jd_context(monkeypatch):
    calls = []

    class FakeGraph:
        def __init__(self, tracer=None):
            self.tracer = tracer

        async def astream(self, message, **kwargs):
            calls.append({"message": message, "kwargs": kwargs})
            yield {"type": "node:analyzer", "data": {"gap_analysis": {"match_score": 81}}}
            yield {"type": "complete", "data": {"gap_analysis": {"match_score": 81}}}

    monkeypatch.setattr(runner, "AgentGraph", FakeGraph)

    case = SimpleNamespace(resume_text="RESUME TEXT", jd_text="JD TEXT")
    output = await runner._run_agent_for_case(case)

    assert output == {"gap_analysis": {"match_score": 81}}
    assert calls == [
        {
            "message": runner.EVAL_USER_MESSAGE,
            "kwargs": {
                "resume_text": "RESUME TEXT",
                "jd_text": "JD TEXT",
                "prompt_version": "v1",
            },
        }
    ]


def test_select_model_output_prefers_complete_event():
    output = runner._select_model_output(
        [
            {"type": "node:analyzer", "data": {"gap_analysis": {"match_score": 1}}},
            {"type": "complete", "data": {"gap_analysis": {"match_score": 2}}},
        ]
    )

    assert output == {"gap_analysis": {"match_score": 2}}


def test_eval_user_message_does_not_trigger_rewrite_intent():
    assert "改写" not in runner.EVAL_USER_MESSAGE
    assert "rewrite" not in runner.EVAL_USER_MESSAGE.lower()
