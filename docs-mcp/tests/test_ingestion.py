import pytest
from pathlib import Path

from apps.ingestion.service import IngestionService
from core.models import IngestRequest


class DummyStore:
    def __init__(self):
        self.upserted = []
        self.deleted = []

    def upsert(self, chunks, vectors):
        self.upserted.extend(chunks)

    def delete(self, chunk_ids):
        self.deleted.extend(chunk_ids)


@pytest.mark.asyncio
async def test_ingestion_is_incremental_and_tracks_progress(tmp_path: Path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'README.md').write_text('# Architecture\n' + ('docs ' * 700))
    service = IngestionService()
    service.data_dir = tmp_path / 'data'
    service.data_dir.mkdir()
    service.manifest = service.data_dir / 'index_manifest.json'
    service.progress_index = service.data_dir / 'ingestion_progress.json'
    service.store = DummyStore()
    service.embedder._failed = True
    first = await service.ingest(IngestRequest(path=str(repo), repo_name='repo', force=True, job_id='job-1'))
    second = await service.ingest(IngestRequest(path=str(repo), repo_name='repo', force=False, job_id='job-2'))
    progress = service.get_progress('job-1')
    assert first.indexed_chunks > 0
    assert second.skipped_files == 1
    assert progress is not None
    assert progress.status == 'completed'
