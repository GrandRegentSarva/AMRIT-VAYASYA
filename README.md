# AMRIT-VAYASYA

The system ingests source code from multiple repositories, builds a structural knowledge graph, and answers deep architectural questions across service boundaries. Highly optimized for Java/Spring Boot on the backend and Angular/Fetch/Axios on the fronten.

---

## What This System Can Do

Ask plain-English questions and get deterministic, graph-grounded answers:

- "Which backend endpoint does beneficiary registration call?"
- "What services does HealthIdController depend on?"
- "Trace the full flow for the patient data feature."
- "What files would I need to change for AMRIT-101?"

The system answers these questions using static analysis, not guesswork. Every answer cites exact source files, class names, and API routes extracted directly from the code.

---

## Architecture

The project is split into three independent services, each with its own FastAPI server and MCP interface.

```
docs-mcp/        Ingestion and semantic retrieval         port 8000
cross-repo/      Graph intelligence and API tracing       port 8001
jira-mcp/        Jira integration and implementation      port 8002
                 plan generation
```

Each service runs independently. The `cross-repo` service reads Qdrant data produced by `docs-mcp`. The `jira-mcp` service calls `cross-repo` via HTTP. No service shares Python imports with another.

### Data Flow

```
Git Repository
      |
      v
docs-mcp: parse -> chunk -> embed -> Qdrant
                                        |
                                        v
cross-repo: scroll Qdrant -> build Neo4j graph
                                        |
                    +-------------------+-------------------+
                    |                                       |
                    v                                       v
            /trace?feature=...                    EvidenceCollector
            /explain?feature=...             (route normalization,
            /endpoints                        unresolved hops,
            /dependencies/{class}             API contracts,
                                              code retrieval)
                                                       |
                                                       v
                                             CLI Explainer Skill
                                             jira-mcp plan generator
```

---

## Repository Structure

```
Vayasya/
|
+-- docs-mcp/                   Section A: Docs MCP Server
|   +-- apps/
|   |   +-- api/main.py         FastAPI surface (/ingest, /query, /health)
|   |   +-- ingestion/          Git clone, file walker, deduplication
|   |   +-- worker/             Celery async ingestion worker
|   +-- core/
|   |   +-- parsing/            DocumentParser, SourceParser (AST + Tree-sitter)
|   |   +-- chunking/           SemanticChunker (structure-aware, overlap-safe)
|   |   +-- embeddings/         EmbeddingProvider (nomic-embed-text)
|   |   +-- retrieval/          HybridRetriever (BM25 + dense + reranker)
|   |   +-- metadata/           MetadataEnricher (classes, routes, HTTP calls, deps)
|   |   +-- qdrant/             QdrantClient wrapper
|   |   +-- models.py           DocumentChunk (includes cross-repo metadata fields)
|   +-- mcp/server.py           FastMCP tools (search_docs, summarize_repo, etc.)
|   +-- docs/                   Architecture, setup, ingestion, retrieval docs
|   +-- docker-compose.yml      Qdrant, Redis, Neo4j, API, Worker
|
+-- cross-repo/                 Section B + C: Graph Intelligence + API Explainer
|   +-- core/
|   |   +-- evidence.py         TraversalEvidence, EvidenceContract, UnresolvedHop
|   |   +-- evidence_collector.py  Deterministic traversal orchestrator
|   |   +-- route_normalizer.py    URL canonicalization and match quality scoring
|   |   +-- neo4j_client.py        Graph upserts and Cypher queries
|   |   +-- graph_builder.py       Qdrant -> Neo4j population
|   |   +-- frontend_extractor.py  Angular/fetch/axios/RestTemplate HTTP call extraction
|   |   +-- service_chain_resolver.py  Spring Boot DI + Angular constructor DI
|   +-- skills/
|   |   +-- api_flow_explainer.py  CLI skill (--mode deterministic | explain)
|   +-- api.py                  FastAPI (/health, /build-graph, /trace, /explain,
|   |                                    /endpoints, /dependencies/{class})
|   +-- mcp_server.py           FastMCP tools (trace_api_flow, explain_architecture,
|   |                                           list_endpoints, find_dependencies,
|   |                                           rebuild_graph)
|   +-- tests/                  29 unit tests
|
+-- jira-mcp/                   Section D: Jira Integration
|   +-- integrations/
|   |   +-- jira_client.py      Mock + real Jira client (5 canonical AMRIT tickets)
|   |   +-- plan_generator.py   Calls cross-repo /explain, produces grounded plan
|   +-- api.py                  FastAPI (/health, /tickets, /ticket/{key}, /plan/{key})
|   +-- mcp_server.py           FastMCP tools (list_jira_tickets, get_jira_ticket,
|   |                                           create_implementation_plan)
|   +-- tests/                  8 unit tests
|
+-- standards/                  Section E: Lightweight Standards Layer
|   +-- spring-boot.yml         Layering, REST, DTO, DI, exception conventions
|   +-- angular.yml             Component structure, naming, HTTP, DI, state conventions
|   +-- README.md               How standards are structured and consumed
|
+-- README.md
+-- CONTRIBUTING.md
+-- LICENSE
```

