"""爬取 BOSS 直聘 / 拉勾 JD 数据。"""

import asyncio
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# 确保项目根目录在 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def crawl_boss(keyword: str = "AI Agent", pages: int = 5) -> list[dict]:
    """爬 BOSS 直聘 JD（反爬严重，仅作占位示例）."""
    logger.warning("BOSS 直聘反爬严格，建议手动复制 JD 或使用浏览器自动化")
    # 实际实现建议用 Playwright 或 Selenium
    return []


async def main():
    jds = await crawl_boss(keyword="AI Agent 实习生", pages=10)

    output_path = Path("data/jds/sample_jds.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if jds:
        output_path.write_text(json.dumps(jds, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Saved {len(jds)} JDs to {output_path}")
    else:
        # 写入示例数据
        sample = [
            {
                "title": "AI Agent 实习生",
                "company": "某科技公司",
                "text": (
                    "岗位要求：\n"
                    "1. 熟练掌握 Python，熟悉 FastAPI/Django\n"
                    "2. 了解 RAG 技术栈：LangChain/LangGraph，向量数据库（Milvus/Qdrant）\n"
                    "3. 有 Agent 开发经验，理解 Tool Calling 和 Function Calling\n"
                    "4. 熟悉 Prompt Engineering，有 Badcase 分析经验\n"
                    "5. 了解 MCP 协议，深度使用过 Claude Code 或 Cursor\n"
                ),
                "url": "",
            }
        ]
        output_path.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Wrote {len(sample)} sample JDs to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
