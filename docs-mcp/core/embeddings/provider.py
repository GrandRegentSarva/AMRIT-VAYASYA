from __future__ import annotations
import asyncio, hashlib, math
from core.config import get_settings

class EmbeddingProvider:
    """BGE embedding provider. Falls back to deterministic hashing when model is unavailable."""
    def __init__(self, model_name: str | None=None, dim: int | None=None):
        s=get_settings(); self.model_name=model_name or (s.lightweight_embedding_model if s.use_lightweight_embeddings else s.embedding_model); self.dim=dim or s.embedding_dim; self._model=None; self._failed=False

    def _load(self):
        if self._model or self._failed: return self._model
        try:
            from sentence_transformers import SentenceTransformer
            self._model=SentenceTransformer(self.model_name, trust_remote_code=True)
        except Exception:
            self._failed=True
        return self._model

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self.embed_documents_sync, texts)

    def embed_documents_sync(self, texts: list[str]) -> list[list[float]]:
        model=self._load()
        if model:
            vectors=model.encode(texts, batch_size=get_settings().batch_size, normalize_embeddings=True).tolist()
            return [self._fit_dim(v) for v in vectors]
        return [self._hash_embed(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_documents([text]))[0]

    def embed_query_sync(self, text: str) -> list[float]:
        return self.embed_documents_sync([text])[0]

    def _fit_dim(self, v):
        if len(v)==self.dim: return v
        return (v + [0.0]*self.dim)[:self.dim]

    def _hash_embed(self, text: str) -> list[float]:
        vec=[0.0]*self.dim
        for tok in text.lower().split():
            h=int(hashlib.md5(tok.encode()).hexdigest(),16); vec[h%self.dim]+=1.0 if (h>>8)&1 else -1.0
        norm=math.sqrt(sum(x*x for x in vec)) or 1.0
        return [x/norm for x in vec]
