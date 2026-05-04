from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from openai import OpenAI

from app.core.config import settings


class LLMClient:
    """OpenAI 与国内兼容接口共用同一套 Chat Completions 协议。

    当没有配置 API Key 或 LLM_PROVIDER=mock 时，会走确定性本地规则生成，
    方便无网络环境完成项目演示。
    """

    def __init__(self) -> None:
        self.provider = settings.llm_provider.lower()
        self.client = None
        if self.provider != "mock" and settings.llm_api_key:
            self.client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                timeout=settings.llm_timeout_seconds,
                max_retries=settings.llm_max_retries,
            )

    def _compact(self, text: str) -> str:
        if len(text) <= settings.llm_max_prompt_chars:
            return text
        keep = settings.llm_max_prompt_chars
        return text[:keep] + "\n\n[上下文已截断，保留最相关信息继续生成 JSON]"

    def _parse_json(self, content: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.S)
            return json.loads(match.group(0)) if match else fallback

    def _chat_create(self, system: str, user: str, use_json_mode: bool):
        payload: Dict[str, Any] = {
            "model": settings.llm_model,
            "temperature": settings.llm_temperature,
            "messages": [
                {"role": "system", "content": system + "\n必须只输出合法 JSON，不要 Markdown。"},
                {"role": "user", "content": self._compact(user)},
            ],
            "max_tokens": settings.llm_max_tokens,
        }
        if use_json_mode:
            payload["response_format"] = {"type": "json_object"}
        return self.client.chat.completions.create(**payload)

    def json_chat(self, system: str, user: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
        if not self.client:
            return fallback

        use_json_mode = settings.llm_json_mode.lower() in {"auto", "true", "1", "yes"}
        try:
            response = self._chat_create(system, user, use_json_mode=use_json_mode)
            content = response.choices[0].message.content or "{}"
            parsed = self._parse_json(content, fallback)
            if not use_json_mode:
                parsed["_llm_json_mode_disabled"] = True
            return parsed
        except Exception as exc:
            error_text = str(exc)
            if "response_format" in error_text or "json_object" in error_text:
                try:
                    response = self._chat_create(system, user, use_json_mode=False)
                    content = response.choices[0].message.content or "{}"
                    parsed = self._parse_json(content, fallback)
                    parsed["_llm_json_mode_disabled"] = True
                    return parsed
                except Exception as retry_exc:
                    enriched = dict(fallback)
                    enriched["_llm_fallback_reason"] = f"{type(retry_exc).__name__}: {retry_exc}"
                    return enriched
            enriched = dict(fallback)
            enriched["_llm_fallback_reason"] = f"{type(exc).__name__}: {exc}"
            return enriched


def split_keywords(text: str, stack: str) -> List[str]:
    candidates = [
        "Python",
        "FastAPI",
        "Django",
        "Flask",
        "Go",
        "Java",
        "Spring",
        "Redis",
        "MySQL",
        "PostgreSQL",
        "Kafka",
        "RabbitMQ",
        "Docker",
        "Kubernetes",
        "Milvus",
        "LangGraph",
        "RAG",
        "LLM",
        "微服务",
        "高并发",
        "缓存",
        "消息队列",
        "可观测性",
        "CI/CD",
    ]
    source = f"{text}\n{stack}".lower()
    return [word for word in candidates if word.lower() in source][:12]


llm_client = LLMClient()
