"""Conversation helper tests."""

from app.services.conversation import recent_user_history


def test_recent_user_history_keeps_only_user_messages():
    history = recent_user_history(
        [
            {"role": "user", "content": "第一轮：分析 FastAPI 岗位"},
            {"role": "assistant", "content": '{"gap_analysis": {"match_score": 80}}'},
            {"role": "user", "content": "第二轮：继续改写项目经历"},
        ]
    )

    assert history == [
        {"role": "user", "content": "第一轮：分析 FastAPI 岗位"},
        {"role": "user", "content": "第二轮：继续改写项目经历"},
    ]
