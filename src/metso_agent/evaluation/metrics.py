"""Stage 09: evaluate observed tool routes and retrieval without an LLM judge.

Only route/tool names, case IDs, counts, and source identifiers are reported.
Source contents and model replies are deliberately excluded from outputs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


class EvaluationInputError(ValueError):
    """An evaluation input has a missing or malformed required field."""


def load_cases(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Evaluation case file is absent: {path}")
    cases: list[dict] = []
    ids: set[str] = set()
    for n, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as e:
            raise EvaluationInputError(f"Bad JSONL at line {n}") from e
        if not isinstance(case, dict) or not isinstance(case.get('id'), str) or not case['id']:
            raise EvaluationInputError(f"Missing id at line {n}")
        if case['id'] in ids:
            raise EvaluationInputError(f"Duplicate case id: {case['id']}")
        if not isinstance(case.get('prompt'), str) or not case['prompt'].strip():
            raise EvaluationInputError(f"Missing prompt for {case['id']}")
        if not isinstance(case.get('expected_tools'), list) or not all(isinstance(t, str) for t in case['expected_tools']):
            raise EvaluationInputError(f"Invalid expected_tools for {case['id']}")
        if case.get('route_policy', 'exact') not in ('exact', 'optional'):
            raise EvaluationInputError(f"Invalid route_policy for {case['id']}")
        ids.add(case['id'])
        cases.append(case)
    if not cases:
        raise EvaluationInputError('No cases found')
    return cases


def canonical(text: str) -> str:
    """Normalize only whitespace and typographic apostrophes; do not fuzzily match intents."""
    return ' '.join(text.replace('’', "'").split()).strip().rstrip('.?!').casefold()


def parse_chat_log(text: str) -> list[dict]:
    """Read the CLI log format; never include reply text in the returned records."""
    turns: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        m = re.search(r'(?:^|\s)You\s*>\s*(.*)$', line)
        if m:
            prompt = m.group(1).strip()
            if current:
                turns.append(current)
            current = {'prompt': prompt, 'tools': [], 'answer_seen': False, 'error': False}
            continue
        if current is None:
            continue
        routed = re.search(r'\bTools\s+(?:used|attempted):\s*(.*)$', line)
        if routed:
            value = routed.group(1).strip()
            if value.casefold() != 'none':
                current['tools'].extend([a.strip() for a in value.split(',') if a.strip()])
        if re.search(r'\bAssistant\s*>\s*\S', line):
            current['answer_seen'] = True
        if re.search(r'^\s*Error:\s*', line):
            current['error'] = True
    if current:
        turns.append(current)
    return turns


def score_route(case: dict, turn: dict) -> dict:
    expected = set(case['expected_tools'])
    observed = set(turn['tools'])
    policy = case.get('route_policy', 'exact')
    routed = observed == expected if policy == 'exact' else (not observed or observed == expected)
    returned = bool(turn['answer_seen']) and not bool(turn['error'])
    return {'id': case['id'], 'expected_tools': sorted(expected), 'observed_tools': sorted(observed),
            'route_pass': routed, 'response_pass': returned, 'full_pass': routed and returned,
            'error': bool(turn['error'])}


def evaluate_transcript(cases: list[dict], text: str) -> dict:
    by_prompt = {canonical(c['prompt']): c for c in cases}
    results: list[dict] = []
    for turn in parse_chat_log(text):
        key = canonical(turn['prompt'])
        if key in by_prompt:
            results.append(score_route(by_prompt[key], turn))
    if not results:
        return {'matched': 0, 'route_pass': 0, 'response_pass': 0, 'full_pass': 0,
                'route_accuracy': None, 'full_success_rate': None, 'cases': []}
    return {'matched': len(results),
            'route_pass': sum(x['route_pass'] for x in results),
            'response_pass': sum(x['response_pass'] for x in results),
            'full_pass': sum(x['full_pass'] for x in results),
            'route_accuracy': round(sum(x['route_pass'] for x in results)/len(results), 4),
            'full_success_rate': round(sum(x['full_pass'] for x in results)/len(results), 4),
            'cases': results}


def score_sources(expected_sources: list[str], returned_sources: list[str], k: int = 5) -> dict:
    """True source recall@k plus any-relevant hit@k for one labeled query."""
    expected = {str(x).casefold() for x in expected_sources}
    if not expected:
        raise EvaluationInputError('Expected source list must not be empty')
    actual = {str(x).casefold() for x in returned_sources[:k]}
    hits = expected & actual
    return {'source_recall_at_5': round(len(hits) / len(expected), 4),
            'hit_at_5': bool(hits), 'found_sources': sorted(hits),
            'missing_sources': sorted(expected - actual)}


def retrieval_summary(results: list[dict]) -> dict:
    if not results:
        return {'n': 0, 'macro_recall_at_5': None, 'hit_rate_at_5': None, 'cases': []}
    return {'n': len(results),
            'macro_recall_at_5': round(sum(x['source_recall_at_5'] for x in results)/len(results), 4),
            'hit_rate_at_5': round(sum(x['hit_at_5'] for x in results)/len(results), 4),
            'cases': results}
