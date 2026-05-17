from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase

from config import get_settings
from core.route_normalizer import normalize_route, routes_match


class Neo4jClient:
    """Thin wrapper around the Neo4j driver exposing domain-specific upsert and query methods."""

    def __init__(self) -> None:
        s = get_settings()
        self._driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))

    def close(self) -> None:
        self._driver.close()

    # ------------------------------------------------------------------
    # Schema & constraints
    # ------------------------------------------------------------------

    def ensure_constraints(self) -> None:
        queries = [
            'CREATE CONSTRAINT repo_name IF NOT EXISTS FOR (r:Repo) REQUIRE r.name IS UNIQUE',
            'CREATE CONSTRAINT file_path IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE',
            'CREATE CONSTRAINT class_id IF NOT EXISTS FOR (c:Class) REQUIRE c.id IS UNIQUE',
            'CREATE CONSTRAINT endpoint_id IF NOT EXISTS FOR (e:Endpoint) REQUIRE e.id IS UNIQUE',
            'CREATE CONSTRAINT unresolved_id IF NOT EXISTS FOR (u:UnresolvedDependency) REQUIRE u.id IS UNIQUE',
        ]
        with self._driver.session() as session:
            for q in queries:
                try:
                    session.run(q)
                except Exception:
                    pass  # constraint may already exist in older Neo4j versions

    # ------------------------------------------------------------------
    # Node upserts
    # ------------------------------------------------------------------

    def upsert_repo(self, name: str) -> None:
        with self._driver.session() as session:
            session.run('MERGE (r:Repo {name: $name})', name=name)

    def upsert_file(self, path: str, repo: str, language: str | None, framework: str | None) -> None:
        with self._driver.session() as session:
            session.run(
                '''
                MERGE (f:File {path: $path})
                SET f.language = $language, f.framework = $framework
                WITH f
                MATCH (r:Repo {name: $repo})
                MERGE (f)-[:BELONGS_TO]->(r)
                ''',
                path=path, repo=repo, language=language or '', framework=framework or '',
            )

    def upsert_class(self, name: str, kind: str, file_path: str, repo: str) -> None:
        """kind: controller | service | repository | component | unknown"""
        uid = f'{repo}::{file_path}::{name}'
        with self._driver.session() as session:
            session.run(
                '''
                MERGE (c:Class {id: $uid})
                SET c.name = $name, c.kind = $kind, c.repo = $repo
                WITH c
                MATCH (f:File {path: $file_path})
                MERGE (c)-[:DEFINED_IN]->(f)
                ''',
                uid=uid, name=name, kind=kind, repo=repo, file_path=file_path,
            )

    def upsert_endpoint(
        self,
        method: str,
        path: str,
        handler_class_id: str | None,
        repo: str,
        request_dto: str | None = None,
        response_dto: str | None = None,
    ) -> None:
        uid = f'{method.upper()}::{path}'
        norm_path = normalize_route(path)
        with self._driver.session() as session:
            session.run(
                '''
                MERGE (e:Endpoint {id: $uid})
                SET e.method = $method,
                    e.path = $path,
                    e.normalized_path = $norm_path,
                    e.repo = $repo,
                    e.request_dto = $request_dto,
                    e.response_dto = $response_dto
                ''',
                uid=uid, method=method.upper(), path=path,
                norm_path=norm_path, repo=repo,
                request_dto=request_dto or '',
                response_dto=response_dto or '',
            )
            if handler_class_id:
                session.run(
                    '''
                    MATCH (e:Endpoint {id: $eid}), (c:Class {id: $cid})
                    MERGE (e)<-[:HANDLES]-(c)
                    ''',
                    eid=uid, cid=handler_class_id,
                )

    def upsert_http_call(self, method: str, path: str, caller_class_id: str | None, repo: str) -> None:
        uid = f'call::{repo}::{method.upper()}::{path}'
        norm_path = normalize_route(path)
        with self._driver.session() as session:
            session.run(
                '''
                MERGE (h:HttpCall {id: $uid})
                SET h.method = $method,
                    h.path = $path,
                    h.normalized_path = $norm_path,
                    h.repo = $repo
                ''',
                uid=uid, method=method.upper(), path=path,
                norm_path=norm_path, repo=repo,
            )
            if caller_class_id:
                session.run(
                    '''
                    MATCH (h:HttpCall {id: $hid}), (c:Class {id: $cid})
                    MERGE (h)<-[:MAKES]-(c)
                    ''',
                    hid=uid, cid=caller_class_id,
                )

    def upsert_unresolved_dependency(self, name: str, dep_type: str, context: str, source_class_id: str) -> None:
        """Create an UnresolvedDependency node for dead ends in the dependency chain."""
        uid = f'unresolved::{name}'
        with self._driver.session() as session:
            session.run(
                '''
                MERGE (u:UnresolvedDependency {id: $uid})
                SET u.name = $name, u.dep_type = $dep_type, u.context = $context
                WITH u
                MATCH (c:Class {id: $cid})
                MERGE (c)-[:DEPENDS_ON_EXTERNAL]->(u)
                ''',
                uid=uid, name=name, dep_type=dep_type, context=context, cid=source_class_id,
            )

    def link_dependencies(self, class_id: str, dep_names: list[str], repo: str) -> None:
        """Create DEPENDS_ON edges between a class and its injected dependencies by name."""
        with self._driver.session() as session:
            for dep in dep_names:
                session.run(
                    '''
                    MATCH (src:Class {id: $src_id})
                    MATCH (dep:Class {name: $dep_name, repo: $repo})
                    MERGE (src)-[:DEPENDS_ON]->(dep)
                    ''',
                    src_id=class_id, dep_name=dep, repo=repo,
                )

    def link_http_calls_to_endpoints(self) -> int:
        """
        Match HttpCall nodes to Endpoint nodes using normalised routes and create
        RESOLVES_TO edges with evidence contract metadata (match quality, confidence).
        """
        with self._driver.session() as session:
            # Pull all http calls and endpoints into Python for normalised comparison
            calls = session.run('MATCH (h:HttpCall) RETURN h.id AS id, h.method AS method, h.path AS path, h.normalized_path AS norm_path').data()
            endpoints = session.run('MATCH (e:Endpoint) RETURN e.id AS id, e.method AS method, e.path AS path, e.normalized_path AS norm_path').data()

        linked = 0
        with self._driver.session() as session:
            for call in calls:
                for ep in endpoints:
                    if call['method'] != ep['method']:
                        continue
                    call_norm = call.get('norm_path') or normalize_route(call.get('path') or '')
                    ep_norm = ep.get('norm_path') or normalize_route(ep.get('path') or '')
                    matched, match_quality = routes_match(call_norm, ep_norm)
                    if matched:
                        confidence = {'exact': 1.0, 'template': 0.85, 'prefix': 0.6}.get(match_quality, 0.4)
                        session.run(
                            '''
                            MATCH (h:HttpCall {id: $hid}), (e:Endpoint {id: $eid})
                            MERGE (h)-[r:RESOLVES_TO]->(e)
                            SET r.match_quality = $match_quality,
                                r.confidence = $confidence
                            ''',
                            hid=call['id'], eid=ep['id'],
                            match_quality=match_quality,
                            confidence=confidence,
                        )
                        linked += 1
        return linked

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def query_all_endpoints(self, repo_name: str | None = None) -> list[dict[str, Any]]:
        cypher = '''
            MATCH (e:Endpoint)
            OPTIONAL MATCH (e)<-[:HANDLES]-(handler:Class)-[:DEFINED_IN]->(f:File)-[:BELONGS_TO]->(r:Repo)
            OPTIONAL MATCH (caller:Class)-[:MAKES]->(h:HttpCall)-[:RESOLVES_TO]->(e)
            OPTIONAL MATCH (caller)-[:DEFINED_IN]->(cf:File)-[:BELONGS_TO]->(cr:Repo)
        '''
        if repo_name:
            cypher += ' WHERE e.repo = $repo_name OR r.name = $repo_name'
        cypher += '''
            RETURN e.method AS method, e.path AS path, e.repo AS endpoint_repo,
                   collect(DISTINCT {name: handler.name, kind: handler.kind, file: f.path, repo: r.name}) AS handlers,
                   collect(DISTINCT {caller: caller.name, file: cf.path, repo: cr.name}) AS frontend_callers
        '''
        with self._driver.session() as session:
            results = session.run(cypher, repo_name=repo_name or '')
            return [dict(r) for r in results]

    def query_trace(self, feature: str) -> list[dict[str, Any]]:
        """Find all endpoints and their full chain related to a feature keyword."""
        cypher = '''
            MATCH (e:Endpoint)
            WHERE toLower(e.path) CONTAINS toLower($feature)
            OPTIONAL MATCH chain=(e)<-[:HANDLES]-(c:Class)-[:DEPENDS_ON*0..5]->(dep:Class)
            OPTIONAL MATCH (caller:Class)-[:MAKES]->(:HttpCall)-[:RESOLVES_TO]->(e)
            OPTIONAL MATCH (caller)-[:DEFINED_IN]->(cf:File)-[:BELONGS_TO]->(cr:Repo)
            OPTIONAL MATCH (c)-[:DEFINED_IN]->(bf:File)-[:BELONGS_TO]->(br:Repo)
            RETURN e.method AS method, e.path AS path,
                   c.name AS handler_class, c.kind AS handler_kind,
                   bf.path AS backend_file, br.name AS backend_repo,
                   [n IN nodes(chain) WHERE n:Class | n.name] AS service_chain,
                   collect(DISTINCT {caller: caller.name, file: cf.path, repo: cr.name}) AS frontend_callers
        '''
        with self._driver.session() as session:
            results = session.run(cypher, feature=feature)
            return [dict(r) for r in results]

    def query_dependencies(self, class_name: str, repo_name: str | None = None) -> list[dict[str, Any]]:
        cypher = '''
            MATCH (c:Class)-[:DEPENDS_ON*1..5]->(dep:Class)
            WHERE c.name = $class_name
        '''
        if repo_name:
            cypher += ' AND c.repo = $repo_name'
        cypher += ' RETURN c.name AS source, collect(dep.name) AS dependencies, c.repo AS repo'
        with self._driver.session() as session:
            results = session.run(cypher, class_name=class_name, repo_name=repo_name or '')
            return [dict(r) for r in results]

    def stats(self) -> dict[str, int]:
        with self._driver.session() as session:
            counts = {}
            for label in ('Repo', 'File', 'Class', 'Endpoint', 'HttpCall'):
                result = session.run(f'MATCH (n:{label}) RETURN count(n) AS c')
                record = result.single()
                counts[label.lower() + 's'] = record['c'] if record else 0
            result = session.run("MATCH ()-[r:RESOLVES_TO]->() RETURN count(r) AS c")
            record = result.single()
            counts['resolved_links'] = record['c'] if record else 0
            return counts
