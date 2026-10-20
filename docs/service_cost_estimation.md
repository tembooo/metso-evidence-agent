# Stage 05 — Evidence-Based Service Cost Estimation

## Objective

Create a deterministic, locally executable service-cost comparison tool based solely on the authorized Stage04 service-report ledger and original 50 TXT reports. Do not issue a binding quote. Never invent unavailable rates, currency conversions, taxes, travel origin, or parts supply assumptions.

## Program Components

- `src/metso_agent/estimation/cost_estimator.py`: typed request, strict Decimal arithmetic, ledger validation, source integrity, analog ranking, historical local rates, limited provisional component reconstruction, bounded CLI output.
- `tests/test_cost_estimator.py`: 18 synthetic unit tests, no original employer text or prices embedded.
- `local_cache/stage05_cost_comparison.json`: **PRIVATE** generated comparison (automatically ignored by the existing `.gitignore`).

## Inputs

The existing `local_cache/service_ledger.json` contains a JSON list of the 50 records produced by Stage04. Each entry has a nested `report`, `source_sha256`, `material_row_candidates`, `observations` and `quality_flags`. The source reports remain at `raw/data/HistoricalServices/FSR-XXXX.txt`. The tool verifies original SHA-256 hashes before using referenced records.

## Retrieval Design

Task similarity and geography are **separate comparisons**. A PF-DS match must not be widened to every PF machine. A completed cloth-replacement task and a matching explicitly reported quantity score higher than equipment name alone. Geographical comparators provide *historical rates for other scopes*, not a substitute PF-DS cloth-replacement quote.

## Monetary Controls

1. Use `decimal.Decimal` for all arithmetic.
2. Reject impossible or conflicting quantity × rate = extension lines.
3. Do not add values from different or missing currencies.
4. Keep printed totals distinct from reconstructed component sums.
5. Missing totals are `None`, never zero.
6. Bundled totals are not decomposed into an invented per-item rate.
7. Incomplete reports remain flagged.
8. The special *generic* material-table supplement requires a priced source table, line-level matching against the original, a single EUR evidence currency, and deduplication by quantity/rate/amount. Even then, the result is **provisional**, not an invoice total.
9. Existing source-hash agreement does not substitute for manual field validation. The Stage04 private review sheet still has `Pending` entries.
10. Source figures from different years are not automatically treated as currently valid rates.

## Example CLI Run

From the Windows project root:

```powershell
.\.venv\Scripts\python.exe -m metso_agent.estimation.cost_estimator --country Chile --equipment "Larox PF-DS tower press" --task "filter cloth replacement" --quantity 12
```

This reports the closest service analog, a **provisional** itemized component reconstruction when appropriate, other-scope country rates, evidence gaps, and critical clarifying questions. The actual country-specific budget stays `null` if evidence is inadequate.

## Test Commands

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cost_estimator.py -v
.\.venv\Scripts\python.exe -m pytest -v
```

If all 33 prior tests remain and 18 new tests are added, 51 passing tests are expected. Test counts alone do not validate real commercial suitability.

## Known Gaps / Future Stages

- All 41 flagged Stage04 reports have not been manually verified. Review sensitive analogs before claiming a verified price.
- The implementation does **not** calculate a Chile-specific quotation. Location, supplier of cloths, mobilization origin, local labor eligibility, taxes, expenses, and quantity/part compatibility need verification.
- The extracted service nomenclature about multiple PF-DS cloths may differ from the endless-cloth description in the product brochure.
- No LLM is used here. Autonomous intent routing and the interactive final answer are Stage06 tasks, and semantic claim validation belongs in Stage07.
- A richer cost-estimation policy may be added only when the provided evidence can justify its assumptions.

## Confidentiality

Never commit employer original reports, cached ledger, generated comparison JSON, private gold-case review, API credentials, or detailed source excerpts. Confirm `git check-ignore -v local_cache/stage05_cost_comparison.json` and inspect `git ls-files` and Git history before any public push.
