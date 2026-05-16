# Chunking Strategy

## Goals

- Keep architecture and setup sections intact
- Preserve code fences and source blocks
- Maintain 500 to 1200 token targets with 100 to 150 token overlap
- Avoid splitting chunks across unrelated headings

## Strategy

- Start from parser-produced sections rather than raw file text.
- Split section content into semantic blocks using paragraph boundaries and fenced code blocks.
- Build chunks by accumulating blocks until the max token target is reached.
- Carry overlap forward using the last semantic blocks, not arbitrary token slices.
- Rebalance undersized trailing chunks back into the previous chunk when needed.

## Chunk Metadata

Each chunk preserves:

- `repo`
- `path`
- `language`
- `chunk_type`
- `section`
- `section_hierarchy`
- `headings`
- `symbols`
- `imports`
- `related_sections`
- `framework_type`
- `ingestion_timestamp`
