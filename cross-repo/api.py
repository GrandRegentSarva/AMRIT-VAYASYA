from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query, status

from core.evidence_collector import EvidenceCollector
from core.graph_builder import GraphBuilder
from core.neo4j_client import Neo4jClient

app = FastAPI(title='Cross-Repo API', version='0.1.0')


def _get_neo4j() -> Neo4jClient:
    return Neo4jClient()


@app.get('/health')
async def health() -> dict:
    try:
        neo4j = _get_neo4j()
        stats = neo4j.stats()
        neo4j.close()
        return {'status': 'ok', 'graph_stats': stats}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@app.post('/build-graph')
async def build_graph() -> dict:
    """Trigger a full graph rebuild from all Qdrant indexed data."""
    builder = GraphBuilder()
    try:
        stats = builder.build()
        return {'status': 'ok', 'stats': stats}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    finally:
        builder.close()


@app.get('/endpoints')
async def list_endpoints(repo_name: str | None = Query(default=None)) -> dict:
    """List all discovered API endpoints and their frontend→backend mappings."""
    neo4j = _get_neo4j()
    try:
        results = neo4j.query_all_endpoints(repo_name)
        return {'repo_name': repo_name, 'count': len(results), 'endpoints': results}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    finally:
        neo4j.close()


@app.get('/trace')
async def trace_feature(
    feature: str = Query(..., description='Plain-English feature name to trace (e.g. beneficiary registration)'),
) -> dict:
    """Trace the full frontend→backend service chain for a feature."""
    neo4j = _get_neo4j()
    try:
        results = neo4j.query_trace(feature)
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'No endpoints found matching feature: {feature}',
            )
        return {'feature': feature, 'count': len(results), 'traces': results}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    finally:
        neo4j.close()


@app.get('/dependencies/{class_name}')
async def get_dependencies(
    class_name: str,
    repo_name: str | None = Query(default=None),
) -> dict:
    """Return the dependency chain for a given class."""
    neo4j = _get_neo4j()
    try:
        results = neo4j.query_dependencies(class_name, repo_name)
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Class not found: {class_name}',
            )
        return {'class_name': class_name, 'results': results}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    finally:
        neo4j.close()



@app.get('/explain')
async def explain_feature(
    feature: str = Query(..., description='Plain-English feature name to explain'),
) -> dict:
    """
    Run deterministic traversal and return structured TraversalEvidence.
    This is the data contract the Explainer Skill and the LLM use.
    """
    collector = EvidenceCollector()
    try:
        ev = collector.collect(feature)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    finally:
        collector.close()

    if ev.is_empty():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'No evidence found for feature: {feature}',
        )

    return {
        'feature': ev.feature,
        'confidence': ev.confidence,
        'summary': ev.summary(),
        'backend_endpoints': [
            {
                'method': ep.method,
                'path': ep.path,
                'normalized_path': ep.normalized_path,
                'handler_class': ep.handler_class,
                'handler_kind': ep.handler_kind,
                'repo': ep.repo,
                'backend_file': ep.backend_file,
                'api_contract': {
                    'request_dto': ep.api_contract.request_dto,
                    'response_dto': ep.api_contract.response_dto,
                    'path_params': ep.api_contract.path_params,
                } if ep.api_contract else None,
            }
            for ep in ev.backend_endpoints
        ],
        'service_chain': ev.service_chain,
        'frontend_components': [
            {
                'class_name': fc.class_name,
                'repo': fc.repo,
                'file_path': fc.file_path,
                'http_method': fc.http_method,
                'called_path': fc.called_path,
                'evidence': {
                    'matched_via': fc.evidence.matched_via,
                    'confidence': fc.evidence.confidence,
                    'source_file': fc.evidence.source_file,
                },
            }
            for fc in ev.frontend_components
        ],
        'unresolved_hops': [
            {'name': h.name, 'type': h.hop_type, 'context': h.context}
            for h in ev.unresolved_hops
        ],
        'provenance': ev.provenance,
    }


if __name__ == '__main__':
    import uvicorn
    from config import get_settings
    uvicorn.run('api:app', host='0.0.0.0', port=get_settings().cross_repo_port, reload=True)
