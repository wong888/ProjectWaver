from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

from app.core.config import settings
from app.services.vector_store import vector_store


def chunk_text(text: str, chunk_size: int = 700, overlap: int = 120) -> List[str]:
    """按段落优先切分，过长段落再滑窗，保证每个 chunk 可直接送入 embedding。"""

    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    chunks: List[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) <= chunk_size:
            current = f"{current}\n\n{paragraph}".strip()
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= chunk_size:
            current = paragraph
            continue
        start = 0
        while start < len(paragraph):
            chunks.append(paragraph[start : start + chunk_size])
            start += chunk_size - overlap
        current = ""
    if current:
        chunks.append(current)
    return chunks


def load_json_docs(path: Path) -> List[Dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = [payload]
    docs = []
    for index, item in enumerate(payload):
        title = str(item.get("title") or path.stem)
        content = str(item.get("content") or item.get("text") or "")
        for chunk_index, chunk in enumerate(chunk_text(content)):
            docs.append(
                {
                    "title": title,
                    "source": str(item.get("source") or path.name),
                    "chunk_index": index * 1000 + chunk_index,
                    "content": chunk,
                }
            )
    return docs


def load_text_docs(path: Path) -> List[Dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    title = path.stem.replace("_", " ")
    return [
        {"title": title, "source": path.name, "chunk_index": index, "content": chunk}
        for index, chunk in enumerate(chunk_text(text))
    ]


def load_documents() -> List[Dict[str, str]]:
    docs: List[Dict[str, str]] = []
    for path in sorted(settings.rag_dir.glob("*")):
        if path.suffix.lower() == ".json":
            docs.extend(load_json_docs(path))
        elif path.suffix.lower() in {".md", ".txt"}:
            docs.extend(load_text_docs(path))
    return docs


def main() -> None:
    docs = load_documents()
    inserted = vector_store.insert_documents(docs)
    print(
        json.dumps(
            {
                "loaded_chunks": len(docs),
                "inserted_chunks": inserted,
                "vector_store": vector_store.health(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
