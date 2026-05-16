from __future__ import annotations
import re

def toks(s): return set(re.findall(r'[a-zA-Z0-9_]+', s.lower()))

class Reranker:
    def __init__(self, model_name: str | None=None): self.model_name=model_name; self._model=None; self._failed=False
    def _load(self):
        if self._model or self._failed: return self._model
        try:
            from sentence_transformers import CrossEncoder
            from core.config import get_settings
            self._model=CrossEncoder(self.model_name or get_settings().reranker_model)
        except Exception: self._failed=True
        return self._model
    def rerank(self, query: str, candidates: list[dict], limit: int=10) -> list[dict]:
        if not candidates: return []
        model=self._load()
        if model:
            texts=[c.get('payload',{}).get('text','') for c in candidates]
            scores=model.predict([[query,t] for t in texts]).tolist()
        else:
            qt=toks(query); scores=[len(qt & toks(c.get('payload',{}).get('text',''))) + c.get('score',0)*0.05 for c in candidates]
        for c,s in zip(candidates,scores):
            c['rerank_score']=float(s) + self._metadata_boost(query, c.get('payload', {}))
        return sorted(candidates, key=lambda c:c.get('rerank_score',0), reverse=True)[:limit]

    def _metadata_boost(self, query: str, payload: dict) -> float:
        query_tokens = toks(query)
        headings = toks(' '.join(payload.get('heading_hierarchy', [])))
        symbols = toks(' '.join(payload.get('symbols', [])))
        section_tokens = toks(payload.get('section') or '')
        boost = 0.0
        if query_tokens & headings:
            boost += 0.4
        if query_tokens & section_tokens:
            boost += 0.3
        if query_tokens & symbols:
            boost += 0.2
        if payload.get('framework_type') and payload['framework_type'] in query.lower():
            boost += 0.2
        if payload.get('chunk_type') in {'architecture', 'config'}:
            boost += 0.1
        return boost
