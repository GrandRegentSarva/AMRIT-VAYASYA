from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator

class ChunkType(str, Enum):
    markdown = 'markdown'
    code = 'code'
    table = 'table'
    html = 'html'
    pdf = 'pdf'
    architecture = 'architecture'
    config = 'config'
    mixed = 'mixed'

class ParsedSection(BaseModel):
    title: str | None = None
    level: int = 1
    content: str
    kind: str = 'section'
    line_start: int = 1
    line_end: int = 1
    hierarchy: list[str] = Field(default_factory=list)
    related_sections: list[str] = Field(default_factory=list)

class ParsedDocument(BaseModel):
    repo_name: str | None = None
    path: str
    language: str | None = None
    text: str
    headings: list[str] = Field(default_factory=list)
    sections: list[ParsedSection] = Field(default_factory=list)
    code_blocks: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)
    classes: list[str] = Field(default_factory=list)
    functions: list[str] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)
    decorators: list[str] = Field(default_factory=list)
    annotations: list[str] = Field(default_factory=list)
    comments: list[str] = Field(default_factory=list)
    docstrings: list[str] = Field(default_factory=list)
    api_routes: list[str] = Field(default_factory=list)
    http_calls: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    framework_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class DocumentChunk(BaseModel):
    id: str
    repo: str | None = None
    path: str
    language: str | None = None
    section: str | None = None
    heading_hierarchy: list[str] = Field(default_factory=list)
    section_hierarchy: list[str] = Field(default_factory=list)
    chunk_type: ChunkType = ChunkType.mixed
    text: str
    token_count: int
    headings: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)
    related_sections: list[str] = Field(default_factory=list)
    framework_type: str | None = None
    classes: list[str] = Field(default_factory=list)
    api_routes: list[str] = Field(default_factory=list)
    http_calls: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    ingestion_timestamp: datetime = Field(default_factory=datetime.utcnow)
    prev_chunk_id: str | None = None
    next_chunk_id: str | None = None
    source_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def payload(self) -> dict[str, Any]:
        data = self.model_dump(mode='json')
        data['repo'] = self.repo
        data['path'] = self.path
        return data

class SearchResult(BaseModel):
    chunk_id: str
    score: float
    normalized_score: float = 0.0
    rerank_score: float = 0.0
    confidence: str = 'low'
    text: str
    metadata: dict[str, Any]
    source: str

class IngestRequest(BaseModel):
    path: str | None = None
    git_url: str | None = None
    repo_name: str | None = None
    branch: str | None = None
    force: bool = False
    job_id: str | None = None

    @model_validator(mode='after')
    def validate_source(self):
        if not self.path and not self.git_url:
            raise ValueError('Either path or git_url is required')
        return self

class QueryRequest(BaseModel):
    query: str
    repo_name: str | None = None
    limit: int = 10
    mode: str = 'hybrid'
    language: str | None = None
    section: str | None = None
    heading: str | None = None

    @field_validator('limit')
    @classmethod
    def validate_limit(cls, value: int) -> int:
        if value < 1 or value > 25:
            raise ValueError('limit must be between 1 and 25')
        return value

    @field_validator('mode')
    @classmethod
    def validate_mode(cls, value: str) -> str:
        if value not in {'hybrid', 'dense', 'keyword'}:
            raise ValueError("mode must be one of 'hybrid', 'dense', or 'keyword'")
        return value

class ErrorResponse(BaseModel):
    error: str
    detail: str
    code: str

class IngestionProgress(BaseModel):
    job_id: str
    status: str
    repo_name: str | None = None
    root: str | None = None
    parsed_files: int = 0
    skipped_files: int = 0
    total_files: int = 0
    indexed_chunks: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    errors: list[str] = Field(default_factory=list)

class IngestResponse(BaseModel):
    repo_name: str
    root: str
    parsed_files: int
    skipped_files: int
    indexed_chunks: int
    removed_chunks: int = 0
    job_id: str
    status: str

class QueryResponse(BaseModel):
    results: list[SearchResult]

class CollectionResponse(BaseModel):
    collections: list[str]

class HealthResponse(BaseModel):
    status: str
    qdrant_configured: bool
    redis_configured: bool
