"""
Evidence model for the cross-repo traversal engine.

TraversalEvidence is the canonical output of a graph traversal.
It is the single source of truth for all downstream consumers:
  - CLI deterministic report
  - Groq explanation layer
  - Jira implementation plan generator
  - MCP tools

The LLM is never allowed to query Neo4j or Qdrant directly.
The orchestrator builds a TraversalEvidence object and hands it to the LLM as context.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidenceContract:
    """
    Formal proof of why a graph edge exists.
    Prevents hallucination by making every connection citable.
    """
    source_file: str
    source_line: int | None
    matched_via: str   # "exact" | "template" | "prefix"
    confidence: float  # 0.0 - 1.0


@dataclass
class FrontendComponent:
    class_name: str
    repo: str
    file_path: str
    http_method: str
    called_path: str
    normalized_path: str
    evidence: EvidenceContract


@dataclass
class ApiContract:
    """
    The request/response schema of an endpoint.
    Populated from DTO class names found in controller signatures.
    """
    endpoint_id: str
    request_dto: str | None
    response_dto: str | None
    path_params: list[str]


@dataclass
class BackendEndpoint:
    method: str
    path: str
    normalized_path: str
    repo: str
    handler_class: str
    handler_kind: str
    backend_file: str
    api_contract: ApiContract | None


@dataclass
class UnresolvedHop:
    """
    Represents a dead-end in the dependency chain.
    Explicitly distinguishes between 'logic ends here' and
    'delegates to an unknown external system'.
    """
    name: str
    hop_type: str   # "external_api" | "missing_repo" | "external_service"
    context: str    # e.g., "Called from BeneficiaryService via RestTemplate"


@dataclass
class TraversalEvidence:
    """
    The complete, deterministic evidence package for a feature traversal.

    This is built by the EvidenceCollector and consumed (read-only) by
    the explanation layer. The LLM receives this as structured context.
    """
    feature: str

    # Layer 1: Frontend callers (empty if no frontend repo ingested)
    frontend_components: list[FrontendComponent] = field(default_factory=list)

    # Layer 2: API Contracts (DTOs, path params)
    api_contracts: list[ApiContract] = field(default_factory=list)

    # Layer 3: Backend endpoints resolved from graph
    backend_endpoints: list[BackendEndpoint] = field(default_factory=list)

    # Layer 4: Full dependency injection chain per endpoint
    service_chain: list[str] = field(default_factory=list)

    # Layer 5: Actual source code chunks from Qdrant
    supporting_chunks: list[dict[str, Any]] = field(default_factory=list)

    # Graph-derived confidence (0.0 = speculative, 1.0 = exact match everywhere)
    confidence: float = 0.0

    # Dead ends in the dependency chain
    unresolved_hops: list[UnresolvedHop] = field(default_factory=list)

    # Audit trail of how every connection was derived
    provenance: list[str] = field(default_factory=list)

    def log_provenance(self, message: str) -> None:
        self.provenance.append(message)

    def is_empty(self) -> bool:
        return not self.backend_endpoints and not self.frontend_components

    def summary(self) -> dict[str, Any]:
        """Compact summary for display and logging."""
        return {
            'feature': self.feature,
            'confidence': round(self.confidence, 2),
            'frontend_components': len(self.frontend_components),
            'backend_endpoints': len(self.backend_endpoints),
            'service_chain_length': len(self.service_chain),
            'supporting_chunks': len(self.supporting_chunks),
            'unresolved_hops': len(self.unresolved_hops),
            'provenance_steps': len(self.provenance),
        }
