import json
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # LLM
    LLM_BACKEND: str = "mock"  # mock | openai
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-chat"
    JUDGE_BACKEND: str = "mock"  # mock | openai | anthropic
    JUDGE_MODEL: str = "deepseek-chat"

    # Embedding
    EMBEDDING_BACKEND: str = "hash"  # hash | local | siliconflow
    EMBEDDING_DIM: int = 384
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    ENABLE_LOCAL_RERANKER: bool = False
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://jobagent:jobagent@localhost:5432/jobagent"
    REDIS_URL: str = "redis://localhost:6379/0"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "job_agent_chunks"
    ENABLE_VECTOR_SEARCH: bool = True

    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "DEBUG"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8501"]
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_HEAVY_PER_MIN: int = 30
    RATE_LIMIT_GENERAL_PER_MIN: int = 120

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str) and not v.strip().startswith("["):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return json.loads(v)


settings = Settings()
