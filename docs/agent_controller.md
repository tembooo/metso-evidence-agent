# Stage 06 — Autonomous Conversational Agent Controller

## Objective

Connect Stage 03 brochure retrieval and Stage 05 historical-service comparison through a model-driven Responses API tool-calling loop. The model determines tool selection from user messages; Python does all information retrieval and cost computation.

## Architecture

1. The user writes an ordinary message to an interactive CLI.
2. The controller sends a bounded recent-message history and function schemas to the model.
3. The model optionally calls `search_product_brochures` or `compare_service_costs`, possibly both, using strictly specified JSON arguments.
4. The Python tool adapters execute local Stage 03 and Stage 05 logic. They validate arguments and do not copy an entire source file to the model.
5. The function result is passed back to the model for a citation-aware answer or clarification.
6. Only user messages and final assistant answers are retained in local in-memory session state, not the retrieved source excerpts.

## Critical source boundaries

- Technical/product assertions: supplied product brochures only.
- Service rates and cost items: supplied historical field-service reports only.
- No web search, invented monetary exchange rates, unsupported warranties, or guessed commercial totals.
- Output `site_specific_budget: null` does **not** mean zero.
- `FSR-0027`'s EUR 2,215.40 is a **provisional reconstruction**, not a printed source total or Chile quotation.
- Citation validity and entailment are not fully mechanically checked in Stage 06. Stage 07 remains essential.

## Files

- `src/metso_agent/agent/tools.py`: narrowly scoped tool adapters.
- `src/metso_agent/agent/controller.py`: bounded Responses API function-call loop, error handling, in-memory context.
- `src/metso_agent/agent/chat.py`: interactive PowerShell CLI.
- `tests/test_agent_controller.py`: synthetic no-network tests.

## Commands

Local-only preflight (no API key or external requests):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agent_controller.py -v
.\.venv\Scripts\python.exe -m metso_agent.agent.chat --check-local
```

Only if the candidate has verified permission to transmit restricted source excerpts to the configured provider:

```powershell
.\.venv\Scripts\python.exe -m metso_agent.agent.chat --allow-external-evidence --verbose
```

Private `.env` settings:

```dotenv
OPENAI_API_KEY=YOUR_ACTUAL_PRIVATE_KEY
OPENAI_MODEL=AN_ACCESSIBLE_API_MODEL_ID
```

Do not paste actual keys in emails, repositories, logs or chat messages. This is API usage, which may be billed separately from any ChatGPT subscription.

## Testing scope and limitations

Synthetic unit tests do not call the API or touch employer documents. Model integration and live tool routing must be validated separately with an authorized API configuration. A model final answer can still misunderstand evidence; perform human verification and subsequently implement deterministic citation/claim checks (Stage 07). Since tool results may be sent outside the computer, consult the employer's restricted-material policy first. The `store=False` SDK parameter is not a contractual confidentiality guarantee.

## Completion criteria

- Earlier Stage 02-05 tests continue passing.
- A new product question triggers the product retrieval tool without manual mode selection.
- A cost question triggers the historical-service comparison, preserving provisional-currency distinctions.
- A combined question can use both tools.
- The exact two mandatory demo questions work and follow-up context is preserved.
- No live model call proceeds without explicit external-evidence opt-in.
- Git excludes raw material, local cache, `.env`, and any private report.
