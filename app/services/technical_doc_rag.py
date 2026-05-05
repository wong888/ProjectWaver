from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Tuple

from app.services.vector_store import vector_store


TECH_DOC_SOURCE_PREFIX = "techdoc"


def _slug(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z_.-]", "_", value)[:120] or "section"


def _flatten(section: str, value: Any) -> Iterable[Tuple[str, str]]:
    if isinstance(value, dict):
        for key, nested in value.items():
            yield from _flatten(f"{section}.{key}" if section else str(key), nested)
        return
    if isinstance(value, list):
        for index, nested in enumerate(value, start=1):
            yield from _flatten(f"{section}.{index}", nested)
        return
    text = str(value).strip()
    if text:
        yield section, text


def technical_doc_source_prefix(session_id: str, version: int) -> str:
    return f"{TECH_DOC_SOURCE_PREFIX}://{session_id}/v{version}/"


def technical_doc_chunks(session_id: str, technical_doc: Dict[str, Any]) -> List[Dict[str, str]]:
    version = int(technical_doc.get("version", 1))
    prefix = technical_doc_source_prefix(session_id, version)
    chunks: List[Dict[str, str]] = []
    for index, (section, content) in enumerate(_flatten("", technical_doc), start=1):
        if section == "version":
            continue
        source = f"{prefix}{_slug(section)}"
        title = f"技术文档 v{version} | {section}"
        chunks.append(
            {
                "title": title,
                "source": source,
                "content": f"section: {section}\nversion: {version}\ncontent: {content}",
                "chunk_index": str(index),
            }
        )
    return chunks


def index_technical_doc(session_id: str, technical_doc: Dict[str, Any]) -> Dict[str, Any]:
    chunks = technical_doc_chunks(session_id, technical_doc)
    inserted = vector_store.insert_documents(chunks)
    return {
        "version": int(technical_doc.get("version", 1)),
        "chunk_count": len(chunks),
        "inserted_chunks": inserted,
        "source_prefix": technical_doc_source_prefix(session_id, int(technical_doc.get("version", 1))),
    }


def _keyword_score(query: str, content: str) -> int:
    terms = [term for term in re.split(r"\W+", query.lower()) if len(term) >= 2]
    lowered = content.lower()
    return sum(1 for term in terms if term in lowered)


def _local_search(query: str, session_id: str, technical_doc: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    ranked = []
    for chunk in technical_doc_chunks(session_id, technical_doc):
        score = _keyword_score(query, chunk["content"])
        ranked.append((score, chunk))
    ranked.sort(key=lambda item: item[0], reverse=True)
    fallback = ranked[:limit] if any(score > 0 for score, _ in ranked) else ranked[:limit]
    return [
        {
            **chunk,
            "score": float(score),
            "retrieval_mode": "local_technical_doc",
        }
        for score, chunk in fallback
    ]


def search_technical_doc(query: str, session_id: str, technical_doc: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    if not technical_doc:
        return []
    version = int(technical_doc.get("version", 1))
    source_prefix = technical_doc_source_prefix(session_id, version)
    try:
        hits = vector_store.search(query, limit=limit, source_prefix=source_prefix)
    except Exception:
        hits = []
    return hits or _local_search(query, session_id, technical_doc, limit)


def render_technical_doc_hits(hits: List[Dict[str, Any]], max_chars: int = 1600) -> str:
    parts = []
    for hit in hits:
        parts.append(
            f"[{hit.get('title')}] source={hit.get('source')} score={hit.get('score')} mode={hit.get('retrieval_mode')}\n"
            f"{str(hit.get('content', ''))[:700]}"
        )
    rendered = "\n\n".join(parts)
    return rendered[:max_chars]


def compact_technical_doc(technical_doc: Dict[str, Any]) -> str:
    return json.dumps(technical_doc, ensure_ascii=False, indent=2)[:2400]
