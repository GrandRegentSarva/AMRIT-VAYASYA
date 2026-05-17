"""
Jira Implementation Plan Generator
------------------------------------
Graph-grounded change planning from a Jira ticket.

Flow:
    Ticket
    -> Intent extraction (feature keyword from ticket summary/description)
    -> EvidenceCollector (deterministic graph traversal)
    -> Impact analysis (downstream dependencies)
    -> Code retrieval (Qdrant)
    -> Structured implementation plan

This is NOT generic AI coding advice.
Every affected file and component is derived from the knowledge graph.
"""
from __future__ import annotations

import os
import sys
import textwrap
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.evidence import TraversalEvidence, UnresolvedHop
from core.evidence_collector import EvidenceCollector
from integrations.jira_client import get_ticket


def _extract_feature_keywords(ticket: dict[str, Any]) -> list[str]:
    """
    Extract feature keywords from a ticket to drive traversal.
    Uses the explicit 'affected_feature' field if present, then
    falls back to extracting nouns from the summary.
    """
    keywords: list[str] = []
    if ticket.get('affected_feature'):
        keywords.append(ticket['affected_feature'])

    # Also extract significant words from the summary
    summary_words = ticket.get('summary', '').lower().split()
    stop_words = {'add', 'fix', 'modify', 'update', 'change', 'the', 'a', 'an',
                  'to', 'in', 'for', 'of', 'and', 'or', 'after', 'before'}
    keywords += [w for w in summary_words if len(w) > 4 and w not in stop_words]

    # Deduplicate preserving order
    seen: set[str] = set()
    result = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            result.append(k)
    return result[:3]  # cap at 3 keywords to keep traversal focused


def _render_plan(ticket: dict[str, Any], ev: TraversalEvidence) -> str:
    lines: list[str] = []
    bar = '=' * 65

    lines.append(f'\n{bar}')
    lines.append(f'GRAPH-GROUNDED IMPLEMENTATION PLAN')
    lines.append(f'{bar}')
    lines.append(f'Ticket      : {ticket["key"]} ({ticket.get("ticket_type", "").upper()})')
    lines.append(f'Summary     : {ticket["summary"]}')
    lines.append(f'Status      : {ticket.get("status")}')
    lines.append(f'Priority    : {ticket.get("priority")}')
    lines.append(f'Traversal   : "{ev.feature}"  (confidence {ev.confidence:.0%})')
    lines.append(bar)

    lines.append('\nDESCRIPTION:')
    lines.append(textwrap.fill(ticket.get('description', ''), width=70, initial_indent='  ', subsequent_indent='  '))

    lines.append('\n' + '-' * 65)
    lines.append('AFFECTED COMPONENTS  (derived from knowledge graph)')
    lines.append('-' * 65)

    if ev.backend_endpoints:
        lines.append('\nEndpoints:')
        for ep in ev.backend_endpoints:
            lines.append(f'  {ep.method:6} {ep.path}')
            lines.append(f'          Handler : {ep.handler_class}  [{ep.handler_kind}]')
            lines.append(f'          Repo    : {ep.repo}')
            if ep.api_contract:
                if ep.api_contract.request_dto:
                    lines.append(f'          Req DTO : {ep.api_contract.request_dto}')
                if ep.api_contract.response_dto:
                    lines.append(f'          Res DTO : {ep.api_contract.response_dto}')
    else:
        lines.append('\nEndpoints: (none resolved - check graph build)')

    if ev.service_chain:
        lines.append('\nService Chain:')
        lines.append('  ' + ' -> '.join(ev.service_chain))

    if ev.frontend_components:
        lines.append('\nFrontend Callers:')
        for fc in ev.frontend_components:
            lines.append(f'  {fc.class_name}  ({fc.repo})')
            lines.append(f'    File   : {fc.file_path}')
            lines.append(f'    Calls  : {fc.http_method} {fc.called_path}')

    lines.append('\n' + '-' * 65)
    lines.append('SUGGESTED FILES TO MODIFY  (evidence-grounded)')
    lines.append('-' * 65)

    seen_files: set[str] = set()
    for ep in ev.backend_endpoints:
        if ep.backend_file and ep.backend_file not in seen_files:
            seen_files.add(ep.backend_file)
            lines.append(f'  [{ep.repo}]  {ep.backend_file}')
    for chunk in ev.supporting_chunks:
        f = chunk.get('file', '')
        if f and f not in seen_files:
            seen_files.add(f)
            lines.append(f'  [{chunk.get("repo", "")}]  {f}')

    if not seen_files:
        lines.append('  (No files resolved — rebuild graph or check ingestion)')

    lines.append('\n' + '-' * 65)
    lines.append('POTENTIAL IMPACT  (downstream dependencies)')
    lines.append('-' * 65)

    if ev.unresolved_hops:
        lines.append('\nExternal / Unresolved boundaries:')
        for hop in ev.unresolved_hops:
            lines.append(f'  [{hop.hop_type.upper()}] {hop.name}')
            lines.append(f'    {hop.context}')
        lines.append('')
        lines.append('  Action required: verify that changes are compatible with the above boundaries.')
    else:
        lines.append('  No external system boundaries detected for this feature.')

    lines.append('\n' + '-' * 65)
    lines.append('IMPLEMENTATION CHECKLIST')
    lines.append('-' * 65)

    ticket_type = ticket.get('ticket_type', 'feature')
    lines.append('')

    if ticket_type == 'bug':
        lines.append('  [ ] Reproduce the issue locally using the identified endpoint')
        lines.append('  [ ] Add a failing test that captures the bug')
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
        if ev.frontend_components:
            lines.append('  [ ] Update frontend component to handle new response shape')

    lines.append('\n' + '-' * 65)
    lines.append('GRAPH PROVENANCE  (how this plan was derived)')
    lines.append('-' * 65)
    for i, step in enumerate(ev.provenance, 1):
        lines.append(f'  {i:2}. {step}')

    lines.append(f'\n{bar}')
    return '\n'.join(lines)


def generate_implementation_plan(issue_key: str) -> str:
    """
    Fetch the ticket and generate a graph-grounded implementation plan.
    Returns the plan as a formatted string.
    """
    ticket = get_ticket(issue_key)
    keywords = _extract_feature_keywords(ticket)

    # Use the primary keyword for traversal
    primary_keyword = keywords[0] if keywords else ticket.get('key', '').lower()

    collector = EvidenceCollector()
    try:
        ev = collector.collect(primary_keyword)
    finally:
        collector.close()

    return _render_plan(ticket, ev)
