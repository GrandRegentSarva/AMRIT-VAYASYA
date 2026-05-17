# Docs MCP

The ingestion and semantic retrieval engine for AMRIT-VAYASYA. It ingests source code repositories, extracts structural metadata, indexes chunks into Qdrant, and exposes both REST and MCP interfaces for querying.

This module covers **Section A** (Docs MCP Server) of the MVP.

---

## What It Does

- Clones any public Git repository and indexes its contents
- Parses source code with syntax-aware AST extraction (Python, TypeScript, JavaScript, Java, Go)
- Extracts cross-repo metadata per chunk: class names, API routes, HTTP calls, DI dependencies
- Chunks documents with heading hierarchy preservation and overlap
- Embeds chunks using nomic-embed-text and stores them in Qdrant
- Maintains a BM25 index for keyword-based retrieval
- Exposes hybrid retrieval: dense vector + BM25 merged with cross-encoder reranking
- Provides a FastMCP server for use as an MCP tool server

---

## Architecture

```
Git URL or local path
        |
        v
DocumentParser / SourceParser
(AST + Tree-sitter, BeautifulSoup for HTML)
        |
        v
MetadataEnricher
(classes, api_routes, http_calls, dependencies per chunk)
        |
        v
SemanticChunker
(section-aware, heading hierarchy, overlap-safe)
        |
      +---+---+
      |       |
      v       v
EmbeddingProvider  BM25Index
(nomic-embed-text) (rank-bm25)
      |       |
      v       v
   Qdrant    HybridRetriever
              |
              v
           Reranker
           (cross-encoder)
              |
         +----+----+
         |         |
         v         v
      FastAPI    FastMCP
```

---

## Setup

```bash
cd docs-mcp
cp .env.example .env
docker compose up -d --build
```

This starts five containers:
- `docs-mcp-api` on port 8000
- `docs-mcp-worker` (Celery)
- `docs-mcp-qdrant` on port 6333
- `docs-mcp-neo4j` on ports 7474 (browser) and 7687 (bolt)
- `docs-mcp-redis` on port 6381

FastAPI interactive docs: http://localhost:8000/docs

---

## Ingesting a Repository

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "git_url": "https://github.com/PSMRI/FHIR-API.git",
    "repo_name": "FHIR-API",
    "branch": "main"
  }'
```

For large repositories that time out via HTTP, ingest directly in the container:

```bash
docker compose exec api python -c "
import asyncio
from apps.ingestion.service import IngestionService
from core.models import IngestRequest

async def run():
    svc = IngestionService()
    req = IngestRequest(
        git_url='https://github.com/PSMRI/HWC-API.git',
        repo_name='HWC-API',
        branch='main',
        force=True
    )
    result = await svc.ingest(req)
    print(f'Files: {result.parsed_files}, Chunks: {result.indexed_chunks}')

asyncio.run(run())
"
```

---

## Querying

```bash
# Semantic query across indexed repos
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How is HealthID validation implemented?",
    "repo_name": "FHIR-API",
    "limit": 5
  }'

# List all indexed collections
curl http://localhost:8000/collections

# Health check
curl http://localhost:8000/health
```

---

## MCP Server

The MCP server exposes the following tools for use with any MCP-compatible client (Claude Desktop, custom agents, etc.):

```bash
python mcp/server.py
```

| Tool | Arguments | Description |
|---|---|---|
| `search_docs` | `query, repo_name, limit` | Hybrid semantic search across indexed repos |
| `summarize_repo` | `repo_name` | High-level summary of a repository |
| `get_section` | `query, section_heading` | Find content under a specific heading |
| `find_related` | `chunk_id` | Find related chunks by semantic similarity |

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/ingest` | Ingest a repository by Git URL or local path |
| POST | `/query` | Semantic search query |
| GET | `/collections` | List all indexed Qdrant collections |
| GET | `/health` | Health check |
| GET | `/progress/{repo_name}` | Check ingestion progress |

---

## Cross-Repo Metadata

Each indexed chunk includes these metadata fields used by the `cross-repo` service:

| Field | Type | Description |
|---|---|---|
| `classes` | list[str] | Class names found in this chunk |
| `api_routes` | list[str] | Backend routes (e.g. "GET /api/v1/patient") |
| `http_calls` | list[str] | Outbound HTTP calls (e.g. "POST /api/beneficiary") |
| `dependencies` | list[str] | Injected class names (Spring @Autowired, Angular constructor) |

---

## Documentation

See `docs/` for detailed documentation:

| File | Contents |
|---|---|
| `architecture.md` | System architecture and design principles |
| `ingestion_pipeline.md` | How repositories are parsed and indexed |
| `retrieval_pipeline.md` | How queries are processed and ranked |
| `chunking_strategy.md` | How documents are split into chunks |
| `mcp_tools.md` | MCP tool reference |
| `setup.md` | Detailed setup and configuration guide |
| `troubleshooting.md` | Common issues and solutions |
| `contribution_guide.md` | How to contribute |
