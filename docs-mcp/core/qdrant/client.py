from __future__ import annotations
from typing import Any
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from core.config import get_settings
from core.models import DocumentChunk

class QdrantVectorStore:
    def __init__(self, url: str | None=None, collection: str | None=None, dim: int | None=None):
        s=get_settings(); self.collection=collection or s.collection_name; self.dim=dim or s.embedding_dim; self.client=QdrantClient(url=url or s.qdrant_url)

    def ensure_collection(self):
        names=[c.name for c in self.client.get_collections().collections]
        if self.collection not in names:
            self.client.create_collection(self.collection, vectors_config=qm.VectorParams(size=self.dim, distance=qm.Distance.COSINE))

    def upsert(self, chunks: list[DocumentChunk], vectors: list[list[float]]):
        self.ensure_collection()
        points=[qm.PointStruct(id=c.id, vector=v, payload=c.payload()) for c,v in zip(chunks,vectors)]
        if points: self.client.upsert(collection_name=self.collection, points=points, wait=True)

    def search(
        self,
        vector: list[float],
        limit: int = 10,
        repo_name: str | None = None,
        language: str | None = None,
        section: str | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_collection()
        flt = None
        must = []
        if repo_name:
            must.append(qm.FieldCondition(key='repo', match=qm.MatchValue(value=repo_name)))
        if language:
            must.append(qm.FieldCondition(key='language', match=qm.MatchValue(value=language)))
        if section:
            must.append(qm.FieldCondition(key='section_hierarchy', match=qm.MatchValue(value=section)))
        if must:
            flt = qm.Filter(must=must)
        hits = self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            limit=limit,
            query_filter=flt,
            with_payload=True,
        )
        return [{'id': str(hit.id), 'score': float(hit.score), 'payload': hit.payload or {}, 'source': 'dense'} for hit in hits]

    def get(self, chunk_id: str) -> dict[str, Any] | None:
        pts=self.client.retrieve(self.collection, ids=[chunk_id], with_payload=True)
        return pts[0].payload if pts else None

    def delete(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        self.ensure_collection()
        self.client.delete(collection_name=self.collection, points_selector=qm.PointIdsList(points=chunk_ids), wait=True)

    def collections(self) -> list[str]:
        return [c.name for c in self.client.get_collections().collections]
