from pathlib import Path

from core.parsing.document_parser import DocumentParser
from core.parsing.source_parser import SourceParser


def test_markdown_parser_extracts_architecture_and_config_sections(tmp_path: Path):
    path = tmp_path / 'README.md'
    path.write_text('# Root\n## Architecture\nsystem layout\n## Configuration\nset env vars\n')
    doc = DocumentParser().parse(path, 'repo')
    kinds = [section.kind for section in doc.sections]
    assert 'architecture' in kinds
    assert 'config' in kinds
    assert doc.metadata['architecture_sections'] == ['Architecture']


def test_python_source_parser_extracts_framework_routes_and_docstrings(tmp_path: Path):
    path = tmp_path / 'app.py'
    path.write_text(
        'from fastapi import FastAPI\n'
        'app = FastAPI()\n'
        '@app.get("/health")\n'
        'def health() -> dict:\n'
        '    """Health endpoint."""\n'
        '    return {"status": "ok"}\n'
    )
    doc = SourceParser().parse(path, 'repo')
    assert doc.framework_type == 'fastapi'
    assert 'health' in doc.functions
    assert 'GET /health' in doc.api_routes
    assert doc.docstrings == ['Health endpoint.']


def test_typescript_parser_detects_angular_interface_and_comments(tmp_path: Path):
    path = tmp_path / 'app.ts'
    path.write_text(
        'import { NgModule } from "@angular/core";\n'
        '// app module\n'
        '@NgModule({})\n'
        'export interface Config {}\n'
        'export function bootstrap() {}\n'
    )
    doc = SourceParser().parse(path, 'repo')
    assert doc.framework_type == 'angular'
    assert 'Config' in doc.interfaces
    assert doc.comments