---

## What Has Been Built

### Section A: Docs MCP Server (100%)

| Capability | Implementation |
|---|---|
| Git repository ingestion | `apps/ingestion/service.py` — clone, walk, deduplicate by content hash |
| Incremental re-ingestion | Stale chunk detection and removal on repeated ingest |
| AST-aware source parsing | Tree-sitter for Python, TypeScript, JavaScript, Java, Go |
| HTML/Markdown document parsing | BeautifulSoup heading hierarchy, section extraction |
| Cross-repo metadata extraction | Classes, API routes, HTTP calls, DI dependencies per chunk |
| Semantic chunking | Structure-aware overlap, code block preservation |
| Embedding and vector storage | nomic-embed-text via sentence-transformers into Qdrant |
| Hybrid retrieval | Dense + BM25 merge with cross-encoder reranking |
| FastAPI REST interface | /ingest, /query, /collections, /health, /progress |
| FastMCP server | search_docs, summarize_repo, get_section, find_related |
| Celery async worker | Large repo ingestion without HTTP timeout |
| Docker Compose | Qdrant, Redis, Neo4j, API, Worker in single compose file |

### Section B: Cross-Repo Code Understanding (100%)

| Capability | Implementation |
|---|---|
| Neo4j knowledge graph | Repo, File, Class, Endpoint, HttpCall, UnresolvedDependency nodes |
| Graph builder | Scrolls all Qdrant chunks and populates Neo4j |
| Angular HTTP call extraction | HttpClient, fetch, axios patterns via regex |
| Java HTTP call extraction | RestTemplate, WebClient patterns |
| Spring Boot DI resolution | @Autowired, constructor injection, field injection |
| Angular DI resolution | Constructor parameter type extraction |
| Class layer classification | controller, service, repository, component, unknown |
| Route normalization | /patient/123/records -> /patient/{param}/records |
| RESOLVES_TO edge matching | Exact, template, and prefix match with confidence scores |
| Evidence contracts | Every edge annotated with matched_via and confidence |
| Unresolved hop detection | External services (Twilio, AWS, Kafka) flagged as UnresolvedDependency nodes |
| API contract abstraction | DTO class names extracted from controller signatures |
| FastAPI REST interface | /health, /build-graph, /trace, /explain, /endpoints, /dependencies/{class} |
| FastMCP server | trace_api_flow, explain_architecture, list_endpoints, find_dependencies, rebuild_graph |

Live graph with FHIR-API + HWC-API data: 4 repos, 463 files, 3124 classes, 273 endpoints.

### Section C: API Flow Explainer Skill (100%)

| Capability | Implementation |
|---|---|
| Deterministic traversal | EvidenceCollector queries Neo4j — LLM never touches the graph |
| Evidence model | TraversalEvidence dataclass with frontend_components, backend_endpoints, service_chain, api_contracts, unresolved_hops, provenance |
| Context assembly | Supporting code chunks fetched from Qdrant based on resolved class names |
| CLI deterministic mode | python skills/api_flow_explainer.py "feature" --mode deterministic |
| CLI explain mode | Groq llama3-70b narrates the assembled evidence |
| JSON output | --json flag emits raw TraversalEvidence as structured JSON |
| MCP exposure | explain_architecture tool returns full evidence payload |

### Section D: Jira Integration (100%)

| Capability | Implementation |
|---|---|
| Mock Jira client | 5 canonical AMRIT tickets targeting real graph paths |
| Real Jira fallback | Automatically uses real Jira when JIRA_SERVER/EMAIL/TOKEN set |
| Intent extraction | Feature keyword extracted from ticket summary and affected_feature field |
| Graph-grounded planning | Calls cross-repo /explain via HTTP — no shared imports |
| Impact analysis | Unresolved hops and downstream dependencies included in plan |
| Affected file listing | Exact file paths from Neo4j, not guessed |
| Implementation checklist | Contextual checklist differing for bug vs. feature tickets |
| Provenance trail | Every plan includes the graph traversal audit log |
| FastAPI REST interface | /health, /tickets, /ticket/{key}, /plan/{key} |
| FastMCP server | list_jira_tickets, get_jira_ticket, create_implementation_plan |

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.10+
- A Groq API key (only needed for `--mode explain` on the CLI skill)

### Step 1: Start the Infrastructure

```bash
cd docs-mcp
cp .env.example .env
docker compose up -d
```

This starts:
- `docs-mcp` API at http://localhost:8000
- Qdrant vector database at http://localhost:6333
- Neo4j graph database at http://localhost:7474 (neo4j / vayasya_dev)
- Redis (Celery broker) at localhost:6381

### Step 2: Ingest a Repository

```bash
# Ingest FHIR-API (Spring Boot backend)
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"git_url": "https://github.com/PSMRI/FHIR-API.git", "repo_name": "FHIR-API", "branch": "main"}'

# Ingest HWC-API (another Spring Boot backend)
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"git_url": "https://github.com/PSMRI/HWC-API.git", "repo_name": "HWC-API", "branch": "main"}'
```

