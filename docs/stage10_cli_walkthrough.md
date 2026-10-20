# Stage 10 — Minimal CLI walkthrough

This document describes a minimal demonstration of the *existing* evidence-based Metso agent. The new `main.py` file is an entry-point wrapper only; it does not replace the previously tested controller, source guards, retrieval, cost engine, or flotation calculations.

## Why a command-line demonstration?

The exercise prioritizes a working agent and inspectable routing rather than a graphical interface. A readable terminal demonstration should show which factual tools were used, the source references that support answers, explicit uncertainty, and brief follow-up questions.

## Private local preflight — no API use

```powershell
.\.venv\Scripts\python.exe main.py --help
.\.venv\Scripts\python.exe main.py --check-local
.\.venv\Scripts\python.exe -m pytest tests/test_stage10_cli.py -v
.\.venv\Scripts\python.exe -m pytest -q
```

The preflight should report usable product retrieval and 50 readable historical service reports. All regression tests should pass before live use.

## Live demo with trace and a private transcript

Only run live after confirming that using the selected API provider with private excerpts is authorized. Set `OPENAI_API_KEY` and `OPENAI_MODEL` in the ignored, local `.env` file; never display or record the key.

```powershell
.\.venv\Scripts\python.exe main.py --allow-external-evidence --verbose --session-log ".\local_cache\stage10_demo_run1.txt"
```

Suggested demonstration order:

1. Product recommendation: a changing-feed Larox pressure-filter question. Verify `search_product_brochures` and document/page references.
2. Field-service cost: a 12-cloth PF-DS visit in Chile. Verify `compare_service_costs`, historical analog details, and explicit non-quotation language.
3. Optional flotation: silica 3.1% and iron 64.5%. Verify `analyze_flotation`, historical counts, and the distinction between frequency and a customer quality specification.
4. Optional combined question: product suitability plus service costs. Both relevant tools should appear.
5. End the session by entering `exit` or `quit`.

Use the two mandatory questions in the exact wording of the assignment when recording the employer-required video. Avoid showing private raw reports in the terminal or editor, and do not show `.env`.

## Expected presentation behavior

- `You >` introduces an arbitrary user request.
- `Tools used:` shows the factual tool names when `--verbose` is enabled; this is not a display of private chain-of-thought.
- `Assistant >` shows the final answer with source references, uncertainty, and a useful question when needed.
- `--session-log` writes the conversation inside ignored `local_cache/` and prevents overwriting an existing path.
- `exit` ends the interactive session gracefully.

## Release and verification boundaries

Do not publish `raw/`, `local_cache/`, `.env`, private gold sets, the detailed private study report, or any source-derived confidential data. `main.py` and this methodology document are code-only artifacts, but should still be included only after the Stage 11 staged-file security review.

This stage establishes a clear runnable presentation of the system. It does not independently prove the numerical correctness of each source record or complete the public GitHub/video/Recright submission.
