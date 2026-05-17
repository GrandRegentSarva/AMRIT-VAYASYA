# cross-repo: Cross-Repository Code Intelligence

The graph intelligence engine for AMRIT-VAYASYA. It builds a Neo4j knowledge graph from repositories indexed by `docs-mcp` and exposes deterministic API tracing, dependency resolution, and architecture explanation.

This module covers **Section B** (Cross-Repo Code Understanding) and **Section C** (API Flow Explainer Skill) of the MVP.

---

## What It Can Answer

- "Which backend endpoint does beneficiary registration call?"
- "What services does EAushadhiController depend on?"
- "Show me all endpoints in HWC-API."
- "Explain the full architecture of the patient data feature."

Every answer is deterministic. No LLM queries the graph. The LLM only narrates pre-assembled evidence.

---

## Graph Data Model

```
(:Repo {name})
(:File {path, language, framework})
(:Class {name, kind})                   kind: controller | service | repository | component
(:Endpoint {method, path,               backend route e.g. GET /api/v1/patient/{param}
            normalized_path,
            request_dto, response_dto})
(:HttpCall {method, path,               frontend outbound call
            normalized_path})
(:UnresolvedDependency {name,           external/missing service boundary
                        dep_type,
                        context})

(:File)-[:BELONGS_TO]->(:Repo)
(:Class)-[:DEFINED_IN]->(:File)
(:Endpoint)<-[:HANDLES]-(:Class)
(:Class)-[:DEPENDS_ON]->(:Class)
(:Class)-[:MAKES]->(:HttpCall)
(:HttpCall)-[r:RESOLVES_TO {match_quality, confidence}]->(:Endpoint)
(:Class)-[:DEPENDS_ON_EXTERNAL]->(:UnresolvedDependency)
```

---

## Core Modules

| File | Purpose |
|---|---|
| `core/evidence.py` | `TraversalEvidence` dataclass — the single source of truth for all consumers |
| `core/evidence_collector.py` | Deterministic orchestrator: Neo4j traversal, Qdrant retrieval, hop detection |
| `core/route_normalizer.py` | Converts `/patient/123/records` to `/patient/{param}/records` for reliable matching |
| `core/neo4j_client.py` | Graph upserts and Cypher queries with evidence contract metadata on edges |
| `core/graph_builder.py` | Scrolls Qdrant, populates Neo4j with nodes and edges |
| `core/frontend_extractor.py` | Extracts HTTP calls from Angular, fetch, axios, RestTemplate, WebClient |
| `core/service_chain_resolver.py` | Extracts DI dependencies from Spring Boot and Angular constructors |
| `skills/api_flow_explainer.py` | CLI skill: deterministic report or Groq narration |

---

## Setup

### Prerequisites

- `docs-mcp` running with Qdrant and Neo4j up
- Python 3.10+
- Groq API key (only for `--mode explain`)

```bash
cd cross-repo
cp .env.example .env
# Optional: add GROQ_API_KEY=your_key_here to .env
pip install -r requirements.txt
```

### Start the infrastructure first

```bash
cd ../docs-mcp
docker compose up -d
```

---

## Running

```bash
# Start the cross-repo API server
uvicorn api:app --port 8001 --reload

# Trigger a full graph build from all indexed Qdrant data
curl -X POST http://localhost:8001/build-graph | python3 -m json.tool
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check and live graph stats |
| POST | `/build-graph` | Rebuild graph from all Qdrant data |
| GET | `/endpoints` | List all discovered endpoints with handler mappings |
| GET | `/trace?feature=` | Trace a feature across repos (raw graph result) |
| GET | `/explain?feature=` | Full TraversalEvidence JSON (evidence contracts, DTOs, hops) |
| GET | `/dependencies/{class}` | Dependency chain for a named class |

---

## CLI Explainer Skill

```bash
cd cross-repo

# Deterministic mode: pure graph evidence, no LLM required
python skills/api_flow_explainer.py "healthID" --mode deterministic

# JSON mode: machine-readable TraversalEvidence
python skills/api_flow_explainer.py "patient" --mode deterministic --json

# Explain mode: Groq narrates the assembled evidence
# Requires GROQ_API_KEY in .env
python skills/api_flow_explainer.py "beneficiary" --mode explain
```

The output of `--mode deterministic` includes:

- Frontend callers (Angular components) with match quality and evidence
- Backend endpoints with normalized paths, handler classes, and DTOs
- Full service dependency chain
- Unresolved hops (external APIs, missing repos)
- Supporting source code snippets from Qdrant
- Complete provenance audit trail

---

## MCP Tools

```bash
python mcp_server.py
```

| Tool | Arguments | Description |
|---|---|---|
| `trace_api_flow` | `feature: str` | Raw graph trace for a feature |
| `explain_architecture` | `feature: str` | Full TraversalEvidence payload for LLM narration |
| `list_endpoints` | `repo_name: str (optional)` | All mapped endpoints |
| `find_dependencies` | `class_name: str` | Dependency chain |
| `rebuild_graph` | none | Trigger full graph rebuild |

---

## Tests

```bash
python -m pytest tests/ -v
# 29 tests covering:
# - Route normalization (UUID, integer, Spring template, prefix, query string)
# - Frontend HTTP extraction (Angular, fetch, axios, RestTemplate, WebClient)
# - Service dependency extraction (Spring, Angular)
# - Class layer classification
```
