from __future__ import annotations

import re


_ANGULAR_HTTP = re.compile(
    r'\.(?:http|httpClient|_http|_httpClient)\s*\.\s*(get|post|put|delete|patch)\s*'
    r'(?:<[^>]*>)?\s*\(\s*[`\'"]([^`\'"]+)[`\'"]',
    re.IGNORECASE,
)
_FETCH = re.compile(
    r'fetch\(\s*[`\'"]([^`\'"]+)[`\'"](?:\s*,\s*\{[^}]*?method\s*:\s*[`\'"]([A-Za-z]+))?',
    re.IGNORECASE,
)
_AXIOS = re.compile(
    r'axios\s*\.\s*(get|post|put|delete|patch)\s*\(\s*[`\'"]([^`\'"]+)[`\'"]',
    re.IGNORECASE,
)
_REST_TEMPLATE = re.compile(
    r'restTemplate\s*\.\s*(get|post|put|delete|patch|exchange)ForObject\s*\([^,\n]*[\'"]([^\'"]+)[\'"]',
    re.IGNORECASE,
)
_WEB_CLIENT = re.compile(
    r'webClient\s*\.\s*(get|post|put|delete|patch)\s*\(\s*\)\s*\.uri\s*\(\s*[\'"]([^\'"]+)[\'"]',
    re.IGNORECASE,
)


def extract_http_calls(text: str, language: str) -> list[dict[str, str]]:
    """
    Extract outbound HTTP calls from source code.

    Returns a list of dicts like:
        {"method": "GET", "path": "/api/beneficiary", "raw": "GET /api/beneficiary"}
    """
    results: list[dict[str, str]] = []

    def _add(method: str, path: str) -> None:
        path = path.strip()
        if path and not path.startswith('http'):
            # Keep relative API paths only; strip query strings
            clean = path.split('?')[0].rstrip('/')
            if clean:
                raw = f'{method.upper()} {clean}'
                results.append({'method': method.upper(), 'path': clean, 'raw': raw})

    if language in ('typescript', 'javascript'):
        for match in _ANGULAR_HTTP.finditer(text):
            _add(match.group(1), match.group(2))
        for match in _FETCH.finditer(text):
            _add(match.group(2) or 'GET', match.group(1))
        for match in _AXIOS.finditer(text):
            _add(match.group(1), match.group(2))

    elif language == 'java':
        for match in _REST_TEMPLATE.finditer(text):
            method = match.group(1)
            if method.lower() == 'exchange':
                method = 'GET'
            _add(method, match.group(2))
        for match in _WEB_CLIENT.finditer(text):
            _add(match.group(1), match.group(2))

    # Deduplicate preserving insertion order
    seen: set[str] = set()
    deduped = []
    for item in results:
        if item['raw'] not in seen:
            seen.add(item['raw'])
            deduped.append(item)
    return deduped
