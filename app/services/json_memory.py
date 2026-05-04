from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import settings


def new_session_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]


def save_session(state: Dict[str, Any]) -> str:
    session_id = state.get("session_id") or new_session_id()
    state["session_id"] = session_id
    path = settings.memory_dir / f"{session_id}.json"
    payload = {"saved_at": datetime.now().isoformat(timespec="seconds"), "state": state}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return session_id


def load_session(session_id: str) -> Dict[str, Any]:
    path = settings.memory_dir / f"{session_id}.json"
    if not Path(path).exists():
        raise FileNotFoundError(f"会话不存在: {session_id}")
    return json.loads(path.read_text(encoding="utf-8"))["state"]


def list_sessions() -> List[Dict[str, str]]:
    sessions: List[Dict[str, str]] = []
    for path in sorted(settings.memory_dir.glob("*.json"), reverse=True):
        payload = json.loads(path.read_text(encoding="utf-8"))
        state = payload.get("state", {})
        sessions.append(
            {
                "session_id": state.get("session_id", path.stem),
                "saved_at": payload.get("saved_at", ""),
                "title": state.get("jd_profile", {}).get("target_role", "未命名打磨会话"),
            }
        )
    return sessions
