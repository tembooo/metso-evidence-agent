"""Idempotent, narrowly gated Stage 09 patch for an existing Stage 07/08 Metso project.

Run only after Stage 09 baseline tests. Preserves existing code and stores backups
under local_cache. Never copies proprietary evidence or API credentials.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

MARK = "STAGE09_SAFE_FALLBACK_V1"
GUARD_MARK = "STAGE09_GUARANTEE_NEGATION_V1"


def patch_files(root: Path) -> list[str]:
    guard = root / "src/metso_agent/validation/response_guard.py"
    controller = root / "src/metso_agent/agent/controller.py"
    cli = root / "src/metso_agent/agent/chat.py"
    files = [guard, controller, cli]
    for path in files:
        if not path.is_file():
            raise RuntimeError(f"Missing expected file: {path.relative_to(root)}")
    src = {p: p.read_text(encoding="utf-8") for p in files}
    if GUARD_MARK in src[guard] and MARK in src[controller] and MARK in src[cli]:
        print("Already installed (idempotent): no changes needed.")
        return []
    if any(x in src[guard]+src[controller]+src[cli] for x in [GUARD_MARK, MARK]):
        raise RuntimeError("Partial/unknown Stage09 patch already present. Stop and review backups; no files were changed.")
    if "STAGE08_QUOTE_NEGATION_FIX_V1" not in src[guard]:
        raise RuntimeError("Expected Stage 08 quote negation fix not found. No files changed.")
    if "STAGE07_LIVE_HOTFIX_V1" not in src[controller] or "STAGE08_FLOTATION" not in src[controller]:
        raise RuntimeError("Expected Stage 07/08 controller markers not found. No files changed.")

    before = "    # This flag is deliberately narrow: no guarantee for unmeasured results.\n    if UNSUPPORTED_GUARANTEE.search(answer):\n        problems.append(\"UNSUPPORTED_PERFORMANCE_GUARANTEE\")"
    assert src[guard].count(before) == 1, "Unknown guard version; no files changed"
    helper = '''# STAGE09_GUARANTEE_NEGATION_V1
# Classify promises separately per clause, preserving an affirmative promise
# after a rejected or negated promise in the same response.
def _asserts_unsupported_guarantee(answer: str) -> bool:
    clauses = re.split(r"(?<!\\d)\\.(?!\\d)|[!?;\\n]|\\b(?:but|however|yet|although|nevertheless)\\b", answer, flags=re.I)
    for clause in clauses:
        for match in UNSUPPORTED_GUARANTEE.finditer(clause):
            preceding = clause[max(0, match.start() - 90): match.start()]
            denial = re.search(
                r"\\b(?:cannot|can\\s+not|can't|do\\s+not|don't|does\\s+not|doesn't|"
                r"will\\s+not|won't|never|no|not|unable\\s+to|not\\s+able\\s+to)\\b"
                r"(?:\\s+[\\w'-]+){0,5}\\s*$", preceding, flags=re.I,
            )
            if not denial:
                return True
    return False


'''
    assert src[guard].count("def validate_answer(") == 1
    new_guard = src[guard].replace("def validate_answer(", helper + "def validate_answer(", 1)
    new_guard = new_guard.replace(before, "    # Preserve guard against positive guarantees while allowing explicit denial.\n    if _asserts_unsupported_guarantee(answer):\n        problems.append(\"UNSUPPORTED_PERFORMANCE_GUARANTEE\")", 1)

    ctrl = src[controller]
    constructor = '        max_guard_repairs: int = 0, enforce_complete_cost_routing: bool = False,\n'
    assert ctrl.count(constructor) == 1, "Unknown controller signature; no files changed"
    ctrl = ctrl.replace(constructor, constructor + '        use_safe_evidence_fallback: bool = False,\n', 1)
    anchor = '        self.enforce_complete_cost_routing = enforce_complete_cost_routing\n'
    assert ctrl.count(anchor) == 1
    ctrl = ctrl.replace(anchor, anchor + '        self.use_safe_evidence_fallback = use_safe_evidence_fallback\n', 1)
    old_block = ('                            raise AgentRuntimeError("Evidence guard rejected response: " + ", ".join(verdict.issues))\n')
    assert ctrl.count(old_block) == 1
    new_block = '''                            if self.use_safe_evidence_fallback:
                                recovered = _stage09_safe_fallback(user_text, verdict.issues, tool_evidence)
                                if recovered and validate_answer(recovered, tool_evidence).ok:
                                    answer = recovered
                                else:
                                    raise AgentRuntimeError("Evidence guard rejected response: " + ", ".join(verdict.issues))
                            else:
                                raise AgentRuntimeError("Evidence guard rejected response: " + ", ".join(verdict.issues))
'''
    ctrl = ctrl.replace(old_block, new_block, 1)
    assert ctrl.count("class AgentRuntimeError(RuntimeError):") == 1
    fallback = '''# STAGE09_SAFE_FALLBACK_V1
# This safety net only emits pre-authored, bounded, checkable text after a
# model draft and its one repair have failed evidence validation. All figures
# and report IDs are taken from the *current turn's* structured tool result.
def _stage09_safe_fallback(user_text: str, issues: tuple[str, ...], evidence: list[tuple[str, dict]]) -> str | None:
    reasons = set(issues)
    if "UNSUPPORTED_PERFORMANCE_GUARANTEE" in reasons and re.search(
        r"\\b(?:guarantee|guaranteed|promise|savings?)\\b", user_text, re.I
    ):
        return ("I cannot guarantee a numerical saving or performance improvement from the supplied "
                "product documentation. An equipment recommendation requires checking the "
                "specific installation and collecting relevant baseline data.")

    currencies = set(re.findall(r"\\b(?:EUR|USD|CAD|SEK|AUD|ZAR)\\b", user_text, re.I))
    if "UNSUPPORTED_MONETARY_AMOUNT" in reasons and len({s.upper() for s in currencies}) >= 2:
        return ("Amounts expressed in different currencies cannot be added directly into a "
                "verified budget. A documented conversion rate and valuation date would be "
                "required. No confirmed site-specific price follows from the provided example.")

    if reasons.intersection({"UNSUPPORTED_SITE_SPECIFIC_QUOTE", "UNSUPPORTED_MONETARY_AMOUNT"}):
        for tool, output in reversed(evidence):
            if tool != "compare_service_costs" or not isinstance(output, dict) or output.get('status') == 'TOOL_ERROR':
                continue
            best = output.get('best_historical_analog') or {}
            rid = best.get('report_id')
            reconstructed = best.get('reconstructed') or {}
            amount, currency = reconstructed.get('amount'), reconstructed.get('currency')
            if not isinstance(rid, str) or not re.fullmatch(r'FSR-\\d{4}', rid):
                continue
            if isinstance(currency, str) and currency in ('EUR', 'USD', 'CAD', 'SEK', 'AUD', 'ZAR'):
                try:
                    from decimal import Decimal
                    total = Decimal(str(amount))
                    if total.is_finite() and total >= 0:
                        rendered = f"{total:.2f} {currency}"
                        return (f"The nearest historical service record is {rid}. Its provisional "
                                f"component sum is {rendered}, reconstructed from recorded items. "
                                "This is historical evidence, not a current site-specific quotation. "
                                "The source may be incomplete. Please confirm the customer site "
                                "and who supplies the replacement parts before requesting a local quote.")
                except (TypeError, ValueError, ArithmeticError):
                    pass
            return (f"The closest available historical service record is {rid}, but the "
                    "supplied evidence does not establish a supported site-specific budget. "
                    "Please confirm the customer site and parts supplier.")
    return None


'''
    ctrl = ctrl.replace("class AgentRuntimeError(RuntimeError):", fallback + "class AgentRuntimeError(RuntimeError):", 1)
    old_rules = "This is engineering planning support, not an official quotation.\n"
    assert ctrl.count(old_rules) == 1
    extra_rules = '''This is engineering planning support, not an official quotation.
If a user requests a fabricated benefit, explain why it cannot be guaranteed:
DO NOT restate a positive savings guarantee. If a user suggests arithmetic
between different currencies, explain that it is invalid WITHOUT echoing any
hypothetical monetary values from the customer as established prices.
The source set contains Chilean historical services with OTHER work scopes;
never claim Chile has no service reports. No exact Chile PF-DS 12-cloth
replacement analog is established. Feed grade is not by itself proof of a
specific slurry-property change or proven diagnosis.
'''
    ctrl = ctrl.replace(old_rules, extra_rules, 1)

    cli_src = src[cli]
    cli_anchor = "max_guard_repairs=1, enforce_complete_cost_routing=True)"
    assert cli_src.count(cli_anchor) == 1, "Unknown CLI setup; no files changed"
    new_cli = cli_src.replace(cli_anchor, "max_guard_repairs=1, enforce_complete_cost_routing=True,\n                            use_safe_evidence_fallback=True)  # STAGE09_SAFE_FALLBACK_V1", 1)

    # An opt-in CLI transcript writer avoids Start-Transcript missing Python I/O.
    main_anchor = "def main() -> None:\n"
    assert new_cli.count(main_anchor) == 1
    session_helper = """# STAGE09_PRIVATE_SESSION_LOG_V1
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


