# Ingestion Pipeline

## Flow

1. Resolve input source from `path` or `git_url`.
2. Enumerate supported files while skipping build and cache directories.
3. Compare file signatures against the ingestion manifest.
4. Remove stale chunks for changed or deleted files.
5. Parse source and documentation into structured `ParsedDocument` objects.
6. Enrich metadata with repo, relative path, hierarchy, framework hints, and ingestion timestamps.
7. Chunk the document using semantic sections and code boundaries.
8. Batch embeddings and upsert vectors into Qdrant.
9. Update BM25 state with the same chunk ids.
10. Persist ingestion manifest and job progress.

## Deduplication Strategy

- File signatures use `mtime_ns:size`.
- Chunk ids are deterministic UUIDv5 values derived from path, source hash, section, and content.
- Reindexing removes previous chunk ids from both Qdrant and BM25 before reinserting updated chunks.
- Deleted files are removed from the manifest and vector store during every ingestion run.

## Progress Tracking

- Each ingestion request gets a `job_id`.
- Progress is persisted to `data/ingestion_progress.json`.
- The API exposes `GET /ingest/{job_id}` for progress polling.
