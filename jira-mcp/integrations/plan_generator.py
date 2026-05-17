"""
Jira Implementation Plan Generator
-------------------------------------
Graph-grounded change planning from a Jira ticket.

This module is part of the jira-mcp service (Section D).
It calls the cross-repo service (Section B/C) via HTTP for graph intelligence.
The two services are fully decoupled — this module has NO direct imports
from cross-repo.

Flow:
    Ticket
    -> Intent extraction  (feature keyword from ticket summary/description)
    -> cross-repo /explain API (deterministic graph traversal, returns TraversalEvidence)
    -> Impact analysis    (downstream dependencies from evidence)
    -> Code retrieval     (included in evidence)
    -> Structured implementation plan
"""
from __future__ import annotations

import os
import textwrap
import urllib.request
import urllib.error
import json
from typing import Any

from integrations.jira_client import get_ticket

CROSS_REPO_URL = os.environ.get('CROSS_REPO_URL', 'http://localhost:8001')


def _call_cross_repo_explain(feature: str) -> dict[str, Any] | None:
    """
    Call the cross-repo /explain endpoint to get deterministic TraversalEvidence.
    Returns parsed JSON or None if the service is unavailable.
    """
    url = f'{CROSS_REPO_URL}/explain?feature={urllib.request.quote(feature)}'
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    except Exception as exc:
        raise RuntimeError(
            f'Could not reach cross-repo service at {CROSS_REPO_URL}. '
            f'Make sure it is running: uvicorn api:app --port 8001\n'
            f'Error: {exc}'
        )


def _extract_feature_keywords(ticket: dict[str, Any]) -> list[str]:
    """
    Extract feature keywords from a ticket to drive traversal.
    Uses the explicit 'affected_feature' field first, then significant
    words from the summary as fallback.
    """
    keywords: list[str] = []
    if ticket.get('affected_feature'):
        keywords.append(ticket['affected_feature'])

    stop_words = {
        'add', 'fix', 'modify', 'update', 'change', 'the', 'a', 'an',
        'to', 'in', 'for', 'of', 'and', 'or', 'after', 'before',
    }
    for word in ticket.get('summary', '').lower().split():
        if len(word) > 4 and word not in stop_words:
            keywords.append(word)

    seen: set[str] = set()
    result: list[str] = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            result.append(k)
    return result[:3]


