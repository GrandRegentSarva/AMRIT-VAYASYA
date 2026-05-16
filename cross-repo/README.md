# cross-repo: Cross-Repository Code Understanding

A standalone service that builds a **Neo4j knowledge graph** of service dependencies across all AMRIT repositories indexed by `docs-mcp`. It maps frontend HTTP calls to backend endpoints and traces the full Spring Boot controller → service → repository chain.

## What It Can Answer

- *"Which backend endpoint does beneficiary registration call?"*
- *"What services does BeneficiaryController depend on?"*
- *"Show me all API endpoints in HWC-API."*

## Graph Data Model

```
(:Repo {name})
(:File {path, language, framework})
(:Class {name, kind})           ← controller | service | repository | component
(:Endpoint {method, path})      ← backend route e.g. GET /api/beneficiary
(:HttpCall {method, path})      ← frontend outbound call

(:File)-[:BELONGS_TO]->(:Repo)
(:Class)-[:DEFINED_IN]->(:File)
(:Endpoint)<-[:HANDLES]-(:Class)
(:Class)-[:DEPENDS_ON]->(:Class)
(:Class)-[:MAKES]->(:HttpCall)
(:HttpCall)-[:RESOLVES_TO]->(:Endpoint)
```

## Prerequisites

- `docs-mcp` running with Qdrant and Neo4j containers up:
  ```bash
  cd ../docs-mcp && docker compose up -d
  ```

## Quick Start

```bash
cd cross-repo
cp .env.example .env
pip install -r requirements.txt

# Run the API server
uvicorn api:app --reload --port 8001
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check + graph stats |
| `POST` | `/build-graph` | Rebuild graph from Qdrant |
| `GET` | `/endpoints` | List all endpoint mappings |
| `GET` | `/trace?feature=...` | Trace a feature flow |
| `GET` | `/dependencies/{class_name}` | Dependency chain |

## MCP Tools

```bash
python mcp_server.py
```

Tools exposed:
- `trace_api_flow(feature)` — Full frontend→backend trace
- `list_endpoints(repo_name)` — All endpoint mappings
- `find_dependencies(class_name)` — Dependency chain
- `rebuild_graph()` — Trigger graph rebuild

## Demo Flow

```bash
# 1. Ingest an Angular frontend and Spring Boot backend via docs-mcp
curl -X POST http://localhost:8000/ingest \
  -d '{"git_url": "https://github.com/PSMRI/HWC-API.git", "repo_name": "HWC-API"}'

# 2. Build the cross-repo graph
curl -X POST http://localhost:8001/build-graph

# 3. Trace a feature
curl "http://localhost:8001/trace?feature=beneficiary+registration"

# 4. Explore the graph visually in Neo4j Browser
open http://localhost:7474
# Login: neo4j / vayasya_dev
```

## Tests

```bash
pytest tests/ -v
```
