from core.chunking.semantic import SemanticChunker
from core.metadata.enricher import MetadataEnricher
from core.models import ParsedDocument, ParsedSection


def test_chunking_preserves_hierarchy_and_code_blocks():
    doc = ParsedDocument(
        repo_name='repo',
        path='README.md',
        language='markdown',
        text='# Architecture\nintro\n\n```python\nprint(1)\n```\n\n' + ('word ' * 900),
        headings=['Architecture'],
        sections=[
            ParsedSection(
                title='Architecture',
                level=1,
                kind='architecture',
                content='# Architecture\nintro\n\n```python\nprint(1)\n```\n\n' + ('word ' * 900),
                hierarchy=['Architecture'],
            )
        ],
    )
    doc = MetadataEnricher().enrich(doc)
    chunks = SemanticChunker(max_tokens=300, overlap=120).chunk(doc)
    assert chunks
    assert chunks[0].chunk_type.value == 'architecture'
    assert chunks[0].section_hierarchy == ['Architecture']
    assert any('```python' in chunk.text for chunk in chunks)