Wait for the response confirming ingestion is complete.

### Step 3: Start the Cross-Repo Service

```bash
cd cross-repo
cp .env.example .env
# Add your Groq key if you want the explain mode:
# echo "GROQ_API_KEY=your_key_here" >> .env
pip install -r requirements.txt
uvicorn api:app --port 8001 --reload
```

### Step 4: Build the Knowledge Graph

```bash
curl -X POST http://localhost:8001/build-graph | python3 -m json.tool
```

Expected output:
```json
{
  "status": "ok",
  "stats": {
    "repos": 4,
    "files": 463,
    "classes": 3124,
    "endpoints": 273,
    "resolved_links": 18
  }
}
```

### Step 5: Start the Jira Service

```bash
cd jira-mcp
cp .env.example .env
pip install -r requirements.txt
uvicorn api:app --port 8002 --reload
```

---

## Running the Demo

### 1. API Trace (raw JSON)

```bash
# Trace the healthID feature across repos
curl -s "http://localhost:8001/trace?feature=healthID" | python3 -m json.tool

# Get the full evidence payload for a feature
curl -s "http://localhost:8001/explain?feature=patient" | python3 -m json.tool

# List all discovered endpoints
curl -s "http://localhost:8001/endpoints" | python3 -m json.tool

# Get dependency chain for a specific class
curl -s "http://localhost:8001/dependencies/EAushadhiController" | python3 -m json.tool
```

### 2. CLI Explainer Skill (the main demo)

```bash
cd cross-repo

# Deterministic mode: pure graph evidence, no LLM, works offline
python skills/api_flow_explainer.py "healthID" --mode deterministic

# JSON mode: machine-readable evidence payload
python skills/api_flow_explainer.py "patient" --mode deterministic --json

# Explain mode: Groq narrates the assembled evidence
# Requires GROQ_API_KEY in cross-repo/.env
python skills/api_flow_explainer.py "beneficiary" --mode explain
```

### 3. Jira Graph-Grounded Planning

```bash
# List all available tickets
curl -s http://localhost:8002/tickets | python3 -m json.tool

# View a specific ticket
curl -s http://localhost:8002/ticket/AMRIT-101 | python3 -m json.tool

# Generate a graph-grounded implementation plan
# (requires cross-repo running at localhost:8001)
curl -s http://localhost:8002/plan/AMRIT-101 | python3 -m json.tool | grep -A 100 '"plan"'
```

Available canonical tickets:

| Key | Summary | Demonstrates |
|---|---|---|
| AMRIT-101 | Add email notification after beneficiary registration | Event tracing, service chain, downstream impact |
| AMRIT-102 | Modify HealthID validation rules | Impact analysis, API traversal, DTO tracing |
| AMRIT-103 | Add audit logging to patient registration | Cross-cutting concerns, architecture expansion |
| AMRIT-104 | Expose FHIR-compatible patient data endpoint | API contract abstraction, service reuse |
| AMRIT-105 | Fix NullPointerException in EAushadhi drug search | Bug tracing, controller-level identification |

### 4. Neo4j Visual Exploration

Open http://localhost:7474 in your browser and login with `neo4j / vayasya_dev`.

Useful Cypher queries:

```cypher
-- See all repos and their file counts
MATCH (f:File)-[:BELONGS_TO]->(r:Repo)
RETURN r.name AS repo, count(f) AS files ORDER BY files DESC

-- Trace the healthID endpoint chain
MATCH (e:Endpoint)
WHERE toLower(e.path) CONTAINS 'healthid'
OPTIONAL MATCH (e)<-[:HANDLES]-(c:Class)-[:DEPENDS_ON*0..3]->(dep:Class)
RETURN e.path, c.name, collect(dep.name)

-- Find all unresolved external hops
MATCH (u:UnresolvedDependency) RETURN u.name, u.dep_type, u.context

-- See all RESOLVES_TO edges with their confidence scores
MATCH (h:HttpCall)-[r:RESOLVES_TO]->(e:Endpoint)
RETURN h.path, e.path, r.match_quality, r.confidence
LIMIT 20
```

---

## Test Suite

```bash
# Cross-repo: 29 tests
cd cross-repo && python -m pytest tests/ -v

# Jira-mcp: 8 tests
cd jira-mcp && python -m pytest tests/ -v
```

Coverage:
- Route normalization edge cases (UUID, integer, Spring template, prefix)
- Frontend HTTP call extraction (Angular, fetch, axios, RestTemplate, WebClient)
- Service dependency extraction (Spring @Autowired, Angular constructor DI)
- Class layer classification (controller, service, repository, component)
- Jira mock client (all 5 tickets, error handling, field completeness)

---

## Service Ports Reference

| Service | Port | Interface |
|---|---|---|
| docs-mcp API | 8000 | REST + FastMCP |
| cross-repo API | 8001 | REST + FastMCP |
| jira-mcp API | 8002 | REST + FastMCP |
| Qdrant | 6333 | REST |
| Neo4j Browser | 7474 | Web UI |
| Neo4j Bolt | 7687 | Driver |
| Redis | 6381 | Celery broker |
