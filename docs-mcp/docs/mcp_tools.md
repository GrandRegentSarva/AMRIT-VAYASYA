# MCP Tools

## `search_docs`

Inputs:

- `query`
- `repo_name`
- `limit`
- `language`
- `section`

Returns ranked chunks with:

- normalized and reranked scores
- source attribution
- file path
- section hierarchy
- metadata payload

## `explain_doc_section`

Builds a focused query from `path` and `heading`, returns:

- extractive summary
- ranked matching chunks
- related chunks for surrounding context

## `retrieve_related_chunks`

Looks up a chunk by id and performs dense retrieval over its text to surface adjacent context.

## `summarize_repository_docs`

Runs a summary-oriented retrieval query over the indexed repository and returns:

- architecture overview
- major modules
- important files
- framework hints
- ranked supporting chunks
