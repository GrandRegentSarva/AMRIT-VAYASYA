from __future__ import annotations

import logging
from typing import Any

from qdrant_client import QdrantClient

from config import get_settings
from core.frontend_extractor import extract_http_calls
from core.neo4j_client import Neo4jClient
from core.service_chain_resolver import extract_dependencies, resolve_class_kind

logger = logging.getLogger(__name__)


class GraphBuilder:
    """
    Reads all indexed chunks from Qdrant and populates a Neo4j graph with:

    Nodes: Repo, File, Class, Endpoint, HttpCall
    Edges: BELONGS_TO, DEFINED_IN, HANDLES, DEPENDS_ON, MAKES, RESOLVES_TO
    """

    def __init__(self) -> None:
        s = get_settings()
        self._qdrant = QdrantClient(url=s.qdrant_url)
        self._collection = s.collection_name
        self._neo4j = Neo4jClient()

    def build(self) -> dict[str, Any]:
        """Rebuild the full cross-repo graph from Qdrant data."""
        self._neo4j.ensure_constraints()
        stats = self._scroll_and_populate()
        linked = self._neo4j.link_http_calls_to_endpoints()
        stats['resolved_links'] = linked
        logger.info('Graph build complete: %s', stats)
        return stats

    def _scroll_and_populate(self) -> dict[str, int]:
        counts = {'repos': 0, 'files': 0, 'classes': 0, 'endpoints': 0, 'http_calls': 0}
        offset = None
        seen_repos: set[str] = set()
        seen_files: set[str] = set()

        while True:
            response, next_offset = self._qdrant.scroll(
                collection_name=self._collection,
                limit=200,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            if not response:
                break

            for point in response:
                payload = point.payload or {}
                self._process_chunk(payload, counts, seen_repos, seen_files)

            if next_offset is None:
                break
            offset = next_offset

        return counts

    def _process_chunk(
        self,
        payload: dict[str, Any],
        counts: dict[str, int],
        seen_repos: set[str],
        seen_files: set[str],
    ) -> None:
        repo = payload.get('repo') or payload.get('repo_name')
        file_path = payload.get('path') or payload.get('file_path')
        language = payload.get('language') or ''
        framework = payload.get('framework_type') or ''
        text = payload.get('text') or ''
        classes = payload.get('classes') or []
        api_routes = payload.get('api_routes') or []
        http_calls_meta = payload.get('http_calls') or []
        dependencies_meta = payload.get('dependencies') or []

        if not repo or not file_path:
            return

        # Repo node
        if repo not in seen_repos:
            self._neo4j.upsert_repo(repo)
            seen_repos.add(repo)
            counts['repos'] += 1

        # File node
        file_key = f'{repo}::{file_path}'
        if file_key not in seen_files:
            self._neo4j.upsert_file(file_path, repo, language, framework)
            seen_files.add(file_key)
            counts['files'] += 1

        # Class nodes
        class_ids: dict[str, str] = {}
        for class_name in classes:
            kind = resolve_class_kind(text, class_name, language)
            self._neo4j.upsert_class(class_name, kind, file_path, repo)
            class_ids[class_name] = f'{repo}::{file_path}::{class_name}'
            counts['classes'] += 1

        # Endpoint nodes (backend routes from api_routes metadata)
        for route in api_routes:
            parts = route.split(' ', 1)
            if len(parts) == 2:
                method, path = parts
                # Try to find the handler class (first controller-kind class in this file)
                handler_id = next(
                    (cid for cname, cid in class_ids.items()
                     if any(k in cname.lower() for k in ('controller', 'resource', 'handler'))),
                    next(iter(class_ids.values()), None),
                )
                self._neo4j.upsert_endpoint(method, path, handler_id, repo)
                counts['endpoints'] += 1

        # HttpCall nodes — from stored metadata AND re-extracted from text
        all_calls = set(http_calls_meta)
        if text and language in ('typescript', 'javascript', 'java'):
            for call in extract_http_calls(text, language):
                all_calls.add(call['raw'])

        for call_raw in all_calls:
            parts = call_raw.split(' ', 1)
            if len(parts) == 2:
                method, path = parts
                # Caller = first component/service class in this file
                caller_id = next(iter(class_ids.values()), None)
                self._neo4j.upsert_http_call(method, path, caller_id, repo)
                counts['http_calls'] += 1

        # Dependency edges
        all_deps = set(dependencies_meta)
        if text and language in ('typescript', 'javascript', 'java'):
            all_deps.update(extract_dependencies(text, language))

        for class_name, class_id in class_ids.items():
            if all_deps:
                self._neo4j.link_dependencies(class_id, list(all_deps), repo)

    def close(self) -> None:
        self._neo4j.close()
