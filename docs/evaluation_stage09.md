# Stage 09 — Evaluation and Regression Testing

## Why this exists

The Stage 08 checkpoint is **113 passed, 18 DeprecationWarnings**, plus separate live successes for the required product, service and optional flotation scenarios. That checkpoint does not measure generalization to previously unseen wording. Stage 09 adds labels, retrieval measurements and observable route checks without changing production controller, retrieval or price code.

## Independent evidence boundaries

- Product: Metso brochure identifier and page number. Source relevance does **not** prove semantic entailment.
- Service: FSR report reference, work scope, individual amounts, original currency and provisional flags. Never convert a historical Swedish service sum to a Chile quote.
- Flotation: deterministic CSV counts, descriptive statistics, and explicit unknown customer contract limits.
- Safety: no unsupported guarantees, mixed-currency arithmetic, forged FSR IDs or commercial quotation claims.

## Gold set

`docs/private/stage09_gold_cases.jsonl` contains **33** independently labeled cases: product, service, flotation, combined intent and adversarial/clarification examples. Each identifies expected tool(s); 12 product cases carry a separate retrieval query and labeled brochure ID. The labels are evaluation data; **do not paste them into SYSTEM_RULES or hard-code answers**. Add new prompts if necessary, but preserve failures.

## Offline runs

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe .\scripts\run_stage09_eval.py retrieval --output .\local_cache\stage09_retrieval.json
```

The retrieval command evaluates *actual production* `ProductSearcher` against the local brochures, without calling the OpenAI API. It prints per-case source recall@5 and hit@5. Its averages are macro recall and query hit rate; they are not LLM routing accuracy. The target of >=95% recall is an **aspirational project criterion, not a previously verified score**. If a query fails, examine the returned relevance and adjust the retriever only when a grounded improvement is warranted.

## Live runs

Start `Start-Transcript` from PowerShell before launching the Agent (or paste captured terminal text into a local file). Run the two exact mandatory prompts, the exact optional prompt, and a few paraphrases. To grade the transcript:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_stage09_eval.py transcript --log .\local_cache\stage09_live.txt --output .\local_cache\stage09_route_results.json
```

The tool only matches **exact labeled prompt strings**. Routing accuracy is the fraction of matched prompts using the labeled tool set; full success also requires an answer rather than an exception. This is a basic automated check, not a full semantic answer-quality judge. If the log has zero matches, do not report a 100% score.

**Human review is mandatory:** inspect each answer for justified citations, proper commercial uncertainty, truthful thresholds, and source restrictions. Keep an error log. Avoid storing API credentials or data excerpts in public outputs.

## Evaluation failure taxonomy

1. Routing (missed or inappropriate tool)
2. Retrieval (expected brochure source not in first five)
3. Extraction (incorrect service lines, report scope or quantity)
4. Calculation (amount, currency, rates, arithmetic)
5. Synthesis (misreading retrieved material, exact-pair vs joint thresholds)
6. Evidence safety (fake citation, unsupported guarantee, declared Chile quote)
7. Environment (missing input files, dependency, timeout, API error)

## Important known issues

- The numerical success of 113 automated tests is real but is not 113 independent live evaluations.
- Existing NumPy timedelta `DeprecationWarning` messages are not test failures; defer maintenance until after mandatory delivery unless they become fatal.
- The optional flotation answer once called joint threshold prevalence the frequency of an `exact pair`. The correct interpretation is `silica >= threshold AND iron <= threshold` in 823/4,097 rows. Mark misleading replies as a synthesis defect.
- Stage 07's source checks are pattern-based and cannot prove that every technical sentence follows from its source.
- Review of original FSR-0027 and PF-DS cloth terminology should be completed privately before commercial reuse.

## Exit gate

- All existing and new offline tests pass.
- Retrieval recall@5 and hit@5 are measured and shortcomings documented.
- Three specified demo prompts route correctly and generate factual responses in a fresh session, with no unhandled errors.
- At least 3 carefully chosen adversarial probes are tested or explicitly deferred.
- `docs/private/stage07_manual_validation.md` is completed for high-risk evidence, or unresolved rows remain `PENDING` and are disclosed.
- Git checks confirm raw materials, `.env`, and `local_cache` remain excluded before publication.
