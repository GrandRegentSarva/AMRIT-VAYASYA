from core.reranking.reranker import Reranker


def test_reranker_metadata_boost_prioritizes_matching_sections():
    reranker = Reranker()
    reranker._failed = True
    candidates = [
        {
            'id': 'a',
            'score': 1.0,
            'payload': {
                'text': 'architecture overview',
                'section': 'Architecture',
                'heading_hierarchy': ['Architecture'],
                'symbols': ['Service'],
                'chunk_type': 'architecture',
            },
        },
        {
            'id': 'b',
            'score': 1.0,
            'payload': {
                'text': 'random notes',
                'section': 'Misc',
                'heading_hierarchy': ['Misc'],
                'symbols': [],
                'chunk_type': 'mixed',
            },
        },
    ]
    ranked = reranker.rerank('architecture', candidates, limit=2)
    assert ranked[0]['id'] == 'a'
