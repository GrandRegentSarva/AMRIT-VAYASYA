# jira-mcp: Graph-Grounded Jira Integration

The Jira integration service for AMRIT-VAYASYA. It fetches Jira tickets and generates implementation plans that are grounded in the live knowledge graph — not generic AI advice.

This module covers **Section D** (Jira Integration) of the MVP.

---

## What It Does

Standard Jira tools give you a ticket description. This service gives you:

- The exact backend controllers and service classes affected
- The full dependency injection chain that will change
- The specific source files to modify (from Neo4j, not guessed)
- Downstream impact including external service boundaries
- A contextual implementation checklist

---

## How It Works

```
Jira Ticket (AMRIT-101)
        |
        v
Intent Extraction
(affected_feature: "beneficiary")
        |
        v
cross-repo /explain API
(deterministic Neo4j + Qdrant traversal)
        |
        v
TraversalEvidence
(endpoints, service chain, DTOs, unresolved hops, code chunks)
        |
        v
Graph-Grounded Implementation Plan
```

`jira-mcp` has no imports from `cross-repo`. It communicates via HTTP. The two services are fully independent.

---

## Setup

```bash
cd jira-mcp
cp .env.example .env
pip install -r requirements.txt
```

The `.env` file:

```
CROSS_REPO_URL=http://localhost:8001   # Required: cross-repo service
JIRA_MCP_PORT=8002                     # Port this service runs on

# Optional: connect to a real Jira instance
JIRA_SERVER=
JIRA_EMAIL=
JIRA_API_TOKEN=
```

If `JIRA_SERVER`, `JIRA_EMAIL`, and `JIRA_API_TOKEN` are all set, the service will use your real Jira instance. Otherwise it falls back to the 5 built-in canonical AMRIT tickets.

---

## Running

```bash
# Make sure cross-repo is running first
uvicorn api:app --port 8002 --reload
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/tickets` | List all available tickets |
| GET | `/ticket/{key}` | Fetch a single ticket by key |
| GET | `/plan/{key}` | Generate a graph-grounded implementation plan |

---

## Demo: Generating a Plan

```bash
# List all tickets
curl -s http://localhost:8002/tickets | python3 -m json.tool

# Generate a plan for AMRIT-101 (email notification after beneficiary registration)
curl -s http://localhost:8002/plan/AMRIT-101 | python3 -m json.tool | grep -A 200 '"plan"'
```

Sample plan output for AMRIT-101:

```
================================================================
GRAPH-GROUNDED IMPLEMENTATION PLAN
================================================================
Ticket   : AMRIT-101 (FEATURE)
Summary  : Add email notification after beneficiary registration
Traversal: "beneficiary"  (confidence 75%)

AFFECTED COMPONENTS  (derived from knowledge graph)

Endpoints:
  POST   /api/v1/beneficiary/register
          Handler : BeneficiaryRegistrationController  [controller]
          Repo    : HWC-API
          Req DTO : BeneficiaryDTO

Service Chain:
  BeneficiaryRegistrationController -> BeneficiaryService -> BeneficiaryRepo

SUGGESTED FILES TO MODIFY  (evidence-grounded)
  [HWC-API]  src/main/java/com/.../BeneficiaryRegistrationController.java
  [HWC-API]  src/main/java/com/.../BeneficiaryService.java

IMPLEMENTATION CHECKLIST
  [ ] Review API contract (request/response DTOs above)
  [ ] Implement notification logic in the service layer
  [ ] Verify impact on external boundaries
  [ ] Write unit tests for new service methods
```

---

## Canonical Tickets

| Key | Summary | Graph Path Demonstrated |
|---|---|---|
| AMRIT-101 | Add email notification after beneficiary registration | Event tracing, service chain, downstream impact |
| AMRIT-102 | Modify HealthID validation rules | Impact analysis, API traversal, DTO tracing |
| AMRIT-103 | Add audit logging to patient registration | Cross-cutting concern tracing |
| AMRIT-104 | Expose FHIR-compatible patient data endpoint | API contract abstraction, service reuse |
| AMRIT-105 | Fix NullPointerException in EAushadhi drug search | Bug tracing, controller-level identification |

---

## MCP Tools

```bash
python mcp_server.py
```

| Tool | Arguments | Description |
|---|---|---|
| `list_jira_tickets` | none | List all tickets |
| `get_jira_ticket` | `issue_key: str` | Fetch a ticket |
| `create_implementation_plan` | `issue_key: str` | Graph-grounded plan |

---

## Tests

```bash
python -m pytest tests/ -v
# 8 tests covering:
# - All 5 canonical tickets accessible
# - Required fields present on every ticket
# - Error handling for unknown ticket keys
# - affected_feature field populated correctly
```
