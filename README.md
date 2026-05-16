# AMRIT-VAYASYA: SRE & Docs AI Agent

Welcome to the **AMRIT-VAYASYA** repository. This project serves as an intelligent, autonomous agent designed to deeply understand software architecture, map cross-repository dependencies, and directly integrate with SDLC workflows via the Model Context Protocol (MCP).

---

## The Vision: Ideal MVP Implementation

This project is built around a rigorous MVP specification designed to move beyond standard "PDF chatbots" and deliver **Massive Signal Value** through deep code understanding and orchestration.

### A. Docs MCP Server (Foundation)
*The core ingestion and semantic engine.*
- **Status:** Foundation Complete
- **Tech Stack:** FastAPI, Qdrant Vector DB, SentenceTransformers (Embeddings), and FastMCP.
- **Capabilities:**
  - Automated `git clone` ingestion of AMRIT docs and repositories.
  - Advanced syntax-aware parsing (Python, TS/JS, Java, Go) using AST and Tree-sitter.
  - Semantic indexing and chunking with preserved heading hierarchies.
  - Plain-English querying and contextual hybrid retrieval (Dense + BM25).

### B. Cross-Repo Code Understanding (The Killer Feature)
*Mapping frontend calls to backend endpoints across all AMRIT repos using a Neo4j knowledge graph.*
- **Status:** Complete
- **Tech Stack:** Neo4j, Qdrant (shared with docs-mcp), FastAPI, FastMCP.
- **Capabilities:**
  - Endpoint tracing across repositories.
  - Service dependency mapping (Controller -> Service -> Repository).
  - **Frontend to Backend API Mapping**: Answers "Which backend endpoint does beneficiary registration call?"
  - Visual graph exploration via Neo4j Browser at `http://localhost:7474`.

### C. API Flow Explainer Skill (High-Quality Skill)
*A single, high-fidelity skill demonstrating complete SDLC usefulness.*
- **Status:** Planned
- **Flow:**
  1. User asks about a feature.
  2. Skill traces frontend API usage.
  3. Finds backend endpoint.
  4. Identifies the full service chain.
  5. Explains the architecture seamlessly.

### D. JIRA Integration
*Visible workflow integration tailored for SDLC relevance.*
- **Status:** Planned
- **Capabilities:**
  - Fetch JIRA tickets via MCP.
  - Summarize tasks intelligently.
  - Generate automated, context-aware Implementation Plans.

### E. Lightweight Standards Layer
*Enforcing and referencing architectural rules.*
- **Status:** Planned
- **Capabilities:**
  - Defined Markdown/YAML standards for **Angular conventions**.
  - Layering rules for **Spring Boot**.

### F. Documentation
*Clear, structured guidance separating chaotic builders from strong infra contributors.*
- **Status:** Mostly Complete (Located in `docs-mcp/docs/`)
- **Included Artifacts:**
  - Architecture Diagrams & System Design
  - Setup & Quickstart Guide
  - Contribution Guide
  - Component Breakdown (Ingestion & Retrieval pipelines)

---

## Quick Start (Local Demo)

The system is configured to run fully locally without requiring a dedicated GPU (CPU fallback enabled).

### 1. Start the Environment
```bash
cd docs-mcp
cp .env.example .env
# Set USE_LIGHTWEIGHT_EMBEDDINGS=true in .env for faster local startup

docker compose up -d --build
# Starts: FastAPI (8000), Qdrant (6333), Redis (6379), Neo4j (7474/7687)
```

### 2. Ingest a Repository
```bash
curl -X POST "http://localhost:8000/ingest" \
     -H "Content-Type: application/json" \
     -d '{
           "git_url": "https://github.com/PSMRI/FHIR-API.git",
           "repo_name": "FHIR-API",
           "branch": "main"
         }'
```

### 3. Query the Codebase (Docs MCP)
```bash
curl -X POST "http://localhost:8000/query" \
     -H "Content-Type: application/json" \
     -d '{"query": "How is the routing implemented?", "repo_name": "FHIR-API", "limit": 3}'
```

### 4. Build the Cross-Repo Graph
```bash
cd ../cross-repo
cp .env.example .env
pip install -r requirements.txt
uvicorn api:app --port 8001

# Trigger graph build from all Qdrant data
curl -X POST http://localhost:8001/build-graph

# Trace a feature across repos
curl "http://localhost:8001/trace?feature=beneficiary+registration"

# Explore the graph visually
open http://localhost:7474   # Login: neo4j / vayasya_dev
```

---

## Directory Structure

```text
Vayasya/
├── docs-mcp/           # A. Docs MCP Server (Complete)
│   ├── apps/           # FastAPI + Celery worker
│   ├── core/           # Parsers, embeddings, retrieval, chunking
│   ├── mcp/            # FastMCP server (search_docs, summarize_repo, etc.)
│   └── docs/           # Architecture & setup documentation
├── cross-repo/         # B. Cross-Repo Code Understanding (Complete)
│   ├── core/           # Neo4j client, graph builder, extractors, resolvers
│   ├── api.py          # FastAPI endpoints
│   ├── mcp_server.py   # FastMCP tools (trace_api_flow, list_endpoints, etc.)
│   └── tests/          # Unit tests
├── README.md
└── LICENSE
```
