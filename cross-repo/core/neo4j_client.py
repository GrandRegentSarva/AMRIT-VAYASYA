from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase

from config import get_settings


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

    def upsert_endpoint(self, method: str, path: str, handler_class_id: str | None, repo: str) -> None:
        uid = f'{method.upper()}::{path}'
        with self._driver.session() as session:
            session.run(
                '''
                MERGE (e:Endpoint {id: $uid})
                SET e.method = $method, e.path = $path, e.repo = $repo
                ''',
                uid=uid, method=method.upper(), path=path, repo=repo,
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
        with self._driver.session() as session:
            session.run(
                '''
                MERGE (h:HttpCall {id: $uid})
                SET h.method = $method, h.path = $path, h.repo = $repo
                ''',
                uid=uid, method=method.upper(), path=path, repo=repo,
            )
            if caller_class_id:
                session.run(
                    '''
                    MATCH (h:HttpCall {id: $hid}), (c:Class {id: $cid})
                    MERGE (h)<-[:MAKES]-(c)
                    ''',
                    hid=uid, cid=caller_class_id,
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
        """Match HttpCall nodes to Endpoint nodes by method + path and create RESOLVES_TO edges."""
        with self._driver.session() as session:
            result = session.run(
                '''
                MATCH (h:HttpCall), (e:Endpoint)
                WHERE h.method = e.method AND (
                    e.path = h.path OR
                    e.path ENDS WITH h.path OR
                    h.path ENDS WITH e.path
                )
                MERGE (h)-[:RESOLVES_TO]->(e)
                RETURN count(*) AS linked
                '''
            )
            record = result.single()
            return record['linked'] if record else 0

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
