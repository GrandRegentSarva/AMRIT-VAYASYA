from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from core.models import ParsedDocument, ParsedSection

SOURCE_EXTENSIONS = {
    '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs', '.rb', '.php', '.cs', '.cpp', '.c', '.h'
}
LANG_BY_EXT = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.jsx': 'javascript',
    '.java': 'java',
    '.go': 'go',
    '.rs': 'rust',
}
TREE_SITTER_LANGUAGE_NAMES = {
    'python': 'python',
    'javascript': 'javascript',
    'typescript': 'typescript',
    'java': 'java',
    'go': 'go',
}


class SourceParser:
    """Syntax-aware source parser with Tree-sitter support and deterministic fallbacks."""

    def parse(self, path: str | Path, repo_name: str | None = None) -> ParsedDocument:
        p = Path(path)
        text = p.read_text(encoding='utf-8', errors='ignore')
        lang = LANG_BY_EXT.get(p.suffix.lower(), p.suffix.lower().lstrip('.') or 'text')
        framework = self._detect_framework(text, lang)
        if lang == 'python':
            return self._parse_python(p, text, repo_name, framework)
        tree_result = self._parse_with_tree_sitter(text, lang)
        if tree_result:
            return self._build_document(p, text, repo_name, lang, framework, tree_result)
        return self._parse_regex(p, text, repo_name, lang, framework)

    def _parse_python(
        self,
        path: Path,
        text: str,
        repo_name: str | None,
        framework: str | None,
    ) -> ParsedDocument:
        imports: list[str] = []
        classes: list[str] = []
        functions: list[str] = []
        interfaces: list[str] = []
        decorators: list[str] = []
        annotations: list[str] = []
        comments = self._extract_comments(text, 'python')
        docstrings: list[str] = []
        routes: list[str] = []
        sections: list[ParsedSection] = []
        try:
            tree = ast.parse(text)
            module_docstring = ast.get_docstring(tree)
            if module_docstring:
                docstrings.append(module_docstring)
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imports.append(ast.unparse(node) if hasattr(ast, 'unparse') else type(node).__name__)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                    decorators.extend(self._python_decorators(node.decorator_list))
                    class_docstring = ast.get_docstring(node)
                    if class_docstring:
                        docstrings.append(class_docstring)
                    sections.append(self._node_section(text, node, node.name, 'class'))
                    if node.name.endswith('Protocol'):
                        interfaces.append(node.name)
                    for child in node.body:
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            method_name = f'{node.name}.{child.name}'
                            functions.append(method_name)
                            decorators.extend(self._python_decorators(child.decorator_list))
                            method_docstring = ast.get_docstring(child)
                            if method_docstring:
                                docstrings.append(method_docstring)
                            annotations.extend(self._python_annotations(child))
                            sections.append(self._node_section(text, child, method_name, 'method'))
                            routes.extend(self._python_routes(child))
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append(node.name)
                    decorators.extend(self._python_decorators(node.decorator_list))
                    func_docstring = ast.get_docstring(node)
                    if func_docstring:
                        docstrings.append(func_docstring)
                    annotations.extend(self._python_annotations(node))
                    sections.append(self._node_section(text, node, node.name, 'function'))
                    routes.extend(self._python_routes(node))
            symbols = classes + functions + routes
            headings = [path.name] + [section.title for section in sections if section.title]
            http_calls = self._extract_http_calls(text, 'python')
            dependencies = self._extract_dependencies(text, 'python')
            return ParsedDocument(
                repo_name=repo_name,
                path=str(path),
                language='python',
                text=text,
                headings=headings,
                sections=sections or [ParsedSection(title=path.name, content=text, kind='module', line_end=max(1, len(text.splitlines())))],
                symbols=symbols,
                imports=imports,
                classes=classes,
                functions=functions,
                interfaces=interfaces,
                decorators=sorted(set(decorators)),
                annotations=sorted(set(annotations)),
                comments=comments,
                docstrings=docstrings,
                api_routes=sorted(set(routes)),
                http_calls=sorted(set(http_calls)),
                dependencies=sorted(set(dependencies)),
                framework_type=framework,
                metadata={'parser_name': 'ast'},
            )
        except SyntaxError:
            return self._parse_regex(path, text, repo_name, 'python', framework)

    def _parse_with_tree_sitter(self, text: str, lang: str) -> dict[str, Any] | None:
        language_name = TREE_SITTER_LANGUAGE_NAMES.get(lang)
        if not language_name:
            return None
        try:
            from tree_sitter import Parser
            from tree_sitter_languages import get_language
        except Exception:
            return None
        try:
            parser = Parser()
            parser.set_language(get_language(language_name))
            tree = parser.parse(text.encode('utf-8'))
        except Exception:
            return None

        result: dict[str, Any] = {
            'imports': [],
            'classes': [],
            'functions': [],
            'interfaces': [],
            'decorators': [],
            'annotations': [],
            'comments': [],
            'docstrings': [],
            'api_routes': [],
            'sections': [],
            'parser_name': 'tree-sitter',
        }
        root = tree.root_node
        lines = text.splitlines()

        def node_text(node) -> str:
            return text[node.start_byte:node.end_byte]

        def add_symbol(name: str | None, kind: str, node) -> None:
            if not name:
                return
            if kind == 'class':
                result['classes'].append(name)
            elif kind == 'function':
                result['functions'].append(name)
            elif kind == 'interface':
                result['interfaces'].append(name)
            result['sections'].append(ParsedSection(
                title=name,
                level=2,
                content=node_text(node),
                kind=kind,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                hierarchy=[name],
            ))

        def visit(node) -> None:
            node_type = node.type
            snippet = node_text(node)
            if 'comment' in node_type:
                result['comments'].append(snippet.strip())
                return
            if node_type in {'import_statement', 'import_declaration', 'package_clause', 'import_spec_list'}:
                result['imports'].append(snippet.strip())
            if node_type in {'class_definition', 'class_declaration'}:
                add_symbol(self._capture_named_child(node, snippet), 'class', node)
            if node_type in {'interface_declaration'}:
                add_symbol(self._capture_named_child(node, snippet), 'interface', node)
            if node_type in {'function_definition', 'function_declaration', 'method_definition', 'method_declaration'}:
                add_symbol(self._capture_named_child(node, snippet), 'function', node)
            if node_type in {'decorator', 'annotation'}:
                value = snippet.strip()
                result['decorators'].append(value)
                result['annotations'].append(value)
            for child in getattr(node, 'children', []):
                visit(child)

        visit(root)
        result['comments'].extend(self._extract_comments(text, lang))
        result['api_routes'].extend(self._detect_rest_endpoints(text, lang))
        if not result['sections']:
            result['sections'].append(ParsedSection(
                title=None,
                level=1,
                content=text,
                kind='module',
                line_end=max(1, len(lines)),
            ))
        return result

    def _build_document(
        self,
        path: Path,
        text: str,
        repo_name: str | None,
        lang: str,
        framework: str | None,
        tree_result: dict[str, Any],
    ) -> ParsedDocument:
        headings = [path.name] + [section.title for section in tree_result['sections'] if section.title]
        symbols = tree_result['classes'] + tree_result['functions'] + tree_result['interfaces'] + tree_result['api_routes']
        http_calls = tree_result.get('http_calls', []) + self._extract_http_calls(text, lang)
        dependencies = tree_result.get('dependencies', []) + self._extract_dependencies(text, lang)
        return ParsedDocument(
            repo_name=repo_name,
            path=str(path),
            language=lang,
            text=text,
            headings=headings,
            sections=tree_result['sections'],
            symbols=symbols,
            imports=sorted(set(tree_result['imports'])),
            classes=sorted(set(tree_result['classes'])),
            functions=sorted(set(tree_result['functions'])),
            interfaces=sorted(set(tree_result['interfaces'])),
            decorators=sorted(set(tree_result['decorators'])),
            annotations=sorted(set(tree_result['annotations'])),
            comments=self._dedupe_preserve_order(tree_result['comments']),
            docstrings=self._dedupe_preserve_order(tree_result['docstrings']),
            api_routes=sorted(set(tree_result['api_routes'])),
            http_calls=sorted(set(http_calls)),
            dependencies=sorted(set(dependencies)),
            framework_type=framework,
            metadata={'parser_name': tree_result.get('parser_name', 'tree-sitter')},
        )

    def _parse_regex(
        self,
        path: Path,
        text: str,
        repo_name: str | None,
        lang: str,
        framework: str | None,
    ) -> ParsedDocument:
        imports = re.findall(r'^(?:import|from|use|package|require|using)\s+[^;\n]+', text, re.M)
        classes = re.findall(r'\bclass\s+([A-Za-z_][\w]*)', text)
        interfaces = re.findall(r'\binterface\s+([A-Za-z_][\w]*)', text)
        funcs = re.findall(r'\b(?:function\s+|def\s+|func\s+)?([A-Za-z_][\w]*)\s*\([^)]*\)\s*(?:\{|:)', text)
        decorators = re.findall(r'^\s*(@[A-Za-z_][\w.]*)', text, re.M)
        annotations = decorators + re.findall(r'^\s*@([A-Za-z_][\w.]*)', text, re.M)
        routes = self._detect_rest_endpoints(text, lang)
        comments = self._extract_comments(text, lang)
        http_calls = self._extract_http_calls(text, lang)
        dependencies = self._extract_dependencies(text, lang)
        sections = self._regex_sections(path.name, text, classes, funcs, interfaces)
        return ParsedDocument(
            repo_name=repo_name,
            path=str(path),
            language=lang,
            text=text,
            headings=[path.name] + [section.title for section in sections if section.title],
            sections=sections,
            symbols=classes + funcs + interfaces + routes,
            imports=sorted(set(imports)),
            classes=sorted(set(classes)),
            functions=sorted(set(funcs)),
            interfaces=sorted(set(interfaces)),
            decorators=sorted(set(decorators)),
            annotations=sorted(set(annotations)),
            comments=comments,
            docstrings=[],
            api_routes=sorted(set(routes)),
            http_calls=sorted(set(http_calls)),
            dependencies=sorted(set(dependencies)),
            framework_type=framework,
            metadata={'parser_name': 'regex'},
        )

    def _regex_sections(
        self,
        filename: str,
        text: str,
        classes: list[str],
        functions: list[str],
        interfaces: list[str],
    ) -> list[ParsedSection]:
        sections = []
        lines = text.splitlines()
        for symbol in classes:
            sections.append(ParsedSection(title=symbol, level=2, content=text, kind='class', line_end=max(1, len(lines)), hierarchy=[filename, symbol]))
        for symbol in interfaces:
            sections.append(ParsedSection(title=symbol, level=2, content=text, kind='interface', line_end=max(1, len(lines)), hierarchy=[filename, symbol]))
        for symbol in functions:
            sections.append(ParsedSection(title=symbol, level=2, content=text, kind='function', line_end=max(1, len(lines)), hierarchy=[filename, symbol]))
        return sections or [ParsedSection(title=filename, level=1, content=text, kind='module', line_end=max(1, len(lines)), hierarchy=[filename])]

    def _detect_framework(self, text: str, lang: str) -> str | None:
        lower = text.lower()
        if lang == 'python' and ('fastapi' in lower or '@app.get' in lower or '@router.get' in lower):
            return 'fastapi'
        if lang in {'javascript', 'typescript'} and "express(" in lower:
            return 'express'
        if lang == 'typescript' and '@ngmodule' in lower:
            return 'angular'
        if lang == 'java' and ('@restcontroller' in lower or '@requestmapping' in lower or 'springapplication' in lower):
            return 'spring-boot'
        return None

    def _detect_rest_endpoints(self, text: str, lang: str) -> list[str]:
        routes = []
        if lang == 'python':
            routes.extend(re.findall(r'@(?:app|router)\.(get|post|put|delete|patch)\(["\']([^"\']+)', text, re.I))
            return [f'{method.upper()} {path}' for method, path in routes]
        if lang in {'javascript', 'typescript'}:
            matches = re.findall(r'\b(?:app|router)\.(get|post|put|delete|patch)\(["\']([^"\']+)', text, re.I)
            return [f'{method.upper()} {path}' for method, path in matches]
        if lang == 'java':
            matches = re.findall(r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)\(([^)]*)\)', text)
            normalized = []
            for method, args in matches:
                path_match = re.search(r'["\']([^"\']+)["\']', args)
                http_method = method.replace('Mapping', '').upper()
                if http_method == 'REQUEST':
                    method_arg = re.search(r'RequestMethod\.([A-Z]+)', args)
                    http_method = method_arg.group(1) if method_arg else 'REQUEST'
                normalized.append(f'{http_method} {path_match.group(1) if path_match else "/"}')
            return normalized
        if lang == 'go':
            return re.findall(r'HandleFunc\(["\']([^"\']+)["\']', text)
        return []

    def _extract_http_calls(self, text: str, lang: str) -> list[str]:
        """Extract outbound HTTP calls made by frontend/client code."""
        calls = []
        if lang in {'typescript', 'javascript'}:
            # Angular HttpClient: this.http.get('/api/...') or this.httpClient.post('/api/...')
            angular = re.findall(
                r'\.(?:http|httpClient|_http)\.(get|post|put|delete|patch)\s*[<(][^)]*?[\'"]([^\'"]+)[\'"]',
                text, re.I
            )
            calls.extend(f'{m.upper()} {p}' for m, p in angular if p and p.startswith('/'))
            # fetch('/api/...')
            fetch = re.findall(
                r"""fetch\(\s*['"]([^'"]+)['"]\s*(?:,\s*\{[^}]*?method\s*:\s*['"]([A-Za-z]+))?""",
                text,
            )
            for url, method in fetch:
                if url and url.startswith('/'):
                    calls.append(f"{(method or 'GET').upper()} {url}")
            # axios.get('/api/...')
            axios = re.findall(r'axios\.(get|post|put|delete|patch)\s*\([\'"]([^\'"]+)[\'"]', text, re.I)
            calls.extend(f'{m.upper()} {p}' for m, p in axios if p and p.startswith('/'))
        elif lang == 'java':
            # RestTemplate / WebClient
            rest = re.findall(
                r'(?:restTemplate|webClient)\.(get|post|put|delete|patch)ForObject\([^,]*[\'"]([^\'"]+)[\'"]',
                text, re.I
            )
            calls.extend(f'{m.upper()} {p}' for m, p in rest)
            # UriComponentsBuilder / HttpEntity patterns
            uri = re.findall(r'URI\.create\([\'"]([^\'"]+)[\'"]\)', text)
            calls.extend(f'GET {u}' for u in uri if u and u.startswith('/'))
        return calls

    def _extract_dependencies(self, text: str, lang: str) -> list[str]:
        """Extract injected service/class dependencies."""
        deps = []
        if lang == 'java':
            # Constructor injection: private final BeneficiaryService beneficiaryService;
            deps.extend(re.findall(r'(?:private|protected)\s+(?:final\s+)?([A-Z][\w]+(?:Service|Repository|Repo|Client|Manager|Helper))\s+\w+', text))
            # @Autowired fields
            deps.extend(re.findall(r'@Autowired[^;]+?([A-Z][\w]+)\s+\w+\s*;', text, re.S))
        elif lang in {'typescript', 'javascript'}:
            # Angular constructor injection: constructor(private beneficiaryService: BeneficiaryService)
            deps.extend(re.findall(r'constructor\s*\([^)]+?([A-Z][\w]+(?:Service|Client|Repository|Store|Facade))\b', text))
        elif lang == 'python':
            # FastAPI Depends() or direct instantiation
            deps.extend(re.findall(r'Depends\(([A-Za-z_][\w]*)\)', text))
        return deps

    def _extract_comments(self, text: str, lang: str) -> list[str]:
        if lang == 'python':
            return [line.strip() for line in re.findall(r'^\s*#.*$', text, re.M)]
        pattern = r'//.*?$|/\*.*?\*/'
        return [comment.strip() for comment in re.findall(pattern, text, re.M | re.S)]

    def _python_decorators(self, decorators: list[ast.expr]) -> list[str]:
        values = []
        for decorator in decorators:
            if hasattr(ast, 'unparse'):
                values.append(ast.unparse(decorator))
            else:
                values.append(type(decorator).__name__)
        return values

    def _python_annotations(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        annotations = []
        for arg in list(node.args.args) + list(node.args.kwonlyargs):
            if arg.annotation is not None and hasattr(ast, 'unparse'):
                annotations.append(ast.unparse(arg.annotation))
        if node.returns is not None and hasattr(ast, 'unparse'):
            annotations.append(ast.unparse(node.returns))
        return annotations

    def _python_routes(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        routes = []
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            attr = getattr(decorator.func, 'attr', None)
            if attr not in {'get', 'post', 'put', 'delete', 'patch'}:
                continue
            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                routes.append(f'{attr.upper()} {decorator.args[0].value}')
        return routes

    def _node_section(self, text: str, node: ast.AST, title: str, kind: str) -> ParsedSection:
        start_line = getattr(node, 'lineno', 1)
        end_line = getattr(node, 'end_lineno', start_line)
        snippet = '\n'.join(text.splitlines()[start_line - 1:end_line])
        return ParsedSection(
            title=title,
            level=2,
            content=snippet,
            kind=kind,
            line_start=start_line,
            line_end=end_line,
            hierarchy=[title],
        )

    def _capture_named_child(self, node, snippet: str) -> str | None:
        for child in getattr(node, 'children', []):
            if child.type == 'identifier':
                return snippet[child.start_byte - node.start_byte:child.end_byte - node.start_byte]
        match = re.search(r'\b(class|interface|func|function)\s+([A-Za-z_][\w]*)', snippet)
        return match.group(2) if match else None

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        seen = set()
        out = []
        for value in values:
            if value in seen or not value:
                continue
            seen.add(value)
            out.append(value)
        return out
