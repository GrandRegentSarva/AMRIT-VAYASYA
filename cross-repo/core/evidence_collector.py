"""
Evidence Collector
------------------
The orchestrator that queries Neo4j and Qdrant to build a TraversalEvidence object.

CRITICAL RULE: The LLM never touches Neo4j or Qdrant.
               This module does the traversal. The LLM gets the result.

Flow:
    feature string
    -> Neo4j trace query
    -> resolve routes (route_normalizer)
    -> detect unresolved hops
    -> extract API contracts (DTOs)
    -> pull supporting code chunks from Qdrant
    -> compute confidence
    -> return TraversalEvidence
"""
from __future__ import annotations

import re
import logging
from typing import Any

from qdrant_client import QdrantClient

from config import get_settings
from core.evidence import (
    ApiContract,
    BackendEndpoint,
    EvidenceContract,
    FrontendComponent,
    TraversalEvidence,
    UnresolvedHop,
)
from core.neo4j_client import Neo4jClient
from core.route_normalizer import normalize_route, routes_match

logger = logging.getLogger(__name__)

# Known external services that are not AMRIT repos
_EXTERNAL_MARKERS = {
    'twilio', 'sendgrid', 'aws', 's3', 'sns', 'sqs', 'kafka', 'rabbitmq',
    'smtp', 'firebase', 'fcm', 'gcm', 'stripe', 'razorpay', 'sms',
}

# DTO pattern: class names ending in DTO, Request, Response, Payload
_DTO_PATTERN = re.compile(
    r'\b([A-Z][A-Za-z0-9]+(?:DTO|Dto|Request|Response|Payload|Model|Bean))\b'
)

# Path param extractor
_PATH_PARAM_PATTERN = re.compile(r'\{([^}]+)\}')


def _detect_external(dep_name: str) -> bool:
    return any(marker in dep_name.lower() for marker in _EXTERNAL_MARKERS)


def _extract_dtos(text: str) -> list[str]:
    return list(dict.fromkeys(_DTO_PATTERN.findall(text)))


def _extract_path_params(path: str) -> list[str]:
    return _PATH_PARAM_PATTERN.findall(path)


