from __future__ import annotations

from fastmcp import FastMCP

from core.evidence_collector import EvidenceCollector
from core.graph_builder import GraphBuilder
from core.neo4j_client import Neo4jClient
from integrations.jira_client import get_ticket, list_tickets
from integrations.plan_generator import generate_implementation_plan

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


@mcp.tool()
async def explain_architecture(feature: str) -> dict:
    """
    Deterministic traversal + evidence collection for a feature.

    Returns structured TraversalEvidence including:
    - Backend endpoints and handler classes
    - Service dependency chain
    - Frontend callers (if ingested)
    - API contracts (DTOs)
    - Unresolved external hops
    - Full provenance trail

    The LLM should narrate this evidence; it should NOT query the graph directly.
    """
    collector = EvidenceCollector()
    try:
        ev = collector.collect(feature)
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}
    finally:
        collector.close()

    if ev.is_empty():
        return {'ok': False, 'error': f'No evidence found for feature: {feature}'}

    return {
        'ok': True,
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
        'unresolved_hops': [
            {'name': h.name, 'type': h.hop_type, 'context': h.context}
            for h in ev.unresolved_hops
        ],
        'provenance': ev.provenance,
    }


@mcp.tool()
async def list_jira_tickets() -> dict:
    """List all available Jira tickets and their status."""
    try:
        return {'ok': True, 'tickets': list_tickets()}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


@mcp.tool()
async def get_jira_ticket(issue_key: str) -> dict:
    """Fetch the details of a specific Jira ticket."""
    try:
        return {'ok': True, 'ticket': get_ticket(issue_key)}
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}


@mcp.tool()
async def create_implementation_plan(issue_key: str) -> dict:
    """
    Generate a graph-grounded implementation plan for a Jira ticket.

    Flow:
      Ticket -> Intent Extraction -> Feature Resolution
      -> Traversal Expansion -> Impact Analysis
      -> Code Retrieval -> Implementation Plan

    The plan cites exact files, classes, and DTOs derived from the
    knowledge graph. This is NOT generic AI coding advice.
    """
    try:
        plan = generate_implementation_plan(issue_key)
        return {'ok': True, 'issue_key': issue_key, 'plan': plan}
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


if __name__ == '__main__':
    mcp.run()
