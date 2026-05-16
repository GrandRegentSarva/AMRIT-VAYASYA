from __future__ import annotations
import re
from rank_bm25 import BM25Okapi
from core.models import DocumentChunk

def tokenize(text: str) -> list[str]: return re.findall(r'[a-zA-Z0-9_]+', text.lower())

class BM25Index:
    def __init__(self):
        self.chunk_map: dict[str, DocumentChunk] = {}
        self.chunks: list[DocumentChunk] = []
        self._bm25 = None

    def add(self, chunks: list[DocumentChunk]):
        for chunk in chunks:
            self.chunk_map[chunk.id] = chunk
        self._rebuild()

    def remove(self, chunk_ids: list[str]) -> None:
        for chunk_id in chunk_ids:
            self.chunk_map.pop(chunk_id, None)
        self._rebuild()

    def search(
        self,
        query: str,
        limit: int = 20,
        repo_name: str | None = None,
        language: str | None = None,
        section: str | None = None,
    ):
        if not self._bm25:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        out = []
        for index, score in ranked:
            chunk = self.chunks[index]
            if repo_name and chunk.repo != repo_name:
                continue
            if language and chunk.language != language:
                continue
            if section and section.lower() not in ' '.join(chunk.section_hierarchy).lower():
                continue
            out.append({'id': chunk.id, 'score': float(score), 'payload': chunk.payload(), 'source': 'bm25'})
            if len(out) >= limit:
                break
        return out

    def _rebuild(self) -> None:
        self.chunks = list(self.chunk_map.values())
        self._bm25 = BM25Okapi([tokenize(chunk.text) for chunk in self.chunks]) if self.chunks else None

bm25_index = BM25Index()
