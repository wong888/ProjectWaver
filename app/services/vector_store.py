from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Optional

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

from app.core.config import settings
from app.services.embedding_client import embedding_client


SEED_DOCS = [
    {
        "source": "seed://resume-boundary",
        "title": "互联网后端简历项目边界",
        "content": "简历项目应围绕真实业务问题、稳定性、性能、数据一致性、灰度发布、监控告警展开，避免声称支撑无法证明的超大规模流量。",
    },
    {
        "source": "seed://backend-structure",
        "title": "高质量后端项目结构",
        "content": "可上线项目需要包含接口层、服务层、数据层、异步任务、缓存、日志、指标、告警、错误处理、容量估算与回滚方案。",
    },
    {
        "source": "seed://interview-attack",
        "title": "面试攻防常见漏洞",
        "content": "面试官会追问幂等性、限流降级、缓存击穿、消息重复消费、数据库索引、事务边界、故障恢复、部署发布和团队协作。",
    },
    {
        "source": "seed://compliance",
        "title": "合规风控表达",
        "content": "不能伪造公司经历、真实用户量和线上收益；可以描述个人复现、压测指标、设计目标、验证方法和可解释的工程取舍。",
    },
]


def _safe_name(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z_]", "_", value)


def _doc_id(source: str, title: str, content: str, chunk_index: int) -> str:
    raw = f"{source}|{title}|{chunk_index}|{content}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


class MilvusVectorStore:
    def __init__(self) -> None:
        probe_vector = embedding_client.embed("dimension probe for rag collection")
        self.dim = len(probe_vector)
        provider_tag = _safe_name(embedding_client.mode)
        self.collection_name = f"{settings.milvus_collection}_{provider_tag}_{self.dim}"
        self.available = False
        self.last_error = ""
        try:
            connections.connect(host=settings.milvus_host, port=settings.milvus_port)
            self._ensure_collection()
            self.available = True
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.available = False

    def _ensure_collection(self) -> None:
        if utility.has_collection(self.collection_name):
            self.collection = Collection(self.collection_name)
            if self.collection.num_entities == 0:
                self.insert_documents(SEED_DOCS)
            return

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=4096),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
        ]
        schema = CollectionSchema(fields, description="Resume polishing RAG knowledge base")
        self.collection = Collection(self.collection_name, schema)
        self.collection.create_index("embedding", {"index_type": "AUTOINDEX", "metric_type": "COSINE", "params": {}})
        self.insert_documents(SEED_DOCS)

    def insert_documents(self, documents: List[Dict[str, str]]) -> int:
        if not self.available and not hasattr(self, "collection"):
            return 0
        if not documents:
            return 0

        normalized = []
        for index, doc in enumerate(documents):
            title = doc.get("title", "未命名知识片段")[:256]
            source = doc.get("source", "manual")[:512]
            content = doc.get("content", "").strip()[:4096]
            if not content:
                continue
            chunk_index = int(doc.get("chunk_index", index))
            normalized.append(
                {
                    "doc_id": _doc_id(source, title, content, chunk_index),
                    "title": title,
                    "source": source,
                    "chunk_index": chunk_index,
                    "content": content,
                }
            )

        if not normalized:
            return 0

        vectors = embedding_client.embed_texts([doc["content"] for doc in normalized])
        self.collection.insert(
            [
                [doc["doc_id"] for doc in normalized],
                [doc["title"] for doc in normalized],
                [doc["source"] for doc in normalized],
                [doc["chunk_index"] for doc in normalized],
                [doc["content"] for doc in normalized],
                vectors,
            ]
        )
        self.collection.flush()
        return len(normalized)

    def search(self, query: str, limit: int = 4, source_prefix: Optional[str] = None) -> List[Dict[str, str]]:
        if not self.available:
            if source_prefix:
                return []
            return [{**doc, "score": 0.0, "retrieval_mode": "fallback_seed"} for doc in SEED_DOCS[:limit]]

        self.collection.load()
        search_kwargs = {
            "data": [embedding_client.embed(query)],
            "anns_field": "embedding",
            "param": {"metric_type": "COSINE", "params": {}},
            "limit": limit,
            "output_fields": ["doc_id", "title", "source", "chunk_index", "content"],
        }
        if source_prefix:
            search_kwargs["expr"] = f'source like "{source_prefix}%"'
        results = self.collection.search(**search_kwargs)
        return [
            {
                "doc_id": hit.entity.get("doc_id"),
                "title": hit.entity.get("title"),
                "source": hit.entity.get("source"),
                "chunk_index": hit.entity.get("chunk_index"),
                "content": hit.entity.get("content"),
                "score": round(float(hit.score), 4),
                "retrieval_mode": embedding_client.mode,
            }
            for hit in results[0]
        ]

    def health(self) -> Dict[str, object]:
        doc_count = 0
        if self.available:
            try:
                doc_count = int(self.collection.num_entities)
            except Exception:
                doc_count = 0
        return {
            "milvus_available": self.available,
            "collection": self.collection_name,
            "dimension": self.dim,
            "doc_count": doc_count,
            "last_error": self.last_error,
            "embedding": embedding_client.health(),
        }


vector_store = MilvusVectorStore()
