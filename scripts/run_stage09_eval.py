"""Stage 09 local evaluation; no API requests or raw document export.

Usage:
 python scripts/run_stage09_eval.py retrieval
 python scripts/run_stage09_eval.py transcript --log local_cache/stage09_live.txt
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from metso_agent.evaluation.metrics import (
    load_cases, evaluate_transcript, score_sources, retrieval_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description='Metso Stage 09, offline evaluation')
    parser.add_argument('mode', choices=('retrieval', 'transcript'))
    parser.add_argument('--gold', default='docs/private/stage09_gold_cases.jsonl')
    parser.add_argument('--log', help='Terminal transcript text, only for transcript mode')
    parser.add_argument('--output', default=None, help='Optional sanitized JSON summary; use local_cache/')
    args = parser.parse_args()
    cases = load_cases(args.gold)
    if args.mode == 'transcript':
        if not args.log:
            parser.error('transcript mode requires --log')
        result = evaluate_transcript(cases, Path(args.log).read_text(encoding='utf-8-sig', errors='replace'))
        print(f"Live transcript — {result['matched']} matched turns; "
              f"route passes {result['route_pass']}; complete responses {result['full_pass']}")
        for item in result['cases']:
            print(f"{item['id']}: routed={item['route_pass']} answered={item['response_pass']} "
                  f"expected={','.join(item['expected_tools'])} actual={','.join(item['observed_tools'])}")
        if result['matched'] == 0:
            print('NO_MATCHES: copy the exact labeled prompts into the CLI before grading.')
    else:
        from metso_agent.retrieval.brochure_loader import load_brochures
        from metso_agent.retrieval.product_search import ProductSearcher
        root = Path.cwd()
        source_dir = root / 'raw' / 'data' / 'brochures'
        if not source_dir.is_dir():
            parser.error(f'Local source directory missing: {source_dir}')
        # Match the actual production retrieval implementation, without API use.
        searcher = ProductSearcher(load_brochures(source_dir))
        evaluated = []
        for c in cases:
            if not c.get('retrieval_query'):
                continue
            query = c['retrieval_query']
            hits = searcher.search(query, top_k=5)
            returned = [h.evidence.source.document_id for h in hits]
            row = {'id': c['id'], **score_sources(c['expected_sources'], returned)}
            evaluated.append(row)
            print(f"{c['id']}: hit@5={int(row['hit_at_5'])}, source_recall@5="
                  f"{row['source_recall_at_5']:.2f}, missing={','.join(row['missing_sources']) or '-'}")
        result = retrieval_summary(evaluated)
        print(f"Retrieval: {result['n']} labeled queries, macro recall@5="
              f"{result['macro_recall_at_5']}, hit rate@5={result['hit_rate_at_5']}")
    if args.output:
        dest = Path(args.output)
        # Ensure no accidental write outside private local_cache.
        cache = (Path.cwd() / 'local_cache').resolve()
        if not dest.resolve().is_relative_to(cache):
            parser.error('--output must be under project local_cache/ to avoid publication')
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(f'Sanitized summary written to: {dest}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
