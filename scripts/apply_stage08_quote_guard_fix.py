"""Minimal Stage 08-compatible patch for site-quote negation false positives.

Run from project root. No changes to any existing file except response_guard.py.
The old file is backed up to ignored local_cache/; anchors are checked first.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'src' / 'metso_agent' / 'validation' / 'response_guard.py'
MARKER = 'STAGE08_QUOTE_NEGATION_FIX_V1'
OLD = '''                quote_claim = re.search(r"\\b(?:confirmed|final|official|binding|verified)\\s+"
                                        r"(?:chile(?:an)?\\s+)?(?:quote|quotation|price|budget)\\b", answer, re.I)
                if quote_claim:
                    preceding = answer[max(0, quote_claim.start() - 50):quote_claim.start()]
                    # Negated claims such as "not an official Chile quote" are not affirmative quotes.
                    negated = re.search(r"\\b(?:not|never|no)\\s+(?:(?:a|an|the)\\s+)?$", preceding, re.I)
                    if not negated:
                        problems.append("UNSUPPORTED_SITE_SPECIFIC_QUOTE")
'''
NEW = '''                # STAGE08_QUOTE_NEGATION_FIX_V1
                # Examine EACH potential quote claim, not just the first one.
                # Explicitly negative statements must be allowed (we have no quote),
                # but any affirmative claim for an unsupported site remains blocked.
                quote_pattern = (r"\\b(?:confirmed|final|official|binding|verified)\\s+"
                                 r"(?:chile(?:an)?\\s+)?(?:quote|quotation|price|budget)\\b")
                for quote_claim in re.finditer(quote_pattern, answer, re.I):
                    preceding = answer[max(0, quote_claim.start() - 140):quote_claim.start()]
                    # Keep negations local to their clause: "not ...; but confirmed ..."
                    # must never let the earlier "not" excuse the later claim.
                    clause = re.split(r"[.!?;:,\\n]|\\b(?:but|however|yet)\\b", preceding, flags=re.I)[-1]
                    negated_before = bool(re.search(
                        r"\\b(?:not|never|no|cannot|can't|isn't|aren't|wasn't|weren't|"
                        r"don't|doesn't|didn't|shouldn't|mustn't|without)\\b"
                        r"(?:\\s+[\\w'-]+){0,12}\\s*$", clause, re.I))
                    trailing = answer[quote_claim.end():quote_claim.end() + 75]
                    negated_after = bool(re.match(
                        r"\\s+(?:(?:is|was|remains)\\s+(?:not\\s+(?:available|known|"
                        r"confirmed|established|provided)|unavailable|unknown|unconfirmed)|"
                        r"has\\s+not\\s+(?:been\\s+)?(?:issued|provided|established))\\b",
                        trailing, re.I))
                    if not (negated_before or negated_after):
                        problems.append("UNSUPPORTED_SITE_SPECIFIC_QUOTE")
                        break
'''

def main():
    if not TARGET.is_file():
        print(f'File not found: {TARGET}', file=sys.stderr)
        return 2
    content = TARGET.read_text(encoding='utf-8')
    if MARKER in content:
        print('Site quote guard fix already installed; no changes made.')
        return 0
    if content.count(OLD) != 1:
        print('Layout mismatch: existing quote guard has changed. No files modified.', file=sys.stderr)
        return 2
    backup = ROOT / 'local_cache' / 'stage08_backups' / ('quote_guard_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ%f'))
    backup.mkdir(parents=True, exist_ok=False)
    (backup / TARGET.name).write_text(content, encoding='utf-8')
    updated = content.replace(OLD, NEW, 1)
    TARGET.write_text(updated, encoding='utf-8')
    print('Patched:', TARGET.relative_to(ROOT))
    print('Private backup:', backup.relative_to(ROOT))
    print('NEXT: Run 12 new tests, then the complete pytest suite before the live API.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
