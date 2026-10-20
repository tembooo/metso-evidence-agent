# Stage 07 — Evidence and Response Validation

## Objective
Add a conservative, deterministic post-generation gate to the working Stage 06 conversational agent. The Stage 03 brochure retriever and Stage 05 deterministic cost estimator remain unchanged. A plausible answer is not necessarily grounded: citations and derived figures must be checked before publication.

## New package contents
- `src/metso_agent/validation/response_guard.py`: checks cited source IDs/pages, explicit monetary amounts, some mixed-currency expressions, unsupported Chile quote claims and quantified guarantees.
- `src/metso_agent/validation/__init__.py`: package marker.
- `tests/test_response_guard.py`: 16 synthetic, offline tests.
- `scripts/apply_stage07_guard.py`: idempotent narrow integration patch. It stops on unexpected source layouts and makes backups in ignored `local_cache/stage07_backups/`.

## How to run
From the existing Windows project root, merge the new files, then run:

```
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe .\scripts\apply_stage07_guard.py
.\.venv\Scripts\python.exe -m pytest tests\test_response_guard.py -v
.\.venv\Scripts\python.exe -m pytest -q
```

With the 63 existing Stage 06 tests unchanged, expect 16 new tests and 79 total. These are acceptance targets, not independently verified results from the user's Windows machine.

The patch only enables checking in the live CLI; tests that directly create an AgentController are backward compatible. Answers rejected by the guard are neither displayed as customer answers nor appended to conversation history. The guard currently stops an invalid answer with an error and does not silently regenerate it.

## Deterministically checked conditions
1. Every `FSR-####` cited by the answer must appear in current-turn cost tool output.
2. Explicit page citations such as `filter-optimizer, p.2` must be among current-turn brochure hits.
3. Currency-coded amounts such as `2215.40 EUR` and euro-prefixed amounts such as `€2215.40` must occur in the cost tool evidence or be a transparent derived subtotal excluding the observed cloth line. Approximate integer rounding is recognized only when labelled approximately/about/around/≈/~.
4. Expressions like `100 EUR + 60 USD` are rejected.
5. If site_specific_budget is null, an affirmative confirmed Chile quote cannot be presented.
6. Quantified ungrounded savings/performance guarantees are rejected.
7. Empty answers and malformed tool results are rejected.

## Important limitations
The code is a pattern-based post-generation guard, **not a proof of semantic entailment**. A real page reference may still be attached to an unsupported interpretation. The current-turn citation rule may reject a real but not retrieved citation. Some formats of invented prices, numerical specifications and mixed currencies might evade the patterns. It cannot resolve product compatibility, tax, country-specific pricing, or physical causes of changing feed performance. Manual original-PDF and source-line review remains necessary.

## Manual review priorities observed in Stage 06
- The agent's first Larox response called a particular causal mechanism 'common' even though the customer had not provided slurry measurements; present this only as a hypothesis.
- The response sometimes suggests PF-DS capabilities without confirmation that the user's filter is PF-DS; ask for exact model before asserting model-specific behavior.
- The PF-DS brochure mentions one endless cloth, while service reports count multiple cloths. Do not silently reconcile them.
- `FSR-0027` is a Swedish, truncated report. Its `EUR 2215.40` amount is a provisional **reconstruction**, not a printed invoice or Chile quote.
- With customer-provided cloths, a calculated `EUR 1039.40` is another provisional historical comparison; not a site-specific commercial price.
- The agent sometimes promises a 'tighter planning range' merely after technician-origin confirmation. Promise only to reassess whether evidence becomes adequate.
- Chile labor and travel rates from other scopes must be isolated; never add unrelated USD data to EUR items.

## Private golden case set
Make a private worksheet with:
`case_id | input | expected_tools | claim | supporting_source | exact_page_or_line | numerical_check | risk | pass_fail | reviewer_notes`.

Cover: mandatory prompts, paraphrases, wrong brochure pages, unknown FSR IDs, a false 50% guarantee, a fabricated Chile price, mixed-currency math, an ambiguous equipment variant, an injection phrase in a synthetic tool result, and a combined product+service request. Review the meaning of citations manually. Passing unit tests alone is not a measured semantic-grounding or routing accuracy percentage.

## Confidentiality and release
Keep `raw/`, `local_cache/`, `.env`, `docs/private/`, local transcripts and the internal study-book PDF/LaTeX out of the public repository unless separately cleared. Synthetic Stage 07 test data can be public. Review `git status --short --ignored`, `git ls-files` and the Git history before pushing. Never share API keys or live client information in the recorded walkthrough.
