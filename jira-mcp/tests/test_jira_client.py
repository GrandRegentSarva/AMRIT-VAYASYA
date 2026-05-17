"""Unit tests for the Jira mock client and plan generator."""
from __future__ import annotations

import pytest

from integrations.jira_client import get_ticket, list_tickets


class TestMockJiraClient:
    def test_list_tickets_returns_all_five(self):
        tickets = list_tickets()
        assert len(tickets) == 5

    def test_list_tickets_have_required_fields(self):
        for t in list_tickets():
            assert 'key' in t
            assert 'summary' in t
            assert 'status' in t
            assert 'priority' in t

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

    def test_all_tickets_have_affected_feature(self):
        for t in list_tickets():
            full = get_ticket(t['key'])
            assert full.get('affected_feature'), f'{t["key"]} missing affected_feature'

    def test_amrit_102_is_healthid_feature(self):
        ticket = get_ticket('AMRIT-102')
        assert ticket['affected_feature'] == 'healthID'

    def test_amrit_103_is_patient_feature(self):
        ticket = get_ticket('AMRIT-103')
        assert ticket['affected_feature'] == 'patient'
