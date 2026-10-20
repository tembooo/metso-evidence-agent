# Stage 07 — Evidence and Response Validation

This **code-only** archive adds a post-generation safety check to the existing Metso Stage 06 agent. No original sources, client reports, local ledger, API keys or new dependencies are included.

## Windows PowerShell

Extract into your existing `project` directory, merging folders without deleting or replacing prior source files.

```
.\.venv\Scripts\python.exe -m pytest -q
Test-Path '.\src\metso_agent\validation\response_guard.py'
.\.venv\Scripts\python.exe .\scripts\apply_stage07_guard.py
.\.venv\Scripts\python.exe -m pytest tests\test_response_guard.py -v
.\.venv\Scripts\python.exe -m pytest -q
```

Expected with previous 63 tests intact: 16 new Stage 07 tests and 79 total. Run them locally to verify.

The patch script changes two known Stage 06 files in place only after confirming their expected contents. If the files differ, it aborts without changing anything. It writes original backups to ignored `local_cache/stage07_backups/`. The updated controller rejects unsupported final answers before saving them as conversation history. The live CLI enables the guard; prior Stage 06 tests remain compatible.

A failed live guard returns a short error code, not a customer-facing answer. Do not mistake a rejected answer for an API failure or bypass the guard. Investigate retrieval and answer content. See `docs/response_validation.md` for the manual evidence-review checklist and limitations.
