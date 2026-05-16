from __future__ import annotations
import re
from pathlib import Path
from core.models import ParsedDocument, ParsedSection

DOC_EXTENSIONS = {'.md', '.mdx', '.rst', '.txt', '.html', '.htm', '.pdf'}

class DocumentParser:
    """Docling-first parser for documentation with robust local fallbacks."""
    def parse(self, path: str | Path, repo_name: str | None = None) -> ParsedDocument:
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix in {'.html', '.htm'}:
            return self._parse_html(p, repo_name)
        if suffix == '.pdf':
            return self._parse_pdf(p, repo_name)
        return self._parse_markdown_like(p, repo_name)

    def _parse_markdown_like(self, p: Path, repo_name: str | None) -> ParsedDocument:
        text = p.read_text(encoding='utf-8', errors='ignore')
        headings = [m.group(2).strip() for m in re.finditer(r'^(#{1,6})\s+(.+)$', text, re.M)]
        code_blocks = re.findall(r'```[\w+-]*\n(.*?)```', text, re.S)
        tables = [line for line in text.splitlines() if '|' in line and re.search(r'\w', line)]
        sections = self._markdown_sections(text)
        return ParsedDocument(repo_name=repo_name, path=str(p), language='markdown', text=text,
                              headings=headings, sections=sections, code_blocks=code_blocks, tables=tables,
                              metadata=self._document_metadata(p, headings, sections))

    def _parse_html(self, p: Path, repo_name: str | None) -> ParsedDocument:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(p.read_text(encoding='utf-8', errors='ignore'), 'html.parser')
        headings = [h.get_text(' ', strip=True) for h in soup.find_all(re.compile('^h[1-6]$'))]
        code_blocks = [c.get_text('\n', strip=True) for c in soup.find_all(['pre', 'code'])]
        tables = [t.get_text(' ', strip=True) for t in soup.find_all('table')]
        text = soup.get_text('\n', strip=True)
        sections = self._html_sections(soup, text)
        return ParsedDocument(repo_name=repo_name, path=str(p), language='html', text=text,
                              headings=headings, sections=sections, code_blocks=code_blocks, tables=tables,
                              metadata=self._document_metadata(p, headings, sections))

    def _parse_pdf(self, p: Path, repo_name: str | None) -> ParsedDocument:
        text = ''
        try:
            from docling.document_converter import DocumentConverter
            result = DocumentConverter().convert(str(p))
            text = result.document.export_to_markdown()
        except Exception:
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(p))
                text = '\n'.join(page.extract_text() or '' for page in reader.pages)
            except Exception as exc:
                text = f'[PDF parsing failed: {exc}]'
        headings = [line.strip('# ').strip() for line in text.splitlines() if line.startswith('#')]
        sections = self._markdown_sections(text)
        return ParsedDocument(repo_name=repo_name, path=str(p), language='pdf', text=text, headings=headings,
                              sections=sections, metadata=self._document_metadata(p, headings, sections))

    def _markdown_sections(self, text: str) -> list[ParsedSection]:
        lines = text.splitlines()
        matches = list(re.finditer(r'^(#{1,6})\s+(.+)$', text, re.M))
        if not matches:
            return [ParsedSection(content=text, kind='document', line_end=max(1, len(lines)))]
        sections: list[ParsedSection] = []
        hierarchy: list[str] = []
        for index, match in enumerate(matches):
            level = len(match.group(1))
            title = match.group(2).strip()
            hierarchy = hierarchy[:level - 1] + [title]
            start_line = text[:match.start()].count('\n') + 1
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            end_line = text[:end].count('\n') + 1
            body = text[match.end():end].strip()
            kind = self._classify_section(title, body)
            related = [heading for heading in hierarchy[:-1] if heading]
            sections.append(ParsedSection(
                title=title,
                level=level,
                content=((match.group(0) + '\n' + body).strip()),
                kind=kind,
                line_start=start_line,
                line_end=end_line,
                hierarchy=list(hierarchy),
                related_sections=related,
            ))
        return sections

    def _html_sections(self, soup, text: str) -> list[ParsedSection]:
        sections: list[ParsedSection] = []
        hierarchy: list[str] = []
        for heading in soup.find_all(re.compile('^h[1-6]$')):
            level = int(heading.name[1])
            title = heading.get_text(' ', strip=True)
            hierarchy = hierarchy[:level - 1] + [title]
            body_parts = []
            sibling = heading.next_sibling
            while sibling and not getattr(sibling, 'name', '').startswith('h'):
                if hasattr(sibling, 'get_text'):
                    body_parts.append(sibling.get_text(' ', strip=True))
                sibling = sibling.next_sibling
            body = '\n'.join(part for part in body_parts if part).strip()
            sections.append(ParsedSection(
                title=title,
                level=level,
                content=((title + '\n' + body).strip()),
                kind=self._classify_section(title, body),
                line_end=max(1, len(text.splitlines())),
                hierarchy=list(hierarchy),
                related_sections=hierarchy[:-1],
            ))
        if sections:
            return sections
        return [ParsedSection(content=text, kind='document', line_end=max(1, len(text.splitlines())))]

    def _classify_section(self, title: str | None, body: str) -> str:
        label = f'{title or ""} {body[:200]}'.lower()
        if any(term in label for term in {'architecture', 'design', 'component', 'module'}):
            return 'architecture'
        if any(term in label for term in {'config', 'configuration', 'settings', '.env'}):
            return 'config'
        if '```' in body:
            return 'code'
        return 'section'

    def _document_metadata(self, path: Path, headings: list[str], sections: list[ParsedSection]) -> dict:
        return {
            'readme_structure': headings if path.name.lower().startswith('readme') else [],
            'architecture_sections': [section.title for section in sections if section.kind == 'architecture' and section.title],
            'config_sections': [section.title for section in sections if section.kind == 'config' and section.title],
        }
