from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.tools import tool  # type: ignore[import-not-found]

from app.services.vector_store import vector_store


@tool("retrieve_resume_rag_context")
def retrieve_resume_rag_context(query: str, limit: int = 4) -> List[Dict[str, Any]]:
    """从 Milvus 检索简历项目打磨知识，返回命中文档、来源、分数和检索模式。"""

    return vector_store.search(query, limit=limit)


@tool("render_rag_context")
def render_rag_context(rag_context: List[Dict[str, Any]], max_chars: int = 1200) -> str:
    """把 RAG 命中文档渲染成可注入 Agent prompt 的上下文文本。"""

    parts = []
    for item in rag_context:
        parts.append(
            f"[{item.get('title')}] source={item.get('source')} score={item.get('score')}\n"
            f"{item.get('content', '')[:500]}"
        )
    rendered = "\n\n".join(parts)
    return rendered[:max_chars]
