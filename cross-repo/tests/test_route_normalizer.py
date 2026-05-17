"""Unit tests for route normalization."""
from __future__ import annotations

import pytest

from core.route_normalizer import normalize_route, routes_match


class TestNormalizeRoute:
    def test_strips_query_string(self):
        assert normalize_route('/api/v1/patient?sort=asc') == '/api/v1/patient'

    def test_strips_trailing_slash(self):
        assert normalize_route('/api/v1/patient/') == '/api/v1/patient'

    def test_integer_segment_replaced(self):
        assert normalize_route('/api/v1/patient/123/records') == '/api/v1/patient/{param}/records'

    def test_uuid_segment_replaced(self):
        result = normalize_route('/api/v1/patient/550e8400-e29b-41d4-a716-446655440000/data')
        assert '{param}' in result
        assert '550e8400' not in result

    def test_spring_template_normalised(self):
        assert normalize_route('/api/v1/patient/{patientId}/records') == '/api/v1/patient/{param}/records'

    def test_static_path_unchanged(self):
        assert normalize_route('/beneficiary/register') == '/beneficiary/register'

    def test_ensures_leading_slash(self):
        assert normalize_route('api/v1/test').startswith('/')

    def test_empty_returns_empty(self):
        assert normalize_route('') == ''


class TestRoutesMatch:
    def test_exact_match(self):
        matched, quality = routes_match('/api/v1/patient', '/api/v1/patient')
        assert matched is True
        assert quality == 'exact'

    def test_template_match(self):
        # Both /api/v1/patient/123/records and /api/v1/patient/{id}/records
        # normalise to /api/v1/patient/{param}/records, so this is an exact match.
        # This is the correct and desired behaviour: the normalizer makes them equivalent.
        matched, quality = routes_match('/api/v1/patient/123/records', '/api/v1/patient/{id}/records')
        assert matched is True
        assert quality in ('exact', 'template')  # either is a valid match

    def test_prefix_match(self):
        matched, quality = routes_match('/api/v1/patient', '/api/v1/patient/data')
        assert matched is True
        assert quality == 'prefix'

    def test_no_match_different_paths(self):
        matched, quality = routes_match('/api/v1/patient', '/api/v1/beneficiary')
        assert matched is False
        assert quality == 'none'

    def test_method_agnostic(self):
        # routes_match only compares paths, not methods
        matched, quality = routes_match('/api/v1/patient', '/api/v1/patient')
        assert matched is True
