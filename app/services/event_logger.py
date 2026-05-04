from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import settings


def make_log(agent: str, event: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """创建单条结构化日志，交给 LangGraph reducer 追加到 State。"""

    return {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "agent": agent,
        "event": event,
        "detail": detail,
    }


def add_log(logs: List[Dict[str, Any]] | None, agent: str, event: str, detail: Dict[str, Any]) -> List[Dict[str, Any]]:
    """兼容旧调用：返回追加后的完整日志列表。"""

    next_logs = list(logs or [])
    next_logs.append(make_log(agent, event, detail))
    return next_logs


def persist_event(session_id: str, event: Dict[str, Any]) -> None:
    log_path = settings.log_dir / f"{session_id}.jsonl"
    with log_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")


def read_events(session_id: str) -> List[Dict[str, Any]]:
    log_path = settings.log_dir / f"{session_id}.jsonl"
    if not Path(log_path).exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
