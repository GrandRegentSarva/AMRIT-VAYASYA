"""
Mock Jira Client
----------------
Provides 5 canonical AMRIT-themed tickets that trigger REAL graph intelligence.
Each ticket has an 'affected_feature' field that is fed directly into the
EvidenceCollector for deterministic traversal and impact analysis.

If JIRA_SERVER, JIRA_EMAIL, and JIRA_API_TOKEN are set in the environment,
the real Jira SDK will be used instead.
"""
from __future__ import annotations

import os
from typing import Any

# Canonical MVP tickets — designed to demonstrate different graph intelligence paths
_MOCK_TICKETS: dict[str, dict[str, Any]] = {
    'AMRIT-101': {
        'key': 'AMRIT-101',
        'summary': 'Add email notification after beneficiary registration',
        'description': (
            'When a beneficiary is successfully registered in the system, '
            'an email confirmation should be sent to the registered email address. '
            'This should use the existing notification service.'
        ),
        'status': 'Open',
        'priority': 'High',
        'reporter': 'sarvadubey',
        'affected_feature': 'beneficiary',
        'ticket_type': 'feature',
    },
    'AMRIT-102': {
        'key': 'AMRIT-102',
        'summary': 'Modify HealthID validation rules',
        'description': (
            'The current HealthID validation accepts IDs with fewer than 14 digits. '
            'This must be updated to enforce strict ABHA ID format: exactly 14 digits, '
            'no leading zeros. Update validation in the controller and DTO layer.'
        ),
        'status': 'In Progress',
        'priority': 'Critical',
        'reporter': 'sarvadubey',
        'affected_feature': 'healthID',
        'ticket_type': 'bug',
    },
    'AMRIT-103': {
        'key': 'AMRIT-103',
        'summary': 'Add audit logging to patient registration',
        'description': (
            'Every patient registration event must be logged to the audit trail table. '
            'The log must capture: user ID, timestamp, patient ID, and action type. '
            'This is a cross-cutting concern affecting all registration endpoints.'
        ),
        'status': 'Open',
        'priority': 'High',
        'reporter': 'sarvadubey',
        'affected_feature': 'patient',
        'ticket_type': 'feature',
    },
    'AMRIT-104': {
        'key': 'AMRIT-104',
        'summary': 'Expose FHIR-compatible patient data endpoint',
        'description': (
            'Add a new REST endpoint that returns patient data in FHIR R4 format. '
            'This endpoint should reuse the existing patient service layer and '
            'transform the output using a FHIR mapper.'
        ),
        'status': 'Open',
        'priority': 'Medium',
        'reporter': 'sarvadubey',
        'affected_feature': 'patientdata',
        'ticket_type': 'feature',
    },
    'AMRIT-105': {
        'key': 'AMRIT-105',
        'summary': 'Fix NullPointerException in EAushadhi drug search',
        'description': (
            'The EAushadhi drug search endpoint throws a NullPointerException when '
            'the search term contains special characters. The issue is in the '
            'EAushadhiController before the request reaches the service layer.'
        ),
        'status': 'Open',
        'priority': 'Critical',
        'reporter': 'sarvadubey',
        'affected_feature': 'eaushadhi',
        'ticket_type': 'bug',
    },
}


def _try_real_jira(issue_key: str) -> dict[str, Any] | None:
    """Attempt to fetch from a real Jira instance if credentials are configured."""
    server = os.environ.get('JIRA_SERVER')
    email = os.environ.get('JIRA_EMAIL')
    token = os.environ.get('JIRA_API_TOKEN')
    if not (server and email and token):
        return None

    try:
        from jira import JIRA  # type: ignore
        jira = JIRA(server=server, basic_auth=(email, token))
        issue = jira.issue(issue_key)
        return {
            'key': issue.key,
            'summary': issue.fields.summary,
            'description': issue.fields.description or '',
            'status': str(issue.fields.status),
            'priority': str(issue.fields.priority),
            'reporter': str(issue.fields.reporter),
            'affected_feature': issue.key.split('-')[0].lower(),
            'ticket_type': str(issue.fields.issuetype).lower(),
        }
    except Exception:
        return None


def get_ticket(issue_key: str) -> dict[str, Any]:
    """
    Fetch a Jira ticket. Uses real Jira if configured, falls back to mock data.
    """
    real = _try_real_jira(issue_key)
    if real:
        return real

    ticket = _MOCK_TICKETS.get(issue_key.upper())
    if not ticket:
        available = ', '.join(_MOCK_TICKETS.keys())
        raise ValueError(
            f'Ticket {issue_key} not found. '
            f'Available mock tickets: {available}. '
            f'Set JIRA_SERVER, JIRA_EMAIL, JIRA_API_TOKEN to use real Jira.'
        )
    return ticket


def list_tickets() -> list[dict[str, Any]]:
    """List all available mock tickets (summary only)."""
    return [
        {
            'key': t['key'],
            'summary': t['summary'],
            'status': t['status'],
            'priority': t['priority'],
            'ticket_type': t['ticket_type'],
        }
        for t in _MOCK_TICKETS.values()
    ]
