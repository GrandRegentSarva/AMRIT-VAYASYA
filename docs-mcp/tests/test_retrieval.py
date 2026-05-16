import pytest

from core.models import DocumentChunk
from core.retrieval.bm25 import BM25Index
from core.retrieval.hybrid import HybridRetriever


class DummyEmbedder:
    async def embed_query(self, text: str):
        return [0.1, 0.2]


class DummyVectorStore:
    def search(self, vector, limit=10, repo_name=None, language=None, section=None):
        return [
            {
                'id': 'arch',
                'score': 0.9,
                'source': 'dense',
                'payload': {
                    'repo': 'repo',
                    'path': 'README.md',
                    'section': 'Architecture',
                    'section_hierarchy': ['Architecture'],
                    'chunk_type': 'architecture',
                    'framework_type': 'fastapi',
                    'text': 'Architecture overview',
                    'language': 'markdown',
                },
            }
        ]

    def get(self, chunk_id: str):
        return {
            'repo': 'repo',
            'path': 'README.md',
            'section': 'Architecture',
            'text': 'Architecture overview',
            'language': 'markdown',
        }


class DummyReranker:
    def rerank(self, query: str, candidates: list[dict], limit: int = 10):
        for candidate in candidates:
            candidate['rerank_score'] = candidate['score'] + candidate['normalized_score']
        return sorted(candidates, key=lambda item: item['rerank_score'], reverse=True)[:limit]


@pytest.mark.asyncio
async def test_hybrid_retrieval_applies_filters_and_scores():
    original_state = bm25_state()
    try:
        chunk = DocumentChunk(
            id='keyword',
            repo='repo',
            path='guide.md',
            language='markdown',
            section='Setup',
            section_hierarchy=['Setup'],
            text='setup guide for qdrant',
            token_count=4,
            source_hash='hash',
        )
        index = BM25Index()
        index.add([chunk])
        from core.retrieval import hybrid as hybrid_module
        hybrid_module.bm25_index = index
        retriever = HybridRetriever(embedder=DummyEmbedder(), vector_store=DummyVectorStore(), reranker=DummyReranker())
        results = await retriever.search('architecture', repo_name='repo', language='markdown')
        assert results
        assert results[0].metadata['path'] == 'README.md'
        assert results[0].confidence in {'high', 'medium'}
    finally:
        restore_bm25(original_state)


def bm25_state():
    from core.retrieval import hybrid as hybrid_module
    return hybrid_module.bm25_index


def restore_bm25(state):
    from core.retrieval import hybrid as hybrid_module
    hybrid_module.bm25_index = state
