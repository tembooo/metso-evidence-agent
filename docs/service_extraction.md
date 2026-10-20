# Stage 04 — Historical Service Report Extraction

## Objective
Create a traceable, private, quality-flagged evidence ledger for all fifty field-service reports. This is **not** the service-cost quotation engine.

## Input
The authorized files must remain under `raw/data/HistoricalServices/FSR-0001.txt` through `FSR-0050.txt`. The input source files are not modified.

## Modules
- `src/metso_agent/ingestion/service_parser.py`: conservative extraction, typed Pydantic records, hash, source-line provenance, and uncertainty flags.
- `scripts/review_stage04.py`: local review of selected FSR records, no document republishing.
- `tests/test_service_parser.py`: synthetic unit tests; no confidential source text embedded.

## Procedure
1. Verify that exactly 50 numbered `.txt` files are present.
2. Read each source as UTF-8, preserve original file content unchanged and compute SHA-256.
3. Identify report ID, unambiguous date when possible, country/site when explicit, equipment, hours, and completed-work bullets.
4. Capture itemized **reported** monetary rows from the cost summary with original source line references. Preserve material-table rows for review without adding their costs a second time.
5. Capture only a **printed** total; no source-total reconstruction during extraction.
6. Retain incomplete or ambiguous candidate lines in the private ledger and label them for review.
7. Run synthetic tests and inspect selected actual records against their originals.
8. Record any human correction separately with report ID, source line, reviewer, reason and date.

## Output
- `local_cache/service_ledger.json`: private structured records, candidates, flags, hashes and provenance.
- `local_cache/service_quality_issues.json`: private issue list.
- `docs/private/stage04_gold_review.md`: optional human-reviewed reference cases; must remain ignored by Git.

## Field semantics
- `reported_total`: only a total explicitly present in the report. A missing total remains null.
- `total_currency`: no country-based inference; bare `$` is ambiguous.
- `labor_hours` and `travel_hours`: source observations, not estimates of future technician work.
- `activity_window_elapsed_hours`: a clock-time span, not an assumed billable total.
- `cost_items`: individually priced rows in the cost summary only. The materials list is stored separately to prevent double counting.
- `source.location`: original one-based file line number for traceability.
- `quality_flags`: explicit limitations rather than guessed repairs.

## Quality flags
Examples: `TRUNCATED_COST_TABLE`, `TOTAL_NOT_REPORTED`, `PARTIAL_ITEMIZED_COST_ONLY`, `PRICE_NOT_AVAILABLE`, `PARTIAL_OR_UNFINISHED_WORK`, `ELAPSED_VS_REPORTED_HOURS`, `DATE_REQUIRES_REVIEW`, `TRAVEL_DIRECTION_REQUIRES_REVIEW`, `TOTAL_CURRENCY_UNKNOWN`, `BUNDLED_TOTAL_NOT_ITEMIZED`, `TASKS_REQUIRE_REVIEW`.

## High-priority manual gold-review cases
- FSR-0027: source is truncated in the cost table; 8.4 reported on-site hours versus 8.75 elapsed clock hours; do not write the reconstructed EUR 2,215.40 as a printed total.
- FSR-0028: partial completion and contract-based unpriced service; travel described in an ambiguous way.
- FSR-0014: Canadian 16-cloth PF-DS case with wider hydraulic service scope; original total CAD 4,367.
- FSR-0031: Finnish 24-cloth case, hydraulic work, and separate VAT; source total EUR 2,580.44 including tax.
- FSR-0001 / 0015 / 0034 / 0035 / 0046: Chilean cases for geographic context, but not direct 12-cloth PF-DS equivalents.
- FSR-0044: SEK 19,850 bundled total with a wider scope.

## Boundaries
A schema-valid amount can still be semantically wrong. All pricing-sensitive fields require review before Stage 05. The extraction logic intentionally prioritizes abstaining and retaining raw line references over interpreting every irregular phrase.

The current parser is deliberately conservative and **does not** infer ambiguous date formats, assume missing currency from country, or guarantee that all narrative equipment mentions and work scopes are recognized. The script may produce review flags on many records. These are expected and should lead to manual review or improved parsing, not silent value fabrication.

## Tests and reruns

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_service_parser.py -v
.\.venv\Scripts\python.exe -m metso_agent.ingestion.service_parser
.\.venv\Scripts\python.exe .\scripts\review_stage04.py
.\.venv\Scripts\python.exe -m pytest -q
```

All generated ledger and issue artifacts are private; do not commit these outputs or the raw source files.
