# Metso Stage 10 — Minimal command-line demonstration (additive)

**No changes to previously tested project files are required.** Copy the following files from this archive to the project root, preserving their relative paths:

- `main.py` — single stable launcher that calls the already installed `metso_agent.agent.chat.main`.
- `tests/test_stage10_cli.py` — 7 fast offline smoke checks; the local-only check expects the authorized source folder and 50-report ledger to be present.
- `docs/stage10_cli_walkthrough.md` — reproducible runbook for the live demonstration.

The package does **not** contain source brochures, field-service reports, the flotation CSV, API secrets, or private transcripts. It does **not** patch controller/validator and does not alter the existing Stage 09 logging or fallback behavior.

From the project root in PowerShell:

```powershell
.\.venv\Scripts\python.exe main.py --help
.\.venv\Scripts\python.exe main.py --check-local
.\.venv\Scripts\python.exe -m pytest tests/test_stage10_cli.py -v
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: 7 additional tests; if the previous checkpoint remains 147, the projected total is **154 passed**. That number is not verified on your Windows environment until you run it. Do not run the live call until these pass.

For a new, authorized live session:

```powershell
.\.venv\Scripts\python.exe main.py --allow-external-evidence --verbose --session-log ".\local_cache\stage10_demo_run1.txt"
```

Choose a new filename for later sessions; do not overwrite private logs. Type `exit` inside `You >` to stop. This is still the same interactive application as `python -m metso_agent.agent.chat`, just with a shorter launch command. No graphical UI or external front-end libraries are added.