"""
    new_cli = new_cli.replace(main_anchor, session_helper + main_anchor, 1)
    option_anchor = '    parser.add_argument("--verbose", action="store_true", help="Show called tool names only")\n'
    assert new_cli.count(option_anchor) == 1
    new_cli = new_cli.replace(option_anchor, option_anchor + '    parser.add_argument("--session-log", help="Log interactive conversation privately under local_cache")\n', 1)
    parse_anchor = '    args = parser.parse_args()\n'
    assert new_cli.count(parse_anchor) == 1
    init_block = r"""    try:
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

"""
    new_cli = new_cli.replace(parse_anchor, parse_anchor + init_block, 1)
    answer_anchor = '            print("\\nAssistant >", answer)\n'
    assert new_cli.count(answer_anchor) == 1
    new_cli = new_cli.replace(answer_anchor, answer_anchor + '            _record_private(question, agent.last_trace, answer)\n', 1)
    error_anchor = '            print("\\nError:", exc)\n'
    assert new_cli.count(error_anchor) == 1
    new_cli = new_cli.replace(error_anchor, error_anchor + '            _record_private(question, agent.last_trace, str(exc), error=True)\n', 1)

    changes = {guard: new_guard, controller: ctrl, cli: new_cli}
    # Compile all candidate files before writing anything.
    for path, body in changes.items():
        compile(body, str(path), 'exec')
    backup = root / 'local_cache' / 'stage09_backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup.mkdir(parents=True, exist_ok=False)
    for p in files:
        shutil.copy2(p, backup / p.name)
    for path, body in changes.items():
        path.write_text(body, encoding='utf-8')
        print("Patched:", path.relative_to(root))
    print("Backups:", backup.relative_to(root))
    print("Run Stage09 safety tests and the full pytest suite before any live API call.")
    return [str(p) for p in changes]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    try:
        patch_files(root)
    except (AssertionError, RuntimeError, OSError, SyntaxError) as exc:
        print("STOP — patch not applied:", exc, file=sys.stderr)
        raise SystemExit(2)


if __name__ == '__main__':
    main()
