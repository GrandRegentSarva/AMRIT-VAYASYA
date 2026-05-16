from __future__ import annotations

from fastmcp import FastMCP

from core.graph_builder import GraphBuilder
from core.neo4j_client import Neo4jClient

mcp = FastMCP('cross-repo')


def _neo4j() -> Neo4jClient:
    return Neo4jClient()


@mcp.tool()
async def trace_api_flow(feature: str, repo_name: str | None = None) -> dict:
    """
    Trace the full frontend→backend service chain for a plain-English feature description.

    Example: trace_api_flow("beneficiary registration") will find which Angular component
    calls which backend endpoint and trace the full Spring Boot service chain.
    """
    neo4j = _neo4j()
    try:
        results = neo4j.query_trace(feature)
        if not results:
            return {'ok': False, 'error': f'No endpoints found matching: {feature}'}
        return {'ok': True, 'feature': feature, 'traces': results}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}
    finally:
        neo4j.close()


@mcp.tool()
async def list_endpoints(repo_name: str | None = None) -> dict:
    """List all discovered API endpoints and their frontend→backend mappings across all ingested repos."""
    neo4j = _neo4j()
    try:
        results = neo4j.query_all_endpoints(repo_name)
        return {'ok': True, 'repo_name': repo_name, 'count': len(results), 'endpoints': results}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}
    finally:
        neo4j.close()


@mcp.tool()
async def find_dependencies(class_name: str, repo_name: str | None = None) -> dict:
    """
    Return the full dependency chain for a given class.

    Example: find_dependencies("BeneficiaryController") returns all services and repositories
    it depends on, up to 5 hops deep.
    """
    neo4j = _neo4j()
    try:
        results = neo4j.query_dependencies(class_name, repo_name)
        if not results:
            return {'ok': False, 'error': f'Class not found: {class_name}'}
        return {'ok': True, 'class_name': class_name, 'results': results}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}
    finally:
        neo4j.close()


@mcp.tool()
async def rebuild_graph() -> dict:
    """Trigger a full rebuild of the cross-repo service dependency graph from all Qdrant data."""
    builder = GraphBuilder()
    try:
        stats = builder.build()
        return {'ok': True, 'stats': stats}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}
    finally:
        builder.close()


if __name__ == '__main__':
    mcp.run()
