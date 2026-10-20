# Stage 08 — Optional flotation process-quality analysis

## Problem

The employer's optional prompt asks whether **3.1% silica** and **64.5% iron** in concentrate appear "normal". A historical frequency is **not** the same as a contractual quality specification, and a correlation does not identify the cause of process performance.

## Design

- Read the supplied CSV only at runtime, from `raw/data/flotation_process_data_hourly.csv`.
- Validate `date`, `% Iron Concentrate`, `% Silica Concentrate`, non-null finite measurements, and percentages within 0–100.
- Compare inclusive thresholds: historical silica `>= requested silica`, iron `<= requested iron`, and their conjunction.
- Report sample size, descriptive means/medians/quantiles, sample standard deviations, observed counts, percent of rows, observed correlation and any gaps >1 hour.
- Never fabricate contractual limits, prediction accuracy, causal explanations, reagent-flow units or equipment improvements.
- The CLI runs offline without any LLM key. The optional Agent integration can be added only after the independent analysis has been tested.

## Verified supplied example

The source CSV was inspected independently. For the provided example it contains 4,097 rows and 24 columns. At silica 3.1% and iron 64.5%:

| Metric | Result |
|---|---:|
| Historical silica mean | 2.326754% |
| Historical iron mean | 65.050084% |
| Silica >= 3.1% | 981 / 4,097 = 23.94% |
| Iron <= 64.5% | 1,142 / 4,097 = 27.87% |
| Both conditions | 823 / 4,097 = 20.09% |
| Silica / iron Pearson r | -0.801208 (association only) |
| Largest time gap | 319 hours (13 days, 7 hours) |

The customer readings are on the less favorable side of the historical means but are not unprecedented. The word "acceptable" would require the customer's actual contract specifications.

## How to run (Windows PowerShell, project root)

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_flotation.py -q
.\.venv\Scripts\python.exe -m metso_agent.analytics.flotation --silica 3.1 --iron 64.5
.\.venv\Scripts\python.exe -m metso_agent.analytics.flotation --silica 3.1 --iron 64.5 --json --output .\local_cache\stage08_flotation_result.json
```

If the optional model tool is desired, apply `scripts/apply_stage08_tool.py` after ensuring Stage07 is installed and independent tests pass. The script backs up Stage06/07 files under ignored `local_cache/`. It modifies only `agent/tools.py` and `agent/controller.py`, and stops without changing either file if source patterns differ.

## Acceptance and boundaries

- The historical counts must come from `pandas`, not constants embedded in runtime code.
- Dataset state must not be misrepresented as continuous because it has a 319-hour gap.
- An agent must route quality questions to `analyze_flotation` and keep this distinct from product-brochure and field-service-cost evidence.
- Testing this Python calculator does not establish live LLM tool routing, nor does it establish chemical/process suitability or customer-contract compliance.
- The optional task is limited to a **45-minute** allowance in Metso's original brief. Submission of both mandatory workflows, a public code URL, a 5–7 minute video and the Recright interview has priority.
