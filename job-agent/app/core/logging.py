import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"

    logging.basicConfig(level=level, format=fmt, stream=sys.stdout)

    # Quiet noisy third-party loggers
    for lib in ("httpx", "openai", "qdrant_client", "urllib3"):
        logging.getLogger(lib).setLevel(logging.WARNING)
