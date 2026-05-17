"""Unit tests for the Jira client.

When real Jira credentials are configured in .env, list_tickets() returns
live data from the Jira Cloud instance. Tests that depend on mock data
are skipped in that scenario to avoid false failures.
"""
from __future__ import annotations

import os

import pytest

from integrations.jira_client import get_ticket, list_tickets, _MOCK_TICKETS


def _real_jira_configured() -> bool:
    """Check if real Jira credentials are present."""
    from config import get_settings
    s = get_settings()
    return bool(s.jira_server and s.jira_email and s.jira_api_token)


class TestJiraClientCore:
    """Tests that work regardless of whether real Jira is configured."""

    def test_list_tickets_returns_results(self):
        tickets = list_tickets()
        assert len(tickets) >= 1

    def test_list_tickets_have_required_fields(self):
        for t in list_tickets():
            assert 'key' in t
            assert 'summary' in t
            assert 'status' in t


class TestMockJiraClient:
    """Tests that validate the 5 canonical mock tickets.
    These are skipped when real Jira is configured because list_tickets()
    returns live data instead of mock data in that case.
    """

    @pytest.fixture(autouse=True)
    def _skip_if_real_jira(self):
        if _real_jira_configured():
            pytest.skip('Real Jira configured — mock tests skipped')

    def test_list_tickets_returns_all_five(self):
        tickets = list_tickets()
        assert len(tickets) == 5

    def test_get_existing_ticket(self):
        ticket = get_ticket('AMRIT-101')
        assert ticket['key'] == 'AMRIT-101'
        assert 'beneficiary' in ticket['summary'].lower()
        assert ticket['affected_feature'] == 'beneficiary'

    def test_get_ticket_case_insensitive(self):
        ticket = get_ticket('amrit-102')
        assert ticket['key'] == 'AMRIT-102'

    def test_get_unknown_ticket_raises(self):
        with pytest.raises(ValueError, match='not found'):
            get_ticket('AMRIT-999')

    def test_all_mock_tickets_have_affected_feature(self):
        for key, ticket in _MOCK_TICKETS.items():
            assert ticket.get('affected_feature'), f'{key} missing affected_feature'

    def test_amrit_102_is_healthid_feature(self):
        ticket = get_ticket('AMRIT-102')
        assert ticket['affected_feature'] == 'healthID'

    def test_amrit_103_is_patient_feature(self):
        ticket = get_ticket('AMRIT-103')
        assert ticket['affected_feature'] == 'patient'


class TestRealJiraClient:
    """Tests that only run when real Jira is configured."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_real_jira(self):
        if not _real_jira_configured():
            pytest.skip('No real Jira configured — skipping live tests')

    def test_real_list_returns_tickets(self):
        tickets = list_tickets()
        assert len(tickets) >= 1
        for t in tickets:
            assert 'key' in t
            assert 'summary' in t

    def test_real_get_ticket(self):
        tickets = list_tickets()
        if tickets:
            detail = get_ticket(tickets[0]['key'])
            assert detail['key'] == tickets[0]['key']
            assert 'summary' in detail