class EvidenceCollector:
    """
    Builds a TraversalEvidence object for a feature query.
    All graph queries are deterministic. No LLM involvement.
    """

    def __init__(self) -> None:
        s = get_settings()
        self._neo4j = Neo4jClient()
        self._qdrant = QdrantClient(url=s.qdrant_url)
        self._collection = s.collection_name

    def collect(self, feature: str) -> TraversalEvidence:
        ev = TraversalEvidence(feature=feature)
        ev.log_provenance(f'Starting traversal for feature: "{feature}"')

        # Step 1: Neo4j trace query
        raw_traces = self._neo4j.query_trace(feature)
        ev.log_provenance(f'Neo4j returned {len(raw_traces)} raw trace rows')

        if not raw_traces:
            ev.confidence = 0.0
            ev.log_provenance('No matching endpoints found in graph')
            return ev

        # Step 2: Build backend endpoints with normalised routes
        seen_endpoints: set[str] = set()
        all_class_names: list[str] = []
        confidence_votes: list[float] = []

        for row in raw_traces:
            endpoint_key = f"{row.get('method')}::{row.get('path')}"
            if endpoint_key in seen_endpoints:
                continue
            seen_endpoints.add(endpoint_key)

            raw_path = row.get('path') or ''
            norm_path = normalize_route(raw_path)
            handler = row.get('handler_class') or ''
            chain: list[str] = row.get('service_chain') or []

            if handler:
                all_class_names.append(handler)
            for svc in chain:
                if svc and svc not in all_class_names:
                    all_class_names.append(svc)

            # API Contract: pull DTOs from Qdrant code later; for now extract path params
            api_contract = ApiContract(
                endpoint_id=endpoint_key,
                request_dto=None,
                response_dto=None,
                path_params=_extract_path_params(norm_path),
            )

            be = BackendEndpoint(
                method=row.get('method') or 'GET',
                path=raw_path,
                normalized_path=norm_path,
                repo=row.get('backend_repo') or '',
                handler_class=handler,
                handler_kind=row.get('handler_kind') or 'unknown',
                backend_file=row.get('backend_file') or '',
                api_contract=api_contract,
            )
            ev.backend_endpoints.append(be)

            # Service chain
            for name in chain:
                if name and name not in ev.service_chain:
                    ev.service_chain.append(name)

            # Frontend callers from this trace row
            for caller_raw in (row.get('frontend_callers') or []):
                caller_name = caller_raw.get('caller')
                if not caller_name:
                    continue
                called_path = caller_raw.get('path') or raw_path
                norm_called = normalize_route(called_path)
                matched, match_quality = routes_match(norm_called, norm_path)
                confidence_score = {'exact': 1.0, 'template': 0.85, 'prefix': 0.6}.get(match_quality, 0.4)
                confidence_votes.append(confidence_score)

                ev_contract = EvidenceContract(
                    source_file=caller_raw.get('file') or '',
                    source_line=None,
                    matched_via=match_quality,
                    confidence=confidence_score,
                )
                fc = FrontendComponent(
                    class_name=caller_name,
                    repo=caller_raw.get('repo') or '',
                    file_path=caller_raw.get('file') or '',
                    http_method=be.method,
                    called_path=called_path,
                    normalized_path=norm_called,
                    evidence=ev_contract,
                )
                ev.frontend_components.append(fc)
                ev.log_provenance(
                    f'Frontend caller: {caller_name} -> {be.method} {raw_path} '
                    f'[match={match_quality}, confidence={confidence_score}]'
                )

        # If no frontend callers, confidence is based purely on endpoint match
        if not confidence_votes:
            confidence_votes.append(0.75)  # structural match only

        ev.log_provenance(f'Resolved {len(ev.backend_endpoints)} backend endpoints')

        # Step 3: Detect unresolved hops in the service chain
        self._detect_unresolved_hops(ev, all_class_names, raw_traces)

        # Step 4: Pull supporting code chunks from Qdrant
        self._pull_supporting_chunks(ev, all_class_names)

        # Step 5: Extract DTOs from supporting chunks (API contract abstraction)
        self._enrich_api_contracts(ev)

        # Step 6: Compute overall confidence
        ev.confidence = round(sum(confidence_votes) / len(confidence_votes), 2)
        ev.log_provenance(f'Final confidence: {ev.confidence}')

        return ev

    def _detect_unresolved_hops(
        self,
        ev: TraversalEvidence,
        resolved_class_names: list[str],
        raw_traces: list[dict[str, Any]],
    ) -> None:
        """
        Walk the dependency metadata and flag any class that looks external
        or was not found in the graph (closed-world violation).
        """
        # Gather all dependency names mentioned in the trace chain
        all_deps: set[str] = set()
        for row in raw_traces:
            chain = row.get('service_chain') or []
            for name in chain:
                if name:
                    all_deps.add(name)

        for dep in all_deps:
            if dep in resolved_class_names:
                continue
            if _detect_external(dep):
                hop = UnresolvedHop(
                    name=dep,
                    hop_type='external_service',
                    context=f'"{dep}" matches known external service pattern; not an AMRIT class',
                )
                ev.unresolved_hops.append(hop)
                ev.log_provenance(f'External service boundary detected: {dep}')
            else:
                hop = UnresolvedHop(
                    name=dep,
                    hop_type='missing_repo',
                    context=f'"{dep}" appears in dependency chain but has not been ingested',
                )
                ev.unresolved_hops.append(hop)
                ev.log_provenance(f'Missing repo boundary: {dep} not found in graph')

    def _pull_supporting_chunks(self, ev: TraversalEvidence, class_names: list[str]) -> None:
        """
        Retrieve actual source code chunks from Qdrant for the identified classes.
        These are the raw evidence that will be shown to the LLM.
        """
        if not class_names:
            return

        from qdrant_client.http import models as qmodels

        try:
            results, _ = self._qdrant.scroll(
                collection_name=self._collection,
                scroll_filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key='classes',
                            match=qmodels.MatchAny(any=class_names[:20]),  # cap at 20
                        )
                    ]
                ),
                limit=30,
                with_payload=True,
                with_vectors=False,
            )

            seen_paths: set[str] = set()
            for point in results:
                pl = point.payload or {}
                path_key = pl.get('path', '')
                if path_key in seen_paths:
                    continue
                seen_paths.add(path_key)
                ev.supporting_chunks.append({
                    'file': pl.get('path', ''),
                    'repo': pl.get('repo', ''),
                    'language': pl.get('language', ''),
                    'classes': pl.get('classes', []),
                    'text': (pl.get('text') or '')[:600],  # cap per chunk
                })

            ev.log_provenance(f'Retrieved {len(ev.supporting_chunks)} unique code chunks from Qdrant')

        except Exception as exc:
            logger.warning('Qdrant chunk retrieval failed: %s', exc)
            ev.log_provenance(f'Qdrant retrieval failed: {exc}')

    def _enrich_api_contracts(self, ev: TraversalEvidence) -> None:
        """
        Extract DTO names from supporting code chunks and attach them
        to the corresponding ApiContract on each BackendEndpoint.
        """
        # Build a map: handler_class -> supporting chunk text
        class_to_text: dict[str, str] = {}
        for chunk in ev.supporting_chunks:
            for cls in chunk.get('classes', []):
                class_to_text[cls] = chunk.get('text', '')

        for endpoint in ev.backend_endpoints:
            handler = endpoint.handler_class
            text = class_to_text.get(handler, '')
            if not text or not endpoint.api_contract:
                continue
            dtos = _extract_dtos(text)
            if dtos:
                endpoint.api_contract.request_dto = dtos[0]
                if len(dtos) > 1:
                    endpoint.api_contract.response_dto = dtos[1]
                ev.log_provenance(
                    f'API contract for {endpoint.path}: request={dtos[0]}'
                    + (f', response={dtos[1]}' if len(dtos) > 1 else '')
                )

    def close(self) -> None:
        self._neo4j.close()
