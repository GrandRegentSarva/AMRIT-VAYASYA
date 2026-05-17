# Contributing to AMRIT-VAYASYA

Thank you for your interest in contributing to the AMRIT-VAYASYA intelligence platform. This document covers the guidelines, workflow, and expectations for all contributions across the three services.

## Project Structure

The project consists of three independent services. Each has its own dependencies, tests, and deployment configuration.

```
docs-mcp/      Ingestion and semantic retrieval         Python / FastAPI / Qdrant
cross-repo/    Graph intelligence and API tracing       Python / FastAPI / Neo4j
jira-mcp/      Jira integration and planning            Python / FastAPI / Jira SDK
```

## Development Setup

### Prerequisites

- Python 3.10 or later
- Docker and Docker Compose
- Git

### Getting Started

```bash
# Clone the repository
git clone https://github.com/GrandRegentSarva/AMRIT-VAYASYA.git
cd AMRIT-VAYASYA

# Start infrastructure (Qdrant, Neo4j, Redis)
cd docs-mcp && cp .env.example .env && docker compose up -d && cd ..

# Set up each service
cd cross-repo && cp .env.example .env && pip install -r requirements.txt && cd ..
cd jira-mcp && cp .env.example .env && pip install -r requirements.txt && cd ..
```

### Running Tests

Each service has its own test suite. Run them independently:

```bash
# docs-mcp tests
cd docs-mcp && pytest -q

# cross-repo tests (29 tests)
cd cross-repo && python -m pytest tests/ -v

# jira-mcp tests (8 tests)
cd jira-mcp && python -m pytest tests/ -v
```

All tests must pass before submitting a pull request.

## Code Guidelines

### General

- Write clear, descriptive variable and function names
- Add docstrings to all public functions and classes
- Keep functions focused: one function, one responsibility
- Prefer explicit over implicit behavior
- No commented-out code in pull requests

### Python Style

- Follow PEP 8 conventions
- Use type hints on all function signatures
- Use `from __future__ import annotations` for forward references
- Prefer dataclasses for structured data over raw dictionaries

### Architecture Principles

- **Deterministic first:** The LLM is a narration layer, not a decision layer. All graph traversal and evidence collection must produce identical results for identical inputs.
- **Evidence-grounded:** Every claim the system makes must cite a specific file, class, or endpoint from the knowledge graph.
- **Service isolation:** The three services communicate only via HTTP. No shared Python imports across service boundaries.
- **Metadata preservation:** All parsing and chunking operations must carry source file, line number, and repository metadata through the entire pipeline.

## Contribution Workflow

1. **Fork and branch:** Create a feature branch from `main` with a descriptive name (e.g., `add-go-parser`, `fix-route-normalization`).

2. **Make your changes:** Follow the code guidelines above. Add or update tests for any behavior changes.

3. **Run all tests:** Ensure all test suites pass across the affected services.

4. **Write a clear commit message:** Use plain English descriptions. Avoid conventional commit prefixes like `feat()` or `fix()`.

5. **Open a pull request:** Describe what your change does, why it is needed, and how you verified it works.

## Areas of Contribution

### Ingestion (docs-mcp)

- Adding parsers for new languages or frameworks
- Improving chunking quality and metadata extraction
- Optimizing embedding and retrieval performance

### Graph Intelligence (cross-repo)

- Improving route normalization for edge cases
- Adding new dependency extraction patterns
- Expanding the graph data model for new relationship types

### Jira Integration (jira-mcp)

- Enhancing plan generation output quality
- Adding support for additional issue tracker platforms
- Improving intent extraction from ticket descriptions

### Standards (standards/)

- Adding convention files for new frameworks (React, Go, Node.js)
- Refining existing Spring Boot and Angular rules
- Documenting patterns observed in AMRIT repositories

## Reporting Issues

Open an issue on GitHub with:

- A clear description of the problem
- Steps to reproduce (if applicable)
- Expected vs. actual behavior
- Relevant logs or error messages
