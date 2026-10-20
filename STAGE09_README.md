# Stage 09 — Genuine Evaluation and Regression Tests

This is an **additive-only package**. It does not include or overwrite Agent Controller, Stage 07 guard, Stage 08 flotation code, source reports, raw CSV, or API keys.

Included:

- `src/metso_agent/evaluation/__init__.py` — new evaluation package.
- `src/metso_agent/evaluation/metrics.py` — deterministic source and route scoring.
- `scripts/run_stage09_eval.py` — offline retrieval and transcript evaluator.
- `tests/test_stage09_evaluation.py` — 17 new synthetic pytest tests, with no API calls.
- `docs/private/stage09_gold_cases.jsonl` — 33 labeled questions; Git-ignored by project policy.
- `docs/evaluation_stage09.md` — full methodology, limitations, commands and exit gate.

## Windows instructions

Extract at `project/`. **Merge directories** but do not overwrite old files. Verify with `Test-Path .\scripts\run_stage09_eval.py`.

From the `project/` folder with `.venv`:

```
.\.venv\Scripts\python.exe -m pytest tests/test_stage09_evaluation.py -v
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe .\scripts\run_stage09_eval.py retrieval --output .\local_cache\stage09_retrieval.json
```

Expected total is **130 passed**, if the previous baseline is 113 and no other tests have changed. This is an expectation, not a verified Windows result.

For the live test, see `docs/evaluation_stage09.md`. Keep transcripts under `local_cache/` (Git-ignored). Report scores only after running the real tools. Do not publish restricted source text.
