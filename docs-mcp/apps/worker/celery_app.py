from __future__ import annotations
import asyncio
from celery import Celery
from core.config import get_settings
from core.models import IngestRequest
from apps.ingestion.service import IngestionService

settings=get_settings()
celery_app=Celery('docs_mcp', broker=settings.redis_url, backend=settings.redis_url)

@celery_app.task(
    name='docs_mcp.ingest',
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
)
def ingest_task(payload: dict):
    return asyncio.run(IngestionService().ingest(IngestRequest(**payload)))
