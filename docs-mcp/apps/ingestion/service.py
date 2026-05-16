from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from git import Repo

from core.chunking.semantic import SemanticChunker
from core.config import get_settings
from core.embeddings.provider import EmbeddingProvider
from core.metadata.enricher import MetadataEnricher
from core.models import IngestRequest, IngestResponse, IngestionProgress
from core.parsing.document_parser import DOC_EXTENSIONS, DocumentParser
from core.parsing.source_parser import SOURCE_EXTENSIONS, SourceParser
from core.qdrant.client import QdrantVectorStore
from core.retrieval.bm25 import bm25_index

SKIP_DIRS = {'.git', 'node_modules', '.venv', 'venv', 'dist', 'build', 'target', '__pycache__'}


class IngestionService:
    def __init__(self):
        self.doc_parser = DocumentParser()
        self.source_parser = SourceParser()
        self.enricher = MetadataEnricher()
        self.chunker = SemanticChunker()
        self.embedder = EmbeddingProvider()
        self.store = QdrantVectorStore()
        self.settings = get_settings()
        self.data_dir = Path(self.settings.local_data_dir)
        self.manifest = self.data_dir / 'index_manifest.json'
        self.progress_index = self.data_dir / 'ingestion_progress.json'
        self.data_dir.mkdir(parents=True, exist_ok=True)

    async def ingest(self, req: IngestRequest) -> IngestResponse:
        root, repo_name = self._resolve_source(req)
        job_id = req.job_id or str(uuid.uuid4())
        root = root.resolve()
        progress = self._start_progress(job_id, repo_name, root)
        manifest = self._load_manifest()
        repo_manifest = manifest.setdefault(repo_name, {'root': str(root), 'files': {}})
        repo_files = repo_manifest.setdefault('files', {})
        seen_files = set()
        parsed = 0
        skipped = 0
        indexed_chunks = 0
        removed_chunks = 0
        batch = []
        try:
            files = list(self._iter_files(root))
            progress.total_files = len(files)
            self._save_progress(progress)
            for path in files:
                rel_path = self._relative_path(path, root)
                seen_files.add(rel_path)
                signature = self._file_signature(path)
                prior = repo_files.get(rel_path)
                if not req.force and prior and prior.get('signature') == signature:
                    skipped += 1
                    progress.skipped_files = skipped
                    progress.updated_at = datetime.now(timezone.utc)
                    self._save_progress(progress)
                    continue
                if prior:
                    chunk_ids = prior.get('chunk_ids', [])
                    self._delete_chunks(chunk_ids)
                    removed_chunks += len(chunk_ids)
                doc = self._parse(path, repo_name)
                doc = self.enricher.enrich(doc, root)
                file_chunks = self.chunker.chunk(doc)
                repo_files[rel_path] = {
                    'signature': signature,
                    'chunk_ids': [chunk.id for chunk in file_chunks],
                }
                batch.extend(file_chunks)
                parsed += 1
                progress.parsed_files = parsed
                progress.indexed_chunks = indexed_chunks + len(batch)
                progress.updated_at = datetime.now(timezone.utc)
                self._save_progress(progress)
                if len(batch) >= self.settings.ingest_batch_chunks:
                    indexed_chunks += await self._index(batch)
                    batch = []
                    progress.indexed_chunks = indexed_chunks
                    progress.updated_at = datetime.now(timezone.utc)
                    self._save_progress(progress)
            stale_files = set(repo_files.keys()) - seen_files
            for stale_file in stale_files:
                chunk_ids = repo_files[stale_file].get('chunk_ids', [])
                self._delete_chunks(chunk_ids)
                removed_chunks += len(chunk_ids)
                del repo_files[stale_file]
            if batch:
                indexed_chunks += await self._index(batch)
            repo_manifest['root'] = str(root)
            self._save_manifest(manifest)
            progress.status = 'completed'
            progress.parsed_files = parsed
            progress.skipped_files = skipped
            progress.indexed_chunks = indexed_chunks
            progress.updated_at = datetime.now(timezone.utc)
            self._save_progress(progress)
            return IngestResponse(
                repo_name=repo_name,
                root=str(root),
                parsed_files=parsed,
                skipped_files=skipped,
                indexed_chunks=indexed_chunks,
                removed_chunks=removed_chunks,
                job_id=job_id,
                status='completed',
            )
        except Exception as exc:
            progress.status = 'failed'
            progress.errors.append(str(exc))
            progress.updated_at = datetime.now(timezone.utc)
            self._save_progress(progress)
            raise

    def get_progress(self, job_id: str) -> IngestionProgress | None:
        progress_map = self._load_progress_index()
        payload = progress_map.get(job_id)
        return IngestionProgress(**payload) if payload else None

    def _resolve_source(self, req: IngestRequest):
        if req.git_url:
            repo_name = req.repo_name or Path(req.git_url.rstrip('/').removesuffix('.git')).name
            dest = self.data_dir / 'repos' / repo_name
            if dest.exists():
                repo = Repo(str(dest))
                repo.remotes.origin.fetch()
                repo.git.checkout(req.branch or repo.active_branch.name)
                repo.remotes.origin.pull()
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                clone_kwargs = {'branch': req.branch} if req.branch else {}
                Repo.clone_from(req.git_url, dest, **clone_kwargs)
            return dest, repo_name
        if not req.path:
            raise ValueError('Either path or git_url is required')
        root = Path(req.path).expanduser().resolve()
        if not root.exists():
            raise ValueError(f'Path does not exist: {root}')
        return root, req.repo_name or root.name

    def _iter_files(self, root: Path):
        for path in root.rglob('*'):
            if any(part in SKIP_DIRS for part in path.parts) or not path.is_file():
                continue
            if path.suffix.lower() in DOC_EXTENSIONS | SOURCE_EXTENSIONS:
                yield path

    def _parse(self, path: Path, repo_name: str):
        if path.suffix.lower() in DOC_EXTENSIONS:
            return self.doc_parser.parse(path, repo_name)
        return self.source_parser.parse(path, repo_name)

    async def _index(self, chunks) -> int:
        vectors = await self.embedder.embed_documents([chunk.text for chunk in chunks])
        self.store.upsert(chunks, vectors)
        bm25_index.add(chunks)
        return len(chunks)

    def _delete_chunks(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        self.store.delete(chunk_ids)
        bm25_index.remove(chunk_ids)

    def _load_manifest(self) -> dict:
        if self.manifest.exists():
            return json.loads(self.manifest.read_text())
        return {}

    def _save_manifest(self, manifest: dict) -> None:
        self.manifest.write_text(json.dumps(manifest, indent=2))

    def _start_progress(self, job_id: str, repo_name: str, root: Path) -> IngestionProgress:
        progress = IngestionProgress(job_id=job_id, status='running', repo_name=repo_name, root=str(root))
        self._save_progress(progress)
        return progress

    def _save_progress(self, progress: IngestionProgress) -> None:
        payload = progress.model_dump(mode='json')
        data = self._load_progress_index()
        data[progress.job_id] = payload
        self.progress_index.write_text(json.dumps(data, indent=2))

    def _load_progress_index(self) -> dict:
        if self.progress_index.exists():
            return json.loads(self.progress_index.read_text())
        return {}

    def _file_signature(self, path: Path) -> str:
        stat = path.stat()
        return f'{stat.st_mtime_ns}:{stat.st_size}'

    def _relative_path(self, path: Path, root: Path) -> str:
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)
