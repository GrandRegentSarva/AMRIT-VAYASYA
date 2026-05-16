from __future__ import annotations

import json

from core.config import get_settings
from core.embeddings.provider import EmbeddingProvider
from core.models import QueryRequest, SearchResult
from core.qdrant.client import QdrantVectorStore
from core.reranking.reranker import Reranker
from core.retrieval.bm25 import bm25_index


class HybridRetriever:
    def __init__(self, embedder=None, vector_store=None, reranker=None):
        self.embedder = embedder or EmbeddingProvider()
        self.vector_store = vector_store or QdrantVectorStore()
        self.reranker = reranker or Reranker()
        self.settings = get_settings()
        self._redis = None
        try:
            import redis
            self._redis = redis.from_url(self.settings.redis_url, decode_responses=True)
        except Exception:
            self._redis = None

    async def search(
        self,
        query: str,
        limit: int = 10,
        repo_name: str | None = None,
        mode: str = 'hybrid',
        language: str | None = None,
        section: str | None = None,
        heading: str | None = None,
    ) -> list[SearchResult]:
        request = QueryRequest(
            query=query,
            repo_name=repo_name,
            limit=limit,
            mode=mode,
            language=language,
            section=section,
            heading=heading,
        )
        cache_key = self._cache_key(request)
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        candidates = []
        candidate_limit = min(
            max(request.limit * self.settings.retrieve_candidate_multiplier, 20),
            self.settings.max_retrieval_candidates,
        )
        if request.mode in {'hybrid', 'dense'}:
            vector = await self.embedder.embed_query(request.query)
            candidates.extend(self.vector_store.search(
                vector,
                limit=candidate_limit,
                repo_name=request.repo_name,
                language=request.language,
                section=request.section or request.heading,
            ))
        if request.mode in {'hybrid', 'keyword'}:
            candidates.extend(bm25_index.search(
                request.query,
                limit=candidate_limit,
                repo_name=request.repo_name,
                language=request.language,
                section=request.section or request.heading,
            ))

        merged = self._merge(candidates)
        reranked = self.reranker.rerank(request.query, merged, request.limit)
        results = [self._to_result(candidate) for candidate in reranked]
        self._store_cache(cache_key, results)
        return results

    async def related(self, chunk_id: str, limit: int = 5) -> list[SearchResult]:
        payload = self.vector_store.get(chunk_id)
        if not payload:
            return []
        return await self.search(
            payload.get('text', ''),
            limit=limit,
            repo_name=payload.get('repo'),
            mode='dense',
            language=payload.get('language'),
            section=payload.get('section'),
        )

    def _merge(self, candidates: list[dict]) -> list[dict]:
        dense_scores = [candidate['score'] for candidate in candidates if candidate.get('source') == 'dense']
        keyword_scores = [candidate['score'] for candidate in candidates if candidate.get('source') == 'bm25']
        dense_bounds = self._bounds(dense_scores)
        keyword_bounds = self._bounds(keyword_scores)
        by_id: dict[str, dict] = {}
        for candidate in candidates:
            chunk_id = candidate['id']
            payload = candidate.get('payload', {})
            bucket = by_id.setdefault(chunk_id, {
                'id': chunk_id,
                'score': 0.0,
                'normalized_score': 0.0,
                'payload': payload.copy(),
                'sources': set(),
            })
            source = candidate.get('source', 'unknown')
            normalized = self._normalize(
                candidate.get('score', 0.0),
                dense_bounds if source == 'dense' else keyword_bounds,
            )
            bucket['score'] += float(candidate.get('score', 0.0))
            bucket['normalized_score'] += normalized
            bucket['payload'].update(payload)
            bucket['sources'].add(source)
        merged = list(by_id.values())
        for candidate in merged:
            candidate['score'] += self._metadata_rank_bonus(candidate['payload'])
            candidate['normalized_score'] = min(1.0, candidate['normalized_score'])
        merged.sort(key=lambda item: (item['normalized_score'], item['score']), reverse=True)
        return merged

    def _to_result(self, candidate: dict) -> SearchResult:
        payload = candidate.get('payload', {})
        rerank_score = float(candidate.get('rerank_score', candidate.get('score', 0.0)))
        normalized_score = float(candidate.get('normalized_score', 0.0))
        return SearchResult(
            chunk_id=candidate['id'],
            score=rerank_score,
            normalized_score=normalized_score,
            rerank_score=rerank_score,
            confidence=self._confidence(normalized_score),
            text=payload.get('text', ''),
            metadata=payload,
            source=f"{payload.get('repo') or ''}:{payload.get('path')}#{payload.get('section') or ''}",
        )

    def _metadata_rank_bonus(self, payload: dict) -> float:
        bonus = 0.0
        if payload.get('chunk_type') == 'architecture':
            bonus += 0.15
        if payload.get('framework_type'):
            bonus += 0.05
        if payload.get('section_hierarchy'):
            bonus += 0.05
        return bonus

    def _cache_key(self, request: QueryRequest) -> str:
        data = request.model_dump(mode='json')
        return 'search:' + json.dumps(data, sort_keys=True)

    def _load_cache(self, cache_key: str) -> list[SearchResult] | None:
        if not self._redis:
            return None
        try:
            cached = self._redis.get(cache_key)
            if not cached:
                return None
            return [SearchResult(**item) for item in json.loads(cached)]
        except Exception:
            return None

    def _store_cache(self, cache_key: str, results: list[SearchResult]) -> None:
        if not self._redis:
            return
        try:
            self._redis.setex(
                cache_key,
                self.settings.query_cache_ttl_seconds,
                json.dumps([result.model_dump(mode='json') for result in results]),
            )
        except Exception:
            return

    def _normalize(self, score: float, bounds: tuple[float, float]) -> float:
        lower, upper = bounds
        if upper <= lower:
            return 1.0 if score > 0 else 0.0
        return max(0.0, min(1.0, (score - lower) / (upper - lower)))

    def _bounds(self, scores: list[float]) -> tuple[float, float]:
        if not scores:
            return (0.0, 0.0)
        return (min(scores), max(scores))

    def _confidence(self, normalized_score: float) -> str:
        if normalized_score >= 0.75:
            return 'high'
        if normalized_score >= 0.45:
            return 'medium'
        return 'low'
