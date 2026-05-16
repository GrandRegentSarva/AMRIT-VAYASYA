from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from core.models import ParsedDocument

class MetadataEnricher:
    def enrich(self, doc: ParsedDocument, root: str | Path | None = None) -> ParsedDocument:
        p = Path(doc.path)
        rel = str(p)
        if root:
            try: rel = str(p.relative_to(Path(root)))
            except ValueError: pass
        related_sections = []
        if doc.sections:
            titles = [section.title for section in doc.sections if section.title]
            related_sections = titles[:25]
        ingestion_timestamp = datetime.now(timezone.utc).isoformat()
        doc.metadata.update({
            'repo_name': doc.repo_name,
            'file_path': rel,
            'language': doc.language,
            'chunk_type': 'code' if doc.language not in {'markdown', 'html', 'pdf', 'text', None} else doc.language or 'mixed',
            'section_hierarchy': [section.hierarchy for section in doc.sections if section.hierarchy],
            'headings': doc.headings,
            'related_sections': related_sections,
            'symbols': doc.symbols,
            'imports': doc.imports,
            'classes': doc.classes,
            'functions': doc.functions,
            'interfaces': doc.interfaces,
            'decorators': doc.decorators,
            'annotations': doc.annotations,
            'comments': doc.comments[:50],
            'docstrings': doc.docstrings[:25],
            'api_routes': doc.api_routes,
            'framework_type': doc.framework_type,
            'source_hash': hashlib.sha256(doc.text.encode('utf-8')).hexdigest(),
            'ingestion_timestamp': ingestion_timestamp,
            'is_readme': p.name.lower().startswith('readme'),
            'is_architecture_doc': any(k in str(p).lower() for k in ['architecture','design','adr','docs']),
            'is_config_doc': any(k in str(p).lower() for k in ['config', 'settings', 'env', 'deployment']),
        })
        return doc
