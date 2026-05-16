# Docs MCP

Docs MCP is a locally runnable documentation ingestion and retrieval platform for source repositories. It ingests repository content, extracts structured metadata, chunks documents with section awareness, indexes embeddings into Qdrant, maintains BM25 state for keyword search, and exposes both FastAPI and FastMCP interfaces.

## Features

- Repository ingestion from local paths or Git URLs
- Syntax-aware parsing for Python, JavaScript, TypeScript, Java, and Go
- Metadata-rich chunking with section hierarchy, framework hints, and source lineage
- Hybrid retrieval with BM25, dense vector search, normalization, and reranking
- MCP tools for search, section explanation, related chunk lookup, and repository summarization
- Local-first operation via Docker Compose

## Quick Start

```bash
cd docs-mcp
cp .env.example .env
docker compose up --build
```

FastAPI docs: `http://localhost:8000/docs`

## Docs

- `docs/architecture.md`
- `docs/ingestion_pipeline.md`
- `docs/retrieval_pipeline.md`
- `docs/chunking_strategy.md`
- `docs/mcp_tools.md`
- `docs/setup.md`
- `docs/troubleshooting.md`
- `docs/contribution_guide.md`
