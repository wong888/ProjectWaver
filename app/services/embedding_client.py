from __future__ import annotations

import hashlib
from typing import Dict, List

import numpy as np
from openai import OpenAI

from app.core.config import settings


class EmbeddingClient:
    """统一管理 RAG 向量生成。

    provider=compatible/openai 时走 OpenAI Embeddings 兼容协议；接口失败时降级到
    hash embedding，并在 health 信息里明确标记，避免“假装真实 RAG”。
    """

    def __init__(self) -> None:
        self.provider = settings.embedding_provider.lower()
        self.model = settings.embedding_model
        self.base_url = settings.embedding_base_url
        self.dimension = settings.embedding_dim
        self.mode = "hash"
        self.last_error = ""
        self.client = None
        self.local_model = None
        if self.provider in {"local", "fastembed"}:
            try:
                from fastembed import TextEmbedding

                self.local_model = TextEmbedding(model_name=self.model)
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
        if self.provider in {"compatible", "openai"} and settings.embedding_api_key:
            self.client = OpenAI(
                api_key=settings.embedding_api_key,
                base_url=self.base_url,
                timeout=settings.embedding_timeout_seconds,
            )

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        clean_texts = [text if text.strip() else "empty" for text in texts]
        if self.local_model:
            try:
                vectors = [vector.tolist() for vector in self.local_model.embed(clean_texts)]
                if vectors:
                    self.dimension = len(vectors[0])
                    self.mode = "local"
                    self.last_error = ""
                return vectors
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
        if self.client:
            try:
                response = self.client.embeddings.create(model=self.model, input=clean_texts)
                vectors = [item.embedding for item in response.data]
                if vectors:
                    self.dimension = len(vectors[0])
                    self.mode = "remote"
                    self.last_error = ""
                return vectors
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
        self.mode = "hash"
        return [self._hash_embed(text) for text in clean_texts]

    def embed(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]

    def health(self) -> Dict[str, str | int | bool]:
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "mode": self.mode,
            "dimension": self.dimension,
            "remote_enabled": bool(self.client),
            "last_error": self.last_error,
        }

    def _hash_embed(self, text: str) -> List[float]:
        vector = np.zeros(settings.embedding_dim, dtype=np.float32)
        for token in text.lower().split():
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            vector[int(digest, 16) % settings.embedding_dim] += 1.0
        norm = np.linalg.norm(vector)
        return (vector / norm).tolist() if norm else vector.tolist()


embedding_client = EmbeddingClient()
