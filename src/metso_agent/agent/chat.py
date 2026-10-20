"""Interactive Stage 06 terminal interface."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from metso_agent.agent.controller import AgentController, AgentRuntimeError
from metso_agent.agent.tools import LocalTools


# STAGE09_PRIVATE_SESSION_LOG_V1
def _stage09_session_path(root: Path, requested: str | None) -> Path | None:
    if not requested:
        return None
    target = Path(requested).expanduser().resolve()
    allowed = (root / 'local_cache').resolve()
    if not target.is_relative_to(allowed):
        raise ValueError('--session-log must point inside the private local_cache directory')
    if target.exists():
        raise ValueError('--session-log path already exists; choose a new filename')
    return target


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Stage 06 Metso conversational agent")
    parser.add_argument("--check-local", action="store_true",
                        help="Validate local imports/data paths; does NOT send external requests")
    parser.add_argument("--allow-external-evidence", action="store_true",
                        help="Explicitly permit selected private excerpts to be sent to the chosen API")
    parser.add_argument("--model", help="An API model ID accessible to your account")
    parser.add_argument("--verbose", action="store_true", help="Show called tool names only")
    parser.add_argument("--session-log", help="Log interactive conversation privately under local_cache")
    args = parser.parse_args()
    try:
        private_session_path = _stage09_session_path(root, args.session_log)
    except ValueError as exc:
        parser.error(str(exc))
    if private_session_path is not None:
        private_session_path.parent.mkdir(parents=True, exist_ok=True)
        private_session_path.write_text('# Private Stage09 CLI run; do NOT publish.\n', encoding='utf-8')

    def _record_private(question: str, trace: list[str], response: str, *, error: bool = False) -> None:
        if private_session_path is None:
            return
        trace_line = 'Tools attempted: ' if error else 'Tools used: '
        outcome_line = 'Error: ' if error else 'Assistant > '
        with private_session_path.open('a', encoding='utf-8') as log:
            log.write('You > ' + question + '\n' + trace_line + (', '.join(trace) or 'none')
                      + '\n' + outcome_line + response + '\n\n')

    tools = LocalTools(root)
    if args.check_local:
        print("Checking local-only dependencies (no network calls)...")
        product = tools.search_product_brochures("pressure filtration changing feed")
        print(f"Product retrieval usable: {bool(product['items'])}")
        from metso_agent.estimation.cost_estimator import load_ledger
        ledger = load_ledger(root / "local_cache" / "service_ledger.json")
        print(f"Service ledger readable: {len(ledger)} reports")
        print("Check completed without external API calls.")
        return
    if not args.allow_external_evidence:
        parser.error("External processing is disabled. Use --check-local first; "
                     "only use --allow-external-evidence if sharing restricted excerpts is authorized.")
    load_dotenv(root / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        parser.error("Missing OPENAI_API_KEY in private .env")
    model = args.model or os.getenv("OPENAI_MODEL")
    if not model or model == "YOUR_SUPPORTED_MODEL":
        parser.error("Set OPENAI_MODEL to a real accessible model ID in private .env")
    from openai import OpenAI
    # Environment variable OPENAI_API_KEY is loaded by the SDK; never print it.
    client = OpenAI(timeout=25.0, max_retries=1)
    agent = AgentController(tools, client, model=model, enforce_evidence_guards=True,
                            max_guard_repairs=1, enforce_complete_cost_routing=True,
                            use_safe_evidence_fallback=True)  # STAGE09_SAFE_FALLBACK_V1
    print("Metso Evidence Agent / Stage 06. Type 'exit' to stop.")
    print("Warning: selected private evidence excerpts can be transmitted to your API provider.")
    while True:
        try:
            question = input("\nYou > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break
        if question.casefold() in {"exit", "quit"}:
            print("Session ended.")
            break
        if not question:
            continue
        try:
            answer = agent.turn(question)
            if args.verbose:
                print("Tools used:", ", ".join(agent.last_trace) or "none")
            print("\nAssistant >", answer)
            _record_private(question, agent.last_trace, answer)
        except (ValueError, AgentRuntimeError) as exc:
            if args.verbose:
                print("Tools attempted:", ", ".join(agent.last_trace) or "none")
            print("\nError:", exc)
            _record_private(question, agent.last_trace, str(exc), error=True)


if __name__ == "__main__":
    main()
