from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    """集中管理运行时配置，便于本地演示和 Docker 部署切换。"""

    app_name: str = "Multi-Agent程序员简历项目闭环打磨系统"
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "0"))
    llm_json_mode: str = os.getenv("LLM_JSON_MODE", "auto")
    llm_max_prompt_chars: int = int(os.getenv("LLM_MAX_PROMPT_CHARS", "5000"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "1200"))

    milvus_host: str = os.getenv("MILVUS_HOST", "localhost")
    milvus_port: str = os.getenv("MILVUS_PORT", "19530")
    milvus_collection: str = os.getenv("MILVUS_COLLECTION", "resume_polisher_knowledge")
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "hash")
    embedding_api_key: str = os.getenv("EMBEDDING_API_KEY") or os.getenv("LLM_API_KEY", "")
    embedding_base_url: str = os.getenv("EMBEDDING_BASE_URL") or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "384"))
    embedding_timeout_seconds: float = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "20"))

    data_dir: Path = ROOT_DIR / "data"
    memory_dir: Path = ROOT_DIR / "data" / "memory"
    log_dir: Path = ROOT_DIR / "data" / "logs"
    rag_dir: Path = ROOT_DIR / "data" / "rag"


settings = Settings()

for directory in [settings.memory_dir, settings.log_dir, settings.rag_dir]:
    directory.mkdir(parents=True, exist_ok=True)
