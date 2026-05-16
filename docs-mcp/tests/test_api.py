from fastapi.testclient import TestClient

from apps.api.main import app
from core.models import IngestResponse, IngestionProgress, SearchResult


class DummyIngestionService:
    async def ingest(self, req):
        return IngestResponse(
            repo_name=req.repo_name or 'repo',
            root=req.path or '/tmp/repo',
            parsed_files=1,
            skipped_files=0,
            indexed_chunks=2,
            removed_chunks=0,
            job_id=req.job_id or 'job-1',
            status='completed',
        )

    def get_progress(self, job_id: str):
        return IngestionProgress(job_id=job_id, status='completed', repo_name='repo', root='/tmp/repo', parsed_files=1)

    @property
    def store(self):
        class _Store:
            def collections(self):
                return ['docs_chunks']
        return _Store()


class DummyRetriever:
    async def search(self, *args, **kwargs):
        return [
            SearchResult(
                chunk_id='1',
                score=1.2,
                normalized_score=0.8,
                rerank_score=1.2,
                confidence='high',
                text='Architecture overview',
                metadata={'path': 'README.md', 'section_hierarchy': ['Architecture']},
                source='repo:README.md#Architecture',
            )
        ]


def test_api_endpoints(monkeypatch):
    from apps.api import main as api_main
    monkeypatch.setattr(api_main, 'ingestion', DummyIngestionService())
    monkeypatch.setattr(api_main, 'retriever', DummyRetriever())
    client = TestClient(app)
    assert client.get('/health').status_code == 200
    assert client.get('/collections').json() == {'collections': ['docs_chunks']}
    ingest_response = client.post('/ingest', json={'path': '/tmp/repo', 'repo_name': 'repo'})
    assert ingest_response.status_code == 200
    query_response = client.post('/query', json={'query': 'architecture', 'repo_name': 'repo'})
    assert query_response.status_code == 200
    assert query_response.json()['results'][0]['confidence'] == 'high'
