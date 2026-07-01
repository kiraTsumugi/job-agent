"""Agent 可调用的 Tool 注册."""

from app.agent.tools.search_jd import search_jd_tool
from app.agent.tools.extract_skills import extract_skills_tool
from app.agent.tools.score_match import score_match_tool
from app.agent.tools.rewrite_section import rewrite_section_tool

ALL_TOOLS = [search_jd_tool, extract_skills_tool, score_match_tool, rewrite_section_tool]
