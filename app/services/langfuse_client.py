from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

from app.core.config import settings


def is_langfuse_enabled() -> bool:
    return settings.langfuse_enabled


@lru_cache(maxsize=1)
def get_langfuse_handler():
    if not settings.langfuse_enabled:
        return None

    try:
        from langfuse.langchain import CallbackHandler
    except Exception:
        try:
            from langfuse.callback import CallbackHandler
        except Exception:
            return None

    return CallbackHandler()


def graph_observability_config(session_id: str, run_name: str) -> Dict[str, Any]:
    config: Dict[str, Any] = {
        "run_name": run_name,
        "metadata": {
            "session_id": session_id,
            "langfuse_session_id": session_id,
            "app": settings.app_name,
        },
        "tags": ["resume-polisher", run_name],
    }
    handler = get_langfuse_handler()
    if handler:
        config["callbacks"] = [handler]
    return config


def get_openai_client_class():
    if not settings.langfuse_enabled:
        from openai import OpenAI

        return OpenAI

    try:
        from langfuse.openai import OpenAI as LangfuseOpenAI

        return LangfuseOpenAI
    except Exception:
        from openai import OpenAI

        return OpenAI


def flush_langfuse() -> None:
    if not settings.langfuse_enabled:
        return
    try:
        from langfuse import get_client

        get_client().flush()
        return
    except Exception:
        pass

    handler = get_langfuse_handler()
    if not handler:
        return
    langfuse_client = getattr(handler, "langfuse", None)
    flush = getattr(langfuse_client, "flush", None)
    if callable(flush):
        flush()


def langfuse_health() -> Dict[str, Any]:
    handler = get_langfuse_handler()
    return {
        "enabled": settings.langfuse_enabled,
        "host": settings.langfuse_host,
        "callbacks_available": bool(handler),
    }
