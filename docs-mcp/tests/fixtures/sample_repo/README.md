# Sample Service

## Architecture

This service ingests markdown and source files for retrieval.

## Configuration

Set `QDRANT_URL` and `REDIS_URL` before startup.

## API

```python
@app.get("/health")
def health():
    return {"status": "ok"}
```
