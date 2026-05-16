from __future__ import annotations

from fastapi import FastAPI, HTTPException, status

from apps.ingestion.service import IngestionService
from core.config import get_settings
from core.models import (
    CollectionResponse,
    ErrorResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    IngestionProgress,
    QueryRequest,
    QueryResponse,
)
from core.retrieval.hybrid import HybridRetriever

app = FastAPI(title='Docs MCP API', version='0.2.0')
settings = get_settings()
ingestion = IngestionService()
retriever = HybridRetriever(vector_store=ingestion.store, embedder=ingestion.embedder)


@app.get('/health', response_model=HealthResponse, responses={500: {'model': ErrorResponse}})
async def health() -> HealthResponse:
    return HealthResponse(
        status='ok',
        qdrant_configured=bool(settings.qdrant_url),
        redis_configured=bool(settings.redis_url),
    )


@app.get('/collections', response_model=CollectionResponse, responses={500: {'model': ErrorResponse}})
async def collections() -> CollectionResponse:
    try:
        return CollectionResponse(collections=ingestion.store.collections())
    except Exception as exc:
        raise _error(status.HTTP_500_INTERNAL_SERVER_ERROR, 'collection_lookup_failed', str(exc))


@app.get('/ingest/{job_id}', response_model=IngestionProgress, responses={404: {'model': ErrorResponse}})
async def ingest_progress(job_id: str) -> IngestionProgress:
    progress = ingestion.get_progress(job_id)
    if not progress:
        raise _error(status.HTTP_404_NOT_FOUND, 'ingestion_job_not_found', f'No ingestion job found for {job_id}')
    return progress


@app.post('/ingest', response_model=IngestResponse, responses={400: {'model': ErrorResponse}, 500: {'model': ErrorResponse}})
async def ingest_docs(req: IngestRequest) -> IngestResponse:
    try:
        return await ingestion.ingest(req)
    except ValueError as exc:
        raise _error(status.HTTP_400_BAD_REQUEST, 'invalid_ingest_request', str(exc))
    except Exception as exc:
        raise _error(status.HTTP_500_INTERNAL_SERVER_ERROR, 'ingestion_failed', str(exc))


@app.post('/reindex', response_model=IngestResponse, responses={400: {'model': ErrorResponse}, 500: {'model': ErrorResponse}})
async def reindex(req: IngestRequest) -> IngestResponse:
    try:
        return await ingestion.ingest(req.model_copy(update={'force': True}))
    except ValueError as exc:
        raise _error(status.HTTP_400_BAD_REQUEST, 'invalid_reindex_request', str(exc))
    except Exception as exc:
        raise _error(status.HTTP_500_INTERNAL_SERVER_ERROR, 'reindex_failed', str(exc))


@app.post('/query', response_model=QueryResponse, responses={400: {'model': ErrorResponse}, 500: {'model': ErrorResponse}})
async def query(req: QueryRequest) -> QueryResponse:
    try:
        results = await retriever.search(
            req.query,
            req.limit,
            req.repo_name,
            req.mode,
            req.language,
            req.section,
            req.heading,
        )
        return QueryResponse(results=results)
    except ValueError as exc:
        raise _error(status.HTTP_400_BAD_REQUEST, 'invalid_query_request', str(exc))
    except Exception as exc:
        raise _error(status.HTTP_500_INTERNAL_SERVER_ERROR, 'query_failed', str(exc))


def _error(status_code: int, code: str, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=ErrorResponse(error='request_failed', detail=detail, code=code).model_dump())
