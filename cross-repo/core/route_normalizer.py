"""
Route Normalization
-------------------
Converts dynamic, concrete URLs into canonical parameterized templates so that
a frontend call like /api/v1/patient/123/records matches a Spring Boot mapping
of /api/v1/patient/{id}/records.

This eliminates false negatives in the RESOLVES_TO graph edge creation.
"""
from __future__ import annotations

import re

# Matches UUIDs, numeric IDs, and slugs embedded in path segments
_CONCRETE_SEGMENT = re.compile(
    r'(?<=/)'                         # preceded by slash
    r'('
    r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'  # UUID
    r'|\d+'                           # pure integer
    r'|[a-zA-Z0-9_\-]{3,}(?=(?:/|$))'  # slug-like segment that follows known patterns
    r')',
    re.VERBOSE,
)

# Spring Boot / JAX-RS path variables e.g.  {id}, {beneficiaryId}
_SPRING_PARAM = re.compile(r'\{[^}]+\}')

# Query string disposal
_QUERY_STRING = re.compile(r'\?.*$')


def normalize_route(path: str) -> str:
    """
    Convert a concrete URL path or a framework path template into a
    canonical parameterized template for graph matching.

    Examples:
        /api/v1/patient/123/records      -> /api/v1/patient/{param}/records
        /api/v1/patient/{patientId}/data -> /api/v1/patient/{param}/data
        /beneficiary/register            -> /beneficiary/register  (unchanged)
    """
    if not path:
        return path

    # Strip query string
    path = _QUERY_STRING.sub('', path.strip())

    # Remove trailing slashes
    path = path.rstrip('/')

    # Normalise framework-specific templates to {param}
    path = _SPRING_PARAM.sub('{param}', path)

    # Replace concrete dynamic segments with {param}
    # We only replace segments that look like IDs (pure digits / UUIDs)
    path = re.sub(
        r'(?<=/)'
        r'(?:'
        r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'  # UUID
        r'|\d+'  # pure integer
        r')'
        r'(?=/|$)',
        '{param}',
        path,
    )

    # Ensure leading slash
    if path and not path.startswith('/'):
        path = '/' + path

    return path


def routes_match(frontend_path: str, backend_path: str) -> tuple[bool, str]:
    """
    Return (matched, match_quality) where match_quality is one of:
        "exact"       - identical normalised strings
        "template"    - matched after parameterization
        "prefix"      - one path is a prefix of the other
        "none"        - no match

    Evidence contracts use this to annotate the confidence of a RESOLVES_TO edge.
    """
    norm_fe = normalize_route(frontend_path)
    norm_be = normalize_route(backend_path)

    if norm_fe == norm_be:
        return True, 'exact'

    if norm_fe and norm_be and (norm_be.startswith(norm_fe) or norm_fe.startswith(norm_be)):
        return True, 'prefix'

    # Segment-level comparison with wildcard {param} slots
    fe_parts = norm_fe.strip('/').split('/')
    be_parts = norm_be.strip('/').split('/')

    if len(fe_parts) == len(be_parts):
        if all(fp == bp or fp == '{param}' or bp == '{param}'
               for fp, bp in zip(fe_parts, be_parts)):
            return True, 'template'

    return False, 'none'
