"""Apply a narrowly scoped, idempotent Stage 07 integration to Stage 06.

Run from project root with: python scripts/apply_stage07_guard.py
Backups are written under ignored local_cache/stage07_backups/.
The script aborts without replacing files if expected Stage06 snippets differ.
"""
from pathlib import Path
from datetime import datetime, timezone
import sys

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / 'src/metso_agent/agent/controller.py'
CHAT = ROOT / 'src/metso_agent/agent/chat.py'
TOKEN = 'STAGE07_EVIDENCE_GUARD'


def replacements() -> dict[Path, list[tuple[str, str]]]:
    return {
        CONTROLLER: [
            ('from metso_agent.agent.tools import TOOL_SCHEMAS',
             'from metso_agent.agent.tools import TOOL_SCHEMAS\nfrom metso_agent.validation.response_guard import validate_answer  # STAGE07_EVIDENCE_GUARD'),
            ('max_rounds: int = 4, max_calls: int = 6,',
             'max_rounds: int = 4, max_calls: int = 6,\n        enforce_evidence_guards: bool = False,'),
            ('self.max_calls = max_calls',
             'self.max_calls = max_calls\n        self.enforce_evidence_guards = enforce_evidence_guards'),
            ('self.last_trace = []\n        # Carry only',
             'self.last_trace = []\n        tool_evidence: list[tuple[str, dict]] = []\n        # Carry only'),
            ('if not answer:\n                        raise AgentRuntimeError("Model returned no usable answer")\n                    self.history.extend',
             'if not answer:\n                        raise AgentRuntimeError("Model returned no usable answer")\n                    if self.enforce_evidence_guards:\n                        verdict = validate_answer(answer, tool_evidence)\n                        if not verdict.ok:\n                            raise AgentRuntimeError("Evidence guard rejected response: " + ", ".join(verdict.issues))\n                    self.history.extend'),
            ('result = self.tools.dispatch(name, args)\n                        output = json.dumps',
             'result = self.tools.dispatch(name, args)\n                        tool_evidence.append((name, result))\n                        output = json.dumps'),
        ],
        CHAT: [
            ('agent = AgentController(tools, client, model=model)',
             'agent = AgentController(tools, client, model=model, enforce_evidence_guards=True)'),
        ],
    }


def main() -> int:
    changes: dict[Path, tuple[str, str]] = {}
    for path, rules in replacements().items():
        if not path.is_file():
            print(f'Missing expected Stage06 file: {path}', file=sys.stderr)
            return 2
        old = path.read_text(encoding='utf-8')
        if TOKEN in old and path == CONTROLLER:
            print('Stage07 guard already installed in controller; nothing changed.')
            return 0
        new = old
        for before, after in rules:
            if new.count(before) != 1:
                print(f'Unexpected Stage06 source layout in {path.name}; stopped before modifying any file.\n'
                      f'Expected snippet: {before[:110]}', file=sys.stderr)
                return 2
            new = new.replace(before, after, 1)
        changes[path] = (old, new)
    backup_root = ROOT / 'local_cache' / 'stage07_backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup_root.mkdir(parents=True, exist_ok=False)
    for path, (old, _) in changes.items():
        (backup_root / path.name).write_text(old, encoding='utf-8')
    for path, (_, new) in changes.items():
        path.write_text(new, encoding='utf-8')
        print(f'Patched: {path.relative_to(ROOT)}')
    print(f'Ignored backups: {backup_root.relative_to(ROOT)}')
    print('Run pytest now; do not deploy before all tests and a live check pass.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
