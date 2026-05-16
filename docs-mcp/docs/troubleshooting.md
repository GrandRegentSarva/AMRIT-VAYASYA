# Troubleshooting

## `ModuleNotFoundError`

Cause:

- local virtual environment is incomplete or using the wrong Python version

Fix:

- use Python 3.11+
- reinstall with `pip install -r requirements.txt`

## No Results Returned

Check:

- the repository was ingested successfully
- `repo_name` matches the indexed repository
- filters are not too restrictive

Use:

- `GET /ingest/{job_id}` to confirm indexing completed
- `GET /collections` to confirm Qdrant is reachable

## Duplicate or Stale Results

The ingestion manifest and chunk deletion logic remove stale chunks during reindex. If you still see stale data:

- run `POST /reindex` with `force=true`
- remove `data/index_manifest.json`
- re-run ingestion

## Tree-sitter Extraction Missing

The parser falls back to deterministic extraction when Tree-sitter packages are unavailable. Verify:

- `tree-sitter`
- `tree-sitter-languages`

## Large Repository Memory Pressure

Tune:

- `INGEST_BATCH_CHUNKS`
- `BATCH_SIZE`
- `CHUNK_MAX_TOKENS`
