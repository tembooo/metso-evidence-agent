# Stage 03 — Brochure-Grounded Product Retrieval

## Objective

Build a local, traceable product retrieval system based
exclusively on the supplied Metso product brochures.

## Authorized Sources

- raw/data/brochures/*.md
- Corresponding original PDF files for verification

Historical service reports are not used for product
capability or specification claims.

## Architecture

1. Load paired Markdown and PDF brochure names.
2. Validate explicit page markers.
3. Split each page into overlapping textual chunks.
4. Attach ProductEvidence and SourceRef metadata.
5. Build word-level and character-level TF-IDF indexes.
6. Expand customer search vocabulary.
7. Rank relevant evidence chunks.
8. Return source document, page, chunk ID, and score.

## Main Components

- brochure_loader.py
- product_search.py
- ProductEvidence
- SourceRef
- ProductSearcher
- SearchHit

## Retrieval Parameters

- Chunk size: 300 whitespace-delimited words
- Overlap: 45 words
- Word TF-IDF weight: 0.75
- Character TF-IDF weight: 0.25
- Default retrieved evidence count: 5
- Maximum results per document: 2

These settings are initial engineering choices and are
not claimed to be globally optimal.

## Evaluation

Synthetic unit tests cover:

- Page provenance
- Missing PDF/Markdown pairs
- Missing page markers
- Nonconsecutive pages
- Relevant product ranking
- Empty queries
- Page-boundary preservation

Live retrieval should also be verified against the
authorized local brochure corpus.

## Important Limitations

Retrieval scores measure textual similarity, not factual
truth or guaranteed product suitability.

Query expansion is used only to improve discovery.

A retrieved source does not prove compatibility,
savings, performance guarantees, or commercial pricing.

Numeric specifications should be checked against
the original PDF when extraction is ambiguous.

The current implementation does not use an LLM to
compose final responses.

The autonomous agent controller will be implemented
in a later stage.

## Confidentiality

Original brochures remain under raw/.

Do not commit source brochures, source excerpts,
private retrieval caches, or restricted reports.

Synthetic unit-test fixtures may be published after
a repository safety review.