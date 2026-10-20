# Stage 08-compatible quote-guard false-positive fix

This is a **small patch** to `src/metso_agent/validation/response_guard.py`, not a replacement for the agent. It was designed against the Stage 07 live-hotfix + Stage 08 architecture. It fixes a known false-positive pattern: explicit statements such as *"This cannot be treated as an official Chile budget"* should not be classified as affirmative site-specific quotes. Multiple quote claims in one answer are examined individually; the patch does **not** allow confirmed Chile prices unsupported by tool evidence.

The exact rejected model draft in the user's latest live run was not available, so this patch addresses a **reproduced class of problems**, not a proven diagnosis of that particular draft. It does not grant permission to invent prices.

## Install

1. Exit the interactive `You >` chat by entering `exit`.
2. Merge this ZIP's `scripts/` and `tests/` directories into your existing project. Do not overwrite other code or data.
3. Run from the project root:

```powershell
.\.venv\Scripts\python.exe .\scripts\apply_stage08_quote_guard_fix.py
.\.venv\Scripts\python.exe -m pytest tests/test_stage08_quote_guard_fix.py -v
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m metso_agent.agent.chat --check-local
```

Expected: 12 additional parameterized tests and 113 total (`101 + 12`) *if no other tests were added*. If patch reports `Layout mismatch`, stop and share this message; no files will have been modified.

## Live test

Run a fresh agent session and first ask the exact required Chile question. Confirm `Tools used: compare_service_costs`, a historical/reconstructed and explicitly non-Chile amount, and no invented current quote.

A single successful live result does not establish a universal guarantee. Still review the separate Stage 07 manual evidence checklist before final submission.

## Safety

The existing `response_guard.py` is backed up into ignored `local_cache/stage08_backups/`. Source data, `raw/`, `.env`, and historical ledgers should remain private. The script is idempotent.
