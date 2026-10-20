# Metso Stage05 — Code-Only Add-On

This ZIP contains only Stage05 Python implementation, synthetic tests and design documentation; it contains NO employer source reports, ledgers, or private values.

## Installation in your existing Windows project

1. Extract the ZIP into a temporary directory.
2. Copy the contained `src/`, `tests/` and `docs/` directories into your existing `.../interview/project` folder, merging directories. Do not delete/overwrite Stage02–Stage04 files.
3. Keep `raw/data/HistoricalServices/` and `local_cache/service_ledger.json` in their current private paths.
4. Run the tests and CLI using the preexisting `.venv`.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cost_estimator.py -v
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe -m metso_agent.estimation.cost_estimator --country Chile --equipment "Larox PF-DS tower press" --task "filter cloth replacement" --quantity 12
```

The CLI stores a private `local_cache/stage05_cost_comparison.json` and refuses to state an unsupported site-specific budget. The provisional historical reconstruction is not an invoice total or a quotation.

For step-by-step explanation, see `docs/service_cost_estimation.md`.
