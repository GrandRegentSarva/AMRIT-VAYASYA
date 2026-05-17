"""
API Flow Explainer Skill
------------------------
CLI-first orchestration of the deterministic traversal pipeline.

Usage:
    python cross-repo/skills/api_flow_explainer.py "beneficiary registration"
    python cross-repo/skills/api_flow_explainer.py "healthID" --mode explain
    python cross-repo/skills/api_flow_explainer.py "patient" --mode deterministic

Modes:
    deterministic (default)
        Pure graph evidence. No LLM. Works offline.
        Shows every fact with its provenance.

    explain
        Same deterministic pipeline, then feeds assembled context to Groq.
        The LLM narrates only; it never touches the graph.

Architecture:
    feature query
    -> Neo4j traversal (EvidenceCollector)
    -> TraversalEvidence (grounded, citable)
    -> Context assembly (text formatting of evidence)
    -> [deterministic] print structured report
    -> [explain] Groq narrates the assembled context
    -> markdown output
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap

# Ensure the cross-repo root is on sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.evidence import TraversalEvidence
from core.evidence_collector import EvidenceCollector


# ---------------------------------------------------------------------------
# Report formatters
# ---------------------------------------------------------------------------

def _section(title: str) -> str:
    bar = '-' * 60
    return f'\n{bar}\n{title}\n{bar}'


def _render_deterministic(ev: TraversalEvidence) -> str:
    lines: list[str] = []

    lines.append(f'\nAPI FLOW EXPLAINER  --  DETERMINISTIC MODE')
    lines.append(f'Feature: {ev.feature}')
    lines.append(f'Confidence: {ev.confidence:.0%}')
    lines.append(f'Evidence steps: {len(ev.provenance)}')

    # ------ Frontend Callers ------
    lines.append(_section('FRONTEND CALLERS'))
    if ev.frontend_components:
        for fc in ev.frontend_components:
            lines.append(f'  Component : {fc.class_name}')
            lines.append(f'  Repo      : {fc.repo}')
            lines.append(f'  File      : {fc.file_path}')
            lines.append(f'  Calls     : {fc.http_method} {fc.called_path}')
            lines.append(f'  Norm path : {fc.normalized_path}')
            lines.append(f'  Matched   : {fc.evidence.matched_via}  (confidence {fc.evidence.confidence:.0%})')
            lines.append('')
    else:
        lines.append('  No frontend callers indexed.')
        lines.append('  (Ingest a frontend repository to populate this layer.)')

    # ------ Backend Endpoints ------
    lines.append(_section('BACKEND ENDPOINTS'))
    for ep in ev.backend_endpoints:
        lines.append(f'  Route     : {ep.method} {ep.path}')
        lines.append(f'  Norm path : {ep.normalized_path}')
        lines.append(f'  Repo      : {ep.repo}')
        lines.append(f'  Handler   : {ep.handler_class}  [{ep.handler_kind}]')
        lines.append(f'  File      : {ep.backend_file}')
        if ep.api_contract:
            ct = ep.api_contract
            if ct.path_params:
                lines.append(f'  Path params: {", ".join(ct.path_params)}')
            if ct.request_dto:
                lines.append(f'  Request DTO: {ct.request_dto}')
            if ct.response_dto:
                lines.append(f'  Response DTO: {ct.response_dto}')
        lines.append('')

    # ------ Service Chain ------
    lines.append(_section('SERVICE DEPENDENCY CHAIN'))
    if ev.service_chain:
        lines.append('  ' + ' -> '.join(ev.service_chain))
    else:
        lines.append('  No multi-hop service chain resolved.')

    # ------ Unresolved Hops ------
    lines.append(_section('UNRESOLVED / EXTERNAL HOPS'))
    if ev.unresolved_hops:
        for hop in ev.unresolved_hops:
            lines.append(f'  [{hop.hop_type.upper()}] {hop.name}')
            lines.append(f'    {hop.context}')
    else:
        lines.append('  All dependencies resolved within the ingested graph.')

    # ------ Supporting Code Chunks ------
    lines.append(_section('SUPPORTING CODE CHUNKS  (from Qdrant)'))
    if ev.supporting_chunks:
        for chunk in ev.supporting_chunks[:5]:  # cap for readability
            lines.append(f'  File: {chunk["file"]}  ({chunk["repo"]})')
            snippet = chunk.get('text', '')[:200].replace('\n', '\n    ')
            lines.append(f'    {snippet}')
            lines.append('')
    else:
        lines.append('  No code chunks retrieved.')

    # ------ Provenance ------
    lines.append(_section('PROVENANCE  (audit trail)'))
    for i, step in enumerate(ev.provenance, 1):
        lines.append(f'  {i:2}. {step}')

    return '\n'.join(lines)


def _build_llm_context(ev: TraversalEvidence) -> str:
    """
    Serialize TraversalEvidence into a structured text block for the LLM.
    The LLM receives ONLY this; it never queries Neo4j or Qdrant itself.
    """
    parts: list[str] = [
        f'You are an expert software architect explaining code to a developer.',
        f'Below is deterministic graph evidence extracted from AMRIT repositories.',
        f'Your task: synthesize this into a clear, structured architecture explanation.',
        f'Do NOT speculate. Cite only what is in the evidence.',
        f'',
        f'FEATURE QUERY: {ev.feature}',
        f'TRAVERSAL CONFIDENCE: {ev.confidence:.0%}',
        f'',
    ]

    if ev.frontend_components:
        parts.append('FRONTEND CALLERS:')
        for fc in ev.frontend_components:
            parts.append(
                f'  - {fc.class_name} in {fc.repo}/{fc.file_path} '
                f'calls {fc.http_method} {fc.called_path} '
                f'[matched as {fc.evidence.matched_via}]'
            )
        parts.append('')

    if ev.backend_endpoints:
        parts.append('BACKEND ENDPOINTS:')
        for ep in ev.backend_endpoints:
            parts.append(f'  - {ep.method} {ep.path}')
            parts.append(f'    Handler: {ep.handler_class} ({ep.handler_kind}) in {ep.repo}')
            parts.append(f'    File: {ep.backend_file}')
            if ep.api_contract and ep.api_contract.request_dto:
                parts.append(f'    Request DTO: {ep.api_contract.request_dto}')
        parts.append('')

    if ev.service_chain:
        parts.append(f'SERVICE DEPENDENCY CHAIN: {" -> ".join(ev.service_chain)}')
        parts.append('')

    if ev.unresolved_hops:
        parts.append('UNRESOLVED / EXTERNAL DEPENDENCIES:')
        for hop in ev.unresolved_hops:
            parts.append(f'  - [{hop.hop_type}] {hop.name}: {hop.context}')
        parts.append('')

    if ev.supporting_chunks:
        parts.append('RELEVANT SOURCE CODE:')
        for chunk in ev.supporting_chunks[:4]:
            parts.append(f'  --- {chunk["file"]} ---')
            parts.append(textwrap.indent(chunk.get('text', '')[:400], '  '))
        parts.append('')

    parts.append(
        'Based ONLY on the above evidence, write a clear architecture explanation '
        'covering: (1) what triggers this feature, (2) which backend endpoint handles it, '
        '(3) the service dependency chain, (4) any external system boundaries, '
        '(5) the data contracts involved. Use plain English suitable for a developer unfamiliar with the codebase.'
    )
    return '\n'.join(parts)


def _run_groq(context: str) -> str:
    try:
        import groq
    except ImportError:
        return '[Error] groq package not installed. Run: pip install groq'

    api_key = os.environ.get('GROQ_API_KEY') or ''
    if not api_key:
        return '[Error] GROQ_API_KEY not set in environment or cross-repo/.env'

    client = groq.Groq(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model='llama3-70b-8192',
            messages=[{'role': 'user', 'content': context}],
            temperature=0.2,
            max_tokens=1500,
        )
        return response.choices[0].message.content or ''
    except Exception as exc:
        return f'[Groq error] {exc}'


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='API Flow Explainer Skill. Trace any feature across repos.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent('''\
            Examples:
              python skills/api_flow_explainer.py "beneficiary registration"
              python skills/api_flow_explainer.py "healthID" --mode explain
              python skills/api_flow_explainer.py "patient" --mode deterministic --json
        '''),
    )
    parser.add_argument('feature', help='Plain-English feature name to trace')
    parser.add_argument(
        '--mode',
        choices=['deterministic', 'explain'],
        default='deterministic',
        help='deterministic: pure graph evidence (default). explain: Groq narrates the evidence.',
    )
    parser.add_argument(
        '--json',
        action='store_true',
        dest='as_json',
        help='Output the raw TraversalEvidence as JSON (only in deterministic mode)',
    )
    args = parser.parse_args()

    print(f'\nCollecting graph evidence for: "{args.feature}" ...', flush=True)

    collector = EvidenceCollector()
    try:
        ev = collector.collect(args.feature)
    finally:
        collector.close()

    if ev.is_empty():
        print(f'\nNo endpoints found matching "{args.feature}" in the knowledge graph.')
        print('Try: rebuild the graph first with  curl -X POST http://localhost:8001/build-graph')
        sys.exit(1)

    if args.as_json and args.mode == 'deterministic':
        # Emit raw evidence as JSON for programmatic consumption
        out = {
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
                        'request_dto': ep.api_contract.request_dto if ep.api_contract else None,
                        'response_dto': ep.api_contract.response_dto if ep.api_contract else None,
                        'path_params': ep.api_contract.path_params if ep.api_contract else [],
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
        print(json.dumps(out, indent=2))
        return

    if args.mode == 'deterministic':
        print(_render_deterministic(ev))
        return

    # explain mode
    print('\nAssembling context for Groq explanation layer ...\n')
    context = _build_llm_context(ev)

    print('Sending to Groq (llama3-70b-8192) ...\n')
    explanation = _run_groq(context)

    print(_section('DETERMINISTIC EVIDENCE SUMMARY'))
    print(f'  Feature    : {ev.feature}')
    print(f'  Confidence : {ev.confidence:.0%}')
    print(f'  Endpoints  : {len(ev.backend_endpoints)}')
    print(f'  Chain      : {" -> ".join(ev.service_chain) if ev.service_chain else "n/a"}')
    print(f'  Unresolved : {len(ev.unresolved_hops)} hop(s)')

    print(_section('GROQ ARCHITECTURE EXPLANATION'))
    print(explanation)
    print()


if __name__ == '__main__':
    main()
