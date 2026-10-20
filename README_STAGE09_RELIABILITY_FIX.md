# Stage 09 — Narrow, non-destructive reliability correction

Run this **only** on the Windows project version with all prior Stage 07/08 fixes installed and with the original **130 tests passing**. The patch includes no confidential Metso evidence and no API credentials.

## Why this optional correction exists

The Stage 09 live benchmark observed seven matched questions, five strict routing matches, three completed exact-route responses. An attempted response to the cost question could fail the site-quote guard; even an explicit refusal to guarantee performance could be blocked. This patch addresses known model/guard interaction issues without disabling the evidence validator:

1. Permit clearly *negated* performance guarantees, still reject positive promises and mixed negative/positive clauses.
2. After the ordinary validation retry is exhausted, allow an **opt-in** guarded deterministic fallback for a historical cost record (only using the current turn's tool result), for a request that asks to guarantee unsupported improvement, or for a request to add mismatched currencies. Each fallback is **validated again** before being emitted.
3. Add narrow, domain-specific instructions: never pretend a Chilean record is an exact twelve-cloth PF-DS match, do not confuse feed grade with a proven physical mechanism, do not echo unsupported hypothetical amounts as costs.
4. Retain original behavior in any controller constructed without `use_safe_evidence_fallback=True`. The CLI opts in.

## Safe installation

Extract the ZIP and merge **new** files into the project (`scripts/apply_stage09_reliability_fix.py`, `tests/test_stage09_reliability_fix.py`). Do not overwrite previous files. Then run from the project root:

```powershell
.\.venv\Scripts\python.exe .\scripts\apply_stage09_reliability_fix.py
.\.venv\Scripts\python.exe -m pytest tests/test_stage09_reliability_fix.py -v
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m metso_agent.agent.chat --check-local
```

The script checks source-version markers and expected exact snippets **before editing**, compiles replacements, and saves backups under the ignored `local_cache/stage09_backups/`. It should not be applied to an unknown/partially patched layout. It is idempotent if already fully installed.

## Important limits

- **No performance guarantee:** these targeted regex checks are *not* semantic verification of every sentence.
- **Fallback is not a Chile quote.** It can offer only a historic reconstructed sum with the proper report and caveats, based on current tool evidence. Never interpret missing price or unknown exclusions as zero.
- The existing 7-turn benchmark and original gold labels are retained. Do not relabel prior failures to make metrics look better. A separate human-review record may mark safe refusals as appropriate.
- The old Windows `Start-Transcript` failure is unrelated to this patch. Use the recovered log for baseline grading, and manual copy to a UTF-8 private file for the new live check.
- If any patch or full test fails, restore backed up files or ask for review. Never disable the guard or publish private source text.

## Reliable future interactive transcript recording

The patched CLI supports `--session-log` (private file path **only** under `local_cache`). It records prompts, tool names, accepted replies, and guarded error codes directly in UTF-8. It does **not** store raw tool results, but some user messages/replies may be confidential, so keep the file private. It refuses to overwrite an existing log: choose a new filename for each run.

```powershell
.\.venv\Scripts\python.exe -m metso_agent.agent.chat --allow-external-evidence --verbose --session-log ".\local_cache\stage09_after_fix_run1.txt"
```

After entering the seven evaluation prompts and typing `exit`, score the file:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_stage09_eval.py transcript --log ".\local_cache\stage09_after_fix_run1.txt" --output ".\local_cache\stage09_after_fix_results.json"
```

The original benchmark scores were **7 matched**, **5 routing matches**, **3 completed exact-route replies**. Keep that historical result intact; report post-fix scores separately.

## Expected verification

The new file contains **17 synthetic tests**. With the original 130 tests retained, a complete Windows project should target **147 passed**. In a local reconstructed subset of the Stage07/08/09 project, **114/114** tests passed after applying this script. This subset is not the user's complete Windows repository.
