from __future__ import annotations

import hashlib
import re
import uuid

from core.config import get_settings
from core.models import ChunkType, DocumentChunk, ParsedDocument, ParsedSection


def token_count(text: str) -> int:
    return max(1, len(re.findall(r"\w+|[^\w\s]", text)))


class SemanticChunker:
    """Chunk by document structure first, then by semantic block boundaries."""

    def __init__(self, min_tokens: int | None = None, max_tokens: int | None = None, overlap: int | None = None):
        settings = get_settings()
        self.min_tokens = min_tokens or settings.chunk_min_tokens
        self.max_tokens = max_tokens or settings.chunk_max_tokens
        self.overlap = overlap or settings.chunk_overlap_tokens

    def chunk(self, doc: ParsedDocument) -> list[DocumentChunk]:
        sections = doc.sections or [ParsedSection(title=None, content=doc.text, kind='document')]
        source_hash = doc.metadata.get('source_hash') or hashlib.sha256(doc.text.encode()).hexdigest()
        chunks: list[DocumentChunk] = []
        for section in sections:
            chunks.extend(self._chunk_section(doc, section, source_hash))
        for index, chunk in enumerate(chunks):
            chunk.prev_chunk_id = chunks[index - 1].id if index else None
            chunk.next_chunk_id = chunks[index + 1].id if index + 1 < len(chunks) else None
        return chunks

    def _chunk_section(self, doc: ParsedDocument, section: ParsedSection, source_hash: str) -> list[DocumentChunk]:
        blocks = self._split_blocks(section.content)
        emitted: list[DocumentChunk] = []
        current_blocks: list[str] = []
        for block in blocks:
            current_text = '\n\n'.join(current_blocks + [block]).strip()
            if current_blocks and token_count(current_text) > self.max_tokens:
                emitted.append(self._build_chunk(doc, section, '\n\n'.join(current_blocks).strip(), source_hash, len(emitted)))
                current_blocks = self._overlap_blocks(current_blocks) + [block]
                continue
            current_blocks.append(block)
        if current_blocks:
            emitted.append(self._build_chunk(doc, section, '\n\n'.join(current_blocks).strip(), source_hash, len(emitted)))
        return self._rebalance_small_chunks(doc, section, source_hash, emitted)

    def _rebalance_small_chunks(
        self,
        doc: ParsedDocument,
        section: ParsedSection,
        source_hash: str,
        chunks: list[DocumentChunk],
    ) -> list[DocumentChunk]:
        if len(chunks) < 2:
            return chunks
        rebalanced: list[DocumentChunk] = []
        buffer_text = ''
        for chunk in chunks:
            if token_count(chunk.text) >= self.min_tokens or not rebalanced:
                if buffer_text:
                    merged = f'{buffer_text}\n\n{chunk.text}'.strip()
                    chunk = self._build_chunk(doc, section, merged, source_hash, len(rebalanced))
                    buffer_text = ''
                rebalanced.append(chunk)
            else:
                buffer_text = f'{buffer_text}\n\n{chunk.text}'.strip()
        if buffer_text and rebalanced:
            merged = f'{rebalanced[-1].text}\n\n{buffer_text}'.strip()
            rebalanced[-1] = self._build_chunk(doc, section, merged, source_hash, len(rebalanced) - 1)
        return rebalanced

    def _split_blocks(self, text: str) -> list[str]:
        blocks: list[str] = []
        parts = re.split(r'(```[\s\S]*?```)', text)
        for part in parts:
            if not part.strip():
                continue
            if part.strip().startswith('```'):
                blocks.append(part.strip())
                continue
            paragraphs = [paragraph.strip() for paragraph in re.split(r'\n\s*\n', part) if paragraph.strip()]
            blocks.extend(paragraphs)
        return blocks or [text]

    def _overlap_blocks(self, blocks: list[str]) -> list[str]:
        if not blocks:
            return []
        overlap_blocks: list[str] = []
        overlap_tokens = 0
        for block in reversed(blocks):
            overlap_blocks.insert(0, block)
            overlap_tokens += token_count(block)
            if overlap_tokens >= self.overlap:
                break
        return overlap_blocks

    def _build_chunk(
        self,
        doc: ParsedDocument,
        section: ParsedSection,
        text: str,
        source_hash: str,
        index: int,
    ) -> DocumentChunk:
        normalized = text.strip()
        chunk_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'{doc.path}:{source_hash}:{section.title}:{index}:{normalized[:128]}'))
        hierarchy = section.hierarchy or ([section.title] if section.title else [])
        chunk_type = self._chunk_type(doc, section, normalized)
        ingestion_timestamp = doc.metadata.get('ingestion_timestamp')
        return DocumentChunk(
            id=chunk_id,
            repo=doc.repo_name,
            path=doc.metadata.get('file_path', doc.path),
            language=doc.language,
            section=section.title or (hierarchy[-1] if hierarchy else None),
            heading_hierarchy=hierarchy,
            section_hierarchy=hierarchy,
            chunk_type=chunk_type,
            text=normalized,
            token_count=token_count(normalized),
            headings=doc.headings,
            symbols=doc.symbols,
            imports=doc.imports,
            related_sections=section.related_sections or doc.metadata.get('related_sections', []),
            framework_type=doc.framework_type,
            classes=doc.metadata.get('classes') or doc.classes or [],
            api_routes=doc.metadata.get('api_routes') or doc.api_routes or [],
            http_calls=doc.metadata.get('http_calls') or doc.http_calls or [],
            dependencies=doc.metadata.get('dependencies') or doc.dependencies or [],
            ingestion_timestamp=ingestion_timestamp,
            source_hash=source_hash,
        )

    def _chunk_type(self, doc: ParsedDocument, section: ParsedSection, text: str) -> ChunkType:
        if section.kind == 'architecture':
            return ChunkType.architecture
        if section.kind == 'config':
            return ChunkType.config
        if text.startswith('```') or doc.language not in {'markdown', 'html', 'pdf', 'text', None}:
            return ChunkType.code
        if doc.language in {'markdown', 'html', 'pdf'}:
            return ChunkType(doc.language)
        return ChunkType.mixed
