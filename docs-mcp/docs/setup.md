# Setup

## Docker

```bash
cd docs-mcp
cp .env.example .env
docker compose up --build
```

Services:

- API: `http://localhost:8000`
- Qdrant: `http://localhost:6333`
- Redis: `redis://localhost:6379/0`

## Local Development

Requirements:

- Python 3.11+
- Redis
- Qdrant

Install dependencies:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run API:

```bash
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
```

Run worker:

```bash
celery -A apps.worker.celery_app worker --loglevel=INFO
```

## Example Requests

Ingest:

```bash
curl -X POST http://localhost:8000/ingest \
  -H 'Content-Type: application/json' \
  -d '{"path":"/data/sample-docs","repo_name":"sample","force":true}'
```

Query:

```bash
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"How does ingestion work?","repo_name":"sample","limit":5,"mode":"hybrid"}'
```
