from __future__ import annotations

from fastmcp import FastMCP

from integrations.jira_client import get_ticket, list_tickets
from integrations.plan_generator import generate_implementation_plan

mcp = FastMCP('jira-mcp')


@mcp.tool()
async def list_jira_tickets() -> dict:
    """List all available Jira tickets and their current status."""
    try:
        return {'ok': True, 'tickets': list_tickets()}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


@mcp.tool()
async def get_jira_ticket(issue_key: str) -> dict:
    """Fetch the full details of a specific Jira ticket by key (e.g. AMRIT-101)."""
    try:
        return {'ok': True, 'ticket': get_ticket(issue_key)}
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}


@mcp.tool()
async def create_implementation_plan(issue_key: str) -> dict:
    """
    Generate a graph-grounded implementation plan for a Jira ticket.

    Flow:
      Ticket -> Intent Extraction -> Feature Resolution (via cross-repo)
      -> Traversal Expansion -> Impact Analysis
      -> Code Retrieval -> Structured Implementation Plan

    Every affected file and component is derived from the Neo4j knowledge graph.
    This is NOT generic AI coding advice.

    Requires:
      - cross-repo service running at CROSS_REPO_URL (default: http://localhost:8001)
      - Graph already built via POST /build-graph on cross-repo
    """
    try:
        plan = generate_implementation_plan(issue_key)
        return {'ok': True, 'issue_key': issue_key, 'plan': plan}
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    except RuntimeError as exc:
        return {'ok': False, 'error': str(exc)}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


@mcp.tool()
async def publish_implementation_plan(issue_key: str) -> dict:
    """
    Generate a graph-grounded implementation plan and publish it as a comment on the Jira ticket.
    """
    from integrations.jira_client import post_comment
    try:
        plan = generate_implementation_plan(issue_key)
        success, msg = post_comment(issue_key, plan)
        if not success:
            return {'ok': False, 'error': f"Jira API Error: {msg}"}
        return {'ok': True, 'issue_key': issue_key, 'status': 'published'}
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    except RuntimeError as exc:
        return {'ok': False, 'error': str(exc)}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


if __name__ == '__main__':
    mcp.run()