def _render_plan(ticket: dict[str, Any], evidence: dict[str, Any] | None) -> str:
    lines: list[str] = []
    bar = '=' * 65

    lines.append(f'\n{bar}')
    lines.append('GRAPH-GROUNDED IMPLEMENTATION PLAN')
    lines.append(bar)
    lines.append(f'Ticket      : {ticket["key"]} ({ticket.get("ticket_type", "").upper()})')
    lines.append(f'Summary     : {ticket["summary"]}')
    lines.append(f'Status      : {ticket.get("status")}')
    lines.append(f'Priority    : {ticket.get("priority")}')

    if evidence:
        lines.append(
            f'Traversal   : "{evidence.get("feature")}"  '
            f'(confidence {evidence.get("confidence", 0):.0%})'
        )
    lines.append(bar)

    lines.append('\nDESCRIPTION:')
    lines.append(
        textwrap.fill(
            ticket.get('description', ''),
            width=70,
            initial_indent='  ',
            subsequent_indent='  ',
        )
    )

    if not evidence:
        lines.append('\n[!] cross-repo service returned no evidence for this ticket.')
        lines.append('    Start the cross-repo service and rebuild the graph first.')
        return '\n'.join(lines)

    endpoints = evidence.get('backend_endpoints', [])
    service_chain = evidence.get('service_chain', [])
    frontend_components = evidence.get('frontend_components', [])
    unresolved_hops = evidence.get('unresolved_hops', [])
    provenance = evidence.get('provenance', [])

    # ------ Affected Components ------
    lines.append('\n' + '-' * 65)
    lines.append('AFFECTED COMPONENTS  (derived from knowledge graph)')
    lines.append('-' * 65)

    if endpoints:
        lines.append('\nEndpoints:')
        for ep in endpoints:
            lines.append(f'  {ep["method"]:6} {ep["path"]}')
            lines.append(f'          Norm path : {ep.get("normalized_path", "")}')
            lines.append(f'          Handler   : {ep["handler_class"]}  [{ep["handler_kind"]}]')
            lines.append(f'          Repo      : {ep["repo"]}')
            ct = ep.get('api_contract') or {}
            if ct.get('path_params'):
                lines.append(f'          Path params: {", ".join(ct["path_params"])}')
            if ct.get('request_dto'):
                lines.append(f'          Request DTO: {ct["request_dto"]}')
            if ct.get('response_dto'):
                lines.append(f'          Response DTO: {ct["response_dto"]}')
    else:
        lines.append('\nEndpoints: (none resolved — rebuild the graph)')

    if service_chain:
        lines.append('\nService Chain:')
        lines.append('  ' + ' -> '.join(service_chain))

    if frontend_components:
        lines.append('\nFrontend Callers:')
        for fc in frontend_components:
            lines.append(f'  {fc["class_name"]}  ({fc["repo"]})')
            lines.append(f'    File     : {fc["file_path"]}')
            lines.append(f'    Calls    : {fc["http_method"]} {fc["called_path"]}')
            ev = fc.get('evidence', {})
            lines.append(
                f'    Evidence : matched via {ev.get("matched_via")}  '
                f'(confidence {ev.get("confidence", 0):.0%})'
            )

    # ------ Suggested Files ------
    lines.append('\n' + '-' * 65)
    lines.append('SUGGESTED FILES TO MODIFY  (evidence-grounded)')
    lines.append('-' * 65)

    seen_files: set[str] = set()
    for ep in endpoints:
        f = ep.get('backend_file', '')
        if f and f not in seen_files:
            seen_files.add(f)
            lines.append(f'  [{ep["repo"]}]  {f}')

    if not seen_files:
        lines.append('  (No files resolved — check ingestion and graph build)')

    # ------ Potential Impact ------
    lines.append('\n' + '-' * 65)
    lines.append('POTENTIAL IMPACT  (downstream / external boundaries)')
    lines.append('-' * 65)

    if unresolved_hops:
        lines.append('')
        for hop in unresolved_hops:
            lines.append(f'  [{hop["type"].upper()}] {hop["name"]}')
            lines.append(f'    {hop["context"]}')
        lines.append('\n  Action required: verify compatibility with the above boundaries.')
    else:
        lines.append('\n  No external boundaries detected for this feature.')

    # ------ Checklist ------
    lines.append('\n' + '-' * 65)
    lines.append('IMPLEMENTATION CHECKLIST')
    lines.append('-' * 65)

    ticket_type = ticket.get('ticket_type', 'feature')
    lines.append('')
    if ticket_type == 'bug':
        lines.append('  [ ] Reproduce using the identified endpoint')
        lines.append('  [ ] Add a failing test capturing the bug')
        lines.append('  [ ] Patch the identified handler class')
        lines.append('  [ ] Verify fix does not break the service chain')
        lines.append('  [ ] Update integration tests')
    else:
        lines.append('  [ ] Review API contract (request/response DTOs above)')
        lines.append('  [ ] Implement business logic in the service layer (see service chain)')
        lines.append('  [ ] Add or update the endpoint handler')
        lines.append('  [ ] Verify impact on external boundaries (see above)')
        lines.append('  [ ] Write unit tests for new service methods')
        lines.append('  [ ] Update integration/API tests')
        if frontend_components:
            lines.append('  [ ] Update frontend component to handle new response shape')

    # ------ Provenance ------
    lines.append('\n' + '-' * 65)
    lines.append('GRAPH PROVENANCE  (how this plan was derived)')
    lines.append('-' * 65)
    for i, step in enumerate(provenance, 1):
        lines.append(f'  {i:2}. {step}')

    lines.append(f'\n{bar}')
    return '\n'.join(lines)


def generate_implementation_plan(issue_key: str) -> str:
    """
    Fetch the ticket and generate a graph-grounded implementation plan.
    Calls the cross-repo service at CROSS_REPO_URL for graph intelligence.
    """
    ticket = get_ticket(issue_key)
    keywords = _extract_feature_keywords(ticket)
    primary_keyword = keywords[0] if keywords else ticket.get('key', '').lower()

    evidence = _call_cross_repo_explain(primary_keyword)
    return _render_plan(ticket, evidence)
