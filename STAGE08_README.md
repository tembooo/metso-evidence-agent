# Metso Stage 08 — Optional Flotation Data Analysis

**Code-only addition.** This ZIP has no Metso raw data or API key. The existing Stage07 files are not replaced on extraction.

## Files

- `src/metso_agent/analytics/flotation.py` — validated local CSV reader, descriptive counts, JSON/CLI
- `tests/test_flotation.py` — 12 synthetic no-data tests, runnable before integration
- `tests/test_flotation_agent_optional.py` — 4 synthetic tests after applying the tool integration patch
- `scripts/apply_stage08_tool.py` — narrowly-scoped, backed-up addition of the optional tool to the existing Agent
- `docs/flotation_analysis.md` — source/evidence definitions, commands, results and limitations

## Sequence

1. Extract/merge this ZIP at **the project root**, keeping existing files intact.
2. `python -m pytest tests/test_flotation.py -q` (expect 12 passed).
3. `python -m metso_agent.analytics.flotation --silica 3.1 --iron 64.5` (expect 981 / 1142 / 823 and ~20.09% joint).
4. Optional only: `python scripts/apply_stage08_tool.py` (expect 2 patched files, private backups).
5. `python -m pytest -q` (expect 95 passed if original 79 tests are unchanged).
6. Offline `python -m metso_agent.agent.chat --check-local` and live regression of the two required prompts after integration.
7. Then test the optional prompt in a **new Agent session** with the exact Metso wording.

Security: `.env`, `raw/`, `local_cache/`, and the full private study report must not enter the public code repository. The new docs are methodology and source-level aggregates, not the original rows.

If patching fails or the live validation guard rejects a benign flotation answer, **do not bypass the guard**. Preserve Stage07 and prioritize the two mandatory prompts and the deadline.
