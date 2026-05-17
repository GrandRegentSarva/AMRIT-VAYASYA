from __future__ import annotations

from fastapi import FastAPI, HTTPException, status

from integrations.jira_client import get_ticket, list_tickets
from integrations.plan_generator import generate_implementation_plan

app = FastAPI(title='Jira MCP API', version='0.1.0')


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok', 'service': 'jira-mcp'}


@app.get('/tickets')
async def list_jira_tickets() -> dict:
    """List all available Jira tickets."""
    return {'tickets': list_tickets()}


@app.get('/ticket/{issue_key}')
async def get_jira_ticket(issue_key: str) -> dict:
    """Fetch a single Jira ticket by key."""
    try:
        return get_ticket(issue_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.get('/plan/{issue_key}')
async def get_implementation_plan(issue_key: str) -> dict:
    """
    Generate a graph-grounded implementation plan for a Jira ticket.
    Calls the cross-repo service for architecture evidence.
    """
    try:
        plan_text = generate_implementation_plan(issue_key)
        return {'issue_key': issue_key, 'plan': plan_text}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@app.post('/plan/{issue_key}/publish')
async def publish_implementation_plan(issue_key: str) -> dict:
    """
    Generate a graph-grounded implementation plan and publish it as a comment on the Jira ticket.
    """
    from integrations.jira_client import post_comment
    try:
        plan_text = generate_implementation_plan(issue_key)
        success, msg = post_comment(issue_key, plan_text)
        if not success:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Jira API Error: {msg}")
        return {'issue_key': issue_key, 'status': 'published'}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


if __name__ == '__main__':
    import uvicorn
    from config import get_settings
    uvicorn.run('api:app', host='0.0.0.0', port=get_settings().jira_mcp_port, reload=True)
