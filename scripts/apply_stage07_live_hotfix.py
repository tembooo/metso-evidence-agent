"""Safely patch Stage07 Agent Controller: grounded one-pass repair + missing tool reroute.

Run from project root (after Stage07 integration). Backs up originals under ignored
local_cache. Checks all anchors before modifying any file. Idempotent.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / 'src/metso_agent/agent/controller.py'
CHAT = ROOT / 'src/metso_agent/agent/chat.py'
GUARD = ROOT / 'src/metso_agent/validation/response_guard.py'
MARKER = 'STAGE07_LIVE_HOTFIX_V1'


def edits() -> dict[Path, list[tuple[str, str]]]:
    classifier = '''def _complete_cost_request(text: str) -> bool:
    """Conservative heuristic: route fully specified service-budget requests.

    This is not a semantic parser; ambiguous requests can still need clarification.
    Avoid hardcoding a particular site, product, quantity or currency.
    """
    return bool(
        re.search(r"\\b(?:budget|cost|costs|estimate|quotation|quote|price)\\b", text, re.I)
        and re.search(r"\\b\\d+\\s+(?:[a-z-]+\\s+){0,3}(?:cloths?|parts?|units?|filters?)\\b", text, re.I)
        and re.search(r"\\b(?:replac\\w*|repair\\w*|service|maintenance)\\b", text, re.I)
        and re.search(r"\\b(?:filter|press|pump|equipment|machine|unit)\\b", text, re.I)
        and re.search(r"\\b(?:in|at)\\s+[A-Z][a-z]{2,}\\b", text)
    )


'''
    return {
        CONTROLLER: [
            ('import json\nfrom typing import Any', 'import json\nimport re\nfrom typing import Any'),
            ('class AgentRuntimeError(RuntimeError):',
             '# STAGE07_LIVE_HOTFIX_V1\n' + classifier + 'class AgentRuntimeError(RuntimeError):'),
            ('        enforce_evidence_guards: bool = False,\n',
             '        enforce_evidence_guards: bool = False,\n'
             '        max_guard_repairs: int = 0, enforce_complete_cost_routing: bool = False,\n'),
            ('        self.enforce_evidence_guards = enforce_evidence_guards\n',
             '        self.enforce_evidence_guards = enforce_evidence_guards\n'
             '        self.max_guard_repairs = max_guard_repairs\n'
             '        self.enforce_complete_cost_routing = enforce_complete_cost_routing\n'),
            ('        total_calls = 0\n        try:',
             '        total_calls = 0\n'
             '        repair_count = 0\n'
             '        repair_note = ""\n'
             '        force_cost_tool = False\n'
             '        requires_cost_tool = self.enforce_complete_cost_routing and _complete_cost_request(user_text)\n'
             '        try:'),
            ('                    instructions=SYSTEM_RULES,\n',
             '                    instructions=SYSTEM_RULES + repair_note,\n'),
            ('                    tool_choice="auto",\n',
             '                    tool_choice=({"type": "function", "name": "compare_service_costs"}\n'
             '                                 if force_cost_tool and not tool_evidence else "auto"),\n'),
            ('                if not calls:\n                    answer = (response.output_text or "").strip()',
             '                if not calls:\n'
             '                    if requires_cost_tool and not any(name == "compare_service_costs" for name, _ in tool_evidence):\n'
             '                        if not force_cost_tool:\n'
             '                            force_cost_tool = True\n'
             '                            continue  # One forced tool call when a complete cost request was ignored.\n'
             '                        raise AgentRuntimeError("Cost evidence tool was not called for a complete cost request")\n'
             '                    answer = (response.output_text or "").strip()'),
            ('                        if not verdict.ok:\n                            raise AgentRuntimeError("Evidence guard rejected response: " + ", ".join(verdict.issues))',
             '                        if not verdict.ok:\n'
             '                            if repair_count < self.max_guard_repairs:\n'
             '                                repair_count += 1\n'
             '                                repair_note = ("\\nVALIDATION RETRY: Previous draft failed checks: "\n'
             '                                               + ", ".join(verdict.issues)\n'
             '                                               + ". Re-compose ONLY from the tool evidence already available. "\n'
             '                                               "Use exact monetary amounts in the tool result; "\n'
             '                                               "do not round to arbitrary budgets or invent Chile quotes. "\n'
             '                                               "Clearly distinguish historical items from site-specific pricing. "\n'
             '                                               "Do not make unsupported cost guarantees. "\n'
             '                                               "If evidence is insufficient, explicitly abstain.\\n")\n'
             '                                continue\n'
             '                            raise AgentRuntimeError("Evidence guard rejected response: " + ", ".join(verdict.issues))'),
        ],
        GUARD: [
            ('                if re.search(r"\\b(?:confirmed|final|official|binding|verified)\\s+"\n                             r"(?:chile(?:an)?\\s+)?(?:quote|quotation|price|budget)\\b", answer, re.I):\n                    problems.append("UNSUPPORTED_SITE_SPECIFIC_QUOTE")\n',
             '                quote_claim = re.search(r"\\b(?:confirmed|final|official|binding|verified)\\s+"\n                                        r"(?:chile(?:an)?\\s+)?(?:quote|quotation|price|budget)\\b", answer, re.I)\n                if quote_claim:\n                    preceding = answer[max(0, quote_claim.start() - 50):quote_claim.start()]\n                    # Negated claims such as "not an official Chile quote" are not affirmative quotes.\n                    negated = re.search(r"\\b(?:not|never|no)\\s+(?:(?:a|an|the)\\s+)?$", preceding, re.I)\n                    if not negated:\n                        problems.append("UNSUPPORTED_SITE_SPECIFIC_QUOTE")\n'),
        ],
        CHAT: [
            ('agent = AgentController(tools, client, model=model, enforce_evidence_guards=True)',
             'agent = AgentController(tools, client, model=model, enforce_evidence_guards=True,\n'
             '                            max_guard_repairs=1, enforce_complete_cost_routing=True)'),
            ('        except (ValueError, AgentRuntimeError) as exc:\n            print("\\nError:", exc)',
             '        except (ValueError, AgentRuntimeError) as exc:\n'
             '            if args.verbose:\n'
             '                print("Tools attempted:", ", ".join(agent.last_trace) or "none")\n'
             '            print("\\nError:", exc)'),
        ],
    }


def main() -> int:
    planned = {}
    for path, rules in edits().items():
        if not path.is_file():
            print(f"File missing: {path}", file=sys.stderr)
            return 2
        before = path.read_text(encoding='utf-8')
        if path == CONTROLLER and MARKER in before:
            print('Stage07 live hotfix already installed; no changes needed.')
            return 0
        after = before
        for old, new in rules:
            if after.count(old) != 1:
                print(f'Layout mismatch in {path.name}; no files modified.\nExpected: {old[:110]}', file=sys.stderr)
                return 2
            after = after.replace(old, new, 1)
        planned[path] = (before, after)
    backup = ROOT / 'local_cache' / 'stage07_backups' / ('live_hotfix_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ%f'))
    backup.mkdir(parents=True)
    for path, (before, _) in planned.items():
        (backup / path.name).write_text(before, encoding='utf-8')
    for path, (_, after) in planned.items():
        path.write_text(after, encoding='utf-8')
        print('Patched:', path.relative_to(ROOT))
    print('Private backups:', backup.relative_to(ROOT))
    print('NEXT: run pytest before calling the live API.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
