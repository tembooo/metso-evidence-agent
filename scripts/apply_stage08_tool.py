"""Opt-in Stage08 tool integration. Backs up existing Stage07-patched files.

Run from the project root only after the analyzer's independent tests pass.
Fails without changes when expected Stage06/Stage07 code anchors differ.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'src/metso_agent/agent/tools.py'
CONTROLLER = ROOT / 'src/metso_agent/agent/controller.py'
TOKEN = 'STAGE08_FLOTATION'

FLOTATION_SCHEMA = '''    {
        "type": "function",
        "name": "analyze_flotation",
        "description": "Descriptive analysis ONLY from the supplied hourly flotation CSV for iron/silica concentrate values. Do not infer contractual acceptance, process causality, or equipment guarantees.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "silica_pct": {"type": "number", "description": "Observed % silica in concentrate"},
                "iron_pct": {"type": "number", "description": "Observed % iron in concentrate"},
            },
            "required": ["silica_pct", "iron_pct"],
            "additionalProperties": False,
        },
    },
'''


def patch_rules():
    return {
        TOOLS: [
            (
                'from metso_agent.retrieval.brochure_loader import load_brochures',
                'from metso_agent.retrieval.brochure_loader import load_brochures\n'
                'from metso_agent.analytics.flotation import analyze_csv  # STAGE08_FLOTATION',
            ),
            (
                '    },\n]\n\n\nclass LocalTools:',
                '    },\n' + FLOTATION_SCHEMA + ']\n\n\nclass LocalTools:',
            ),
            (
                '    def dispatch(self, name: str, arguments: dict) -> dict:',
                '''    def analyze_flotation(self, silica_pct: float, iron_pct: float) -> dict:
        return analyze_csv(
            self.root / "raw" / "data" / "flotation_process_data_hourly.csv",
            silica_pct, iron_pct,
        )

    def dispatch(self, name: str, arguments: dict) -> dict:''',
            ),
            (
                '        raise ValueError("Tool is not on the allowlist")',
                '''        if name == "analyze_flotation":
            if set(arguments) != {"silica_pct", "iron_pct"}:
                raise ValueError("Invalid flotation tool arguments")
            return self.analyze_flotation(**arguments)
        raise ValueError("Tool is not on the allowlist")''',
            ),
        ],
        CONTROLLER: [
            (
                'This is engineering planning support, not an official quotation.\n',
                '''This is engineering planning support, not an official quotation.
For concentrate iron/silica quality questions, call analyze_flotation with the
user's observed percentages. Its sole data source is the supplied flotation
CSV. Cite that CSV and its row count; report means and threshold frequencies.
A historical reading is NOT a contractual acceptance limit; do not claim a
causal mechanism or guarantee an equipment intervention.  # STAGE08_FLOTATION
''',
            ),
        ],
    }


def main() -> int:
    rules = patch_rules()
    pending = {}
    for path, replacements in rules.items():
        if not path.is_file():
            print(f'Missing source file: {path}', file=sys.stderr)
            return 2
        old = path.read_text(encoding='utf-8')
        if TOKEN in old:
            print(f'Stage08 appears already applied in {path.name}; no files changed.')
            return 2  # requires both to be verified before acknowledging installed
        if path == CONTROLLER and 'STAGE07_EVIDENCE_GUARD' not in old:
            print('Stage07 guard not installed in controller; apply Stage07 first.', file=sys.stderr)
            return 2
        new = old
        for before, after in replacements:
            if new.count(before) != 1:
                print(f'Unexpected source layout in {path.name}; no files changed.\n'
                      f'Anchor: {before[:120]}', file=sys.stderr)
                return 2
            new = new.replace(before, after, 1)
        pending[path] = (old, new)
    if not (ROOT / 'src/metso_agent/analytics/flotation.py').is_file():
        print('Missing Stage08 analyzer; extract ZIP first.', file=sys.stderr)
        return 2
    backup = ROOT / 'local_cache/stage08_backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup.mkdir(parents=True, exist_ok=False)
    for p, (old, _) in pending.items():
        (backup / p.name).write_text(old, encoding='utf-8')
    for p, (_, new) in pending.items():
        p.write_text(new, encoding='utf-8')
        print(f'Patched: {p.relative_to(ROOT)}')
    print('Backups:', backup.relative_to(ROOT))
    print('Now run pytest -q, check-local, and live product/cost tests before the optional prompt.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
