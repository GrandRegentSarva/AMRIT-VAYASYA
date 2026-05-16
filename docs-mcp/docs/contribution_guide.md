# Contribution Guide

## Development Priorities

1. Parsing correctness
2. Metadata quality
3. Retrieval quality
4. Chunk intelligence
5. Maintainability
6. Debuggability
7. Performance

## Expectations

- Keep the retrieval pipeline simple and inspectable.
- Preserve metadata through parsing, chunking, indexing, and response generation.
- Prefer deterministic behavior over hidden heuristics.
- Add or update tests for every behavior change.

## Code Areas

- `core/parsing`: source and document extraction
- `core/chunking`: chunk lifecycle and overlap strategy
- `core/retrieval`: candidate generation, merge, reranking
- `apps/api`: public API contracts
- `mcp`: MCP tool contracts

## Validation

Run:

```bash
pytest -q
```

If changing parser behavior, include:

- fixture inputs
- metadata assertions
- retrieval assertions when ranking behavior changes
