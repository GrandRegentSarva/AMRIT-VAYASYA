from __future__ import annotations

from fastmcp import FastMCP

from apps.ingestion.service import IngestionService
from core.retrieval.hybrid import HybridRetriever

mcp = FastMCP('docs-mcp')
ingestion = IngestionService()
retriever = HybridRetriever(vector_store=ingestion.store, embedder=ingestion.embedder)


def _ok(data: dict) -> dict:
    return {'ok': True, **data}


def _error(code: str, detail: str) -> dict:
    return {'ok': False, 'error': {'code': code, 'detail': detail}}


@mcp.tool()
async def search_docs(
    query: str,
    repo_name: str | None = None,
    limit: int = 10,
    language: str | None = None,
    section: str | None = None,
):
    """Hybrid semantic+keyword search over indexed documentation chunks."""
    try:
        results = await retriever.search(query, limit, repo_name, 'hybrid', language, section)
    except Exception as exc:
        return _error('search_failed', str(exc))
    if repo_name and not results:
        return _error('repo_not_found_or_empty', f'No indexed chunks found for repo {repo_name}')
    return _ok({
        'query': query,
        'repo_name': repo_name,
        'language': language,
        'section': section,
        'results': [result.model_dump(mode='json') for result in results],
    })


@mcp.tool()
async def explain_doc_section(path: str, heading: str, repo_name: str | None = None):
    """Return a concise extractive explanation and related context for a doc section."""
    try:
        results = await retriever.search(f'{path} {heading}', 8, repo_name, 'hybrid', section=heading, heading=heading)
    except Exception as exc:
        return _error('explain_failed', str(exc))
    if not results:
        return _error('section_not_found', f'No content found for heading {heading} in {path}')
    focused = [
        result for result in results
        if result.metadata.get('path') == path and heading.lower() in ' '.join(result.metadata.get('section_hierarchy', [])).lower()
    ]
    chosen = focused or results[:3]
    explanation = '\n\n'.join(chunk.text[:1200] for chunk in chosen)
    return _ok({
        'path': path,
        'heading': heading,
        'repo_name': repo_name,
        'summary': explanation,
        'ranked_chunks': [result.model_dump(mode='json') for result in chosen],
        'related_chunks': [result.model_dump(mode='json') for result in results],
    })


@mcp.tool()
async def retrieve_related_chunks(chunk_id: str, limit: int = 5):
    """Return chunks semantically adjacent to an existing chunk."""
    try:
        results = await retriever.related(chunk_id, limit)
    except Exception as exc:
        return _error('related_lookup_failed', str(exc))
    if not results:
        return _error('chunk_not_found', f'No related chunks found for {chunk_id}')
    return _ok({
        'chunk_id': chunk_id,
        'results': [result.model_dump(mode='json') for result in results],
    })


@mcp.tool()
async def summarize_repository_docs(repo_name: str):
    """Produce an extractive architecture overview from README/architecture/module chunks."""
    try:
        results = await retriever.search(
            'README architecture overview major modules important files configuration setup',
            10,
            repo_name,
            'hybrid',
        )
    except Exception as exc:
        return _error('summary_failed', str(exc))
    if not results:
        return _error('repo_not_found_or_empty', f'No indexed documentation found for repo {repo_name}')
    overview = '\n\n'.join(result.text[:900] for result in results[:5])
    files = sorted({result.metadata.get('path') for result in results if result.metadata.get('path')})
    modules = sorted({symbol for result in results for symbol in result.metadata.get('symbols', [])})[:50]
    frameworks = sorted({result.metadata.get('framework_type') for result in results if result.metadata.get('framework_type')})
    return _ok({
        'repo_name': repo_name,
        'architecture_overview': overview,
        'major_modules': modules,
        'important_files': files,
        'frameworks': frameworks,
        'ranked_chunks': [result.model_dump(mode='json') for result in results],
    })


if __name__ == '__main__':
    mcp.run()
