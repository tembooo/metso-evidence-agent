"""Stage 09 evaluation contract tests, all offline and synthetic."""
import json

import pytest

from metso_agent.evaluation.metrics import (
    EvaluationInputError, canonical, evaluate_transcript, load_cases,
    parse_chat_log, retrieval_summary, score_route, score_sources,
)


def test_canonical_normalizes_typographic_quotes_and_spacing():
    assert canonical(' What’s  NORMAL? ') == canonical("What's normal")


def test_parse_two_turns_and_multiple_tool_names():
    log = ('You > combined question\nTools used: search_product_brochures, compare_service_costs\n'
           'Assistant > Supported response\nYou > another question\nTools used: none\n'
           'Assistant > Need more information\n')
    rows = parse_chat_log(log)
    assert len(rows) == 2
    assert rows[0]['tools'] == ['search_product_brochures', 'compare_service_costs']
    assert rows[1]['tools'] == []


def test_attempted_tool_and_guard_error_not_full_success():
    rows = parse_chat_log('You > cost request\nTools attempted: compare_service_costs\n'
                          'Error: Evidence guard rejected response\n')
    assert rows[0]['error']
    assert not score_route({'id':'C','expected_tools':['compare_service_costs']}, rows[0])['full_pass']


def test_wrong_tool_fails_routing():
    row = {'prompt':'x','tools':['analyze_flotation'],'answer_seen':True,'error':False}
    assert not score_route({'id':'P','expected_tools':['search_product_brochures']},row)['route_pass']


def test_mixed_two_tools_pass_independent_of_order():
    row = {'prompt':'x','tools':['compare_service_costs','search_product_brochures'],'answer_seen':True,'error':False}
    assert score_route({'id':'M','expected_tools':['search_product_brochures','compare_service_costs']},row)['full_pass']


def test_extra_tool_counts_as_routing_mismatch():
    row={'prompt':'x','tools':['search_product_brochures','compare_service_costs'],'answer_seen':True,'error':False}
    assert not score_route({'id':'P','expected_tools':['search_product_brochures']},row)['route_pass']


def test_optional_clarification_accepts_no_tool():
    row={'prompt':'x','tools':[],'answer_seen':True,'error':False}
    assert score_route({'id':'N','expected_tools':[],'route_policy':'optional'},row)['full_pass']


def test_exact_clarification_rejects_unnecessary_tool():
    row={'prompt':'x','tools':['compare_service_costs'],'answer_seen':True,'error':False}
    assert not score_route({'id':'N','expected_tools':[]},row)['route_pass']


def test_missing_answer_does_not_count_as_completion():
    row={'prompt':'x','tools':['search_product_brochures'],'answer_seen':False,'error':False}
    assert not score_route({'id':'P','expected_tools':['search_product_brochures']},row)['full_pass']


def test_retrieval_recall_is_fraction_of_labeled_sources():
    scored=score_sources(['filter-optimizer','larox-pf-ds'], ['larox-pf-ds', 'orion-series-pump'])
    assert scored['source_recall_at_5']==0.5
    assert scored['hit_at_5']


def test_retrieval_k_excludes_sixth_hit():
    scored=score_sources(['target'], ['a','b','c','d','e','target'])
    assert not scored['hit_at_5']


def test_retrieval_summary_is_macro_not_micro():
    scored=[score_sources(['a','b'], ['a']),score_sources(['c'], ['c'])]
    assert retrieval_summary(scored)['macro_recall_at_5']==0.75


def test_empty_retrieval_score_is_unavailable_not_perfect():
    assert retrieval_summary([])['macro_recall_at_5'] is None


def test_transcript_only_grades_exact_labeled_prompts():
    cases=[{'id':'A','prompt':'exact test','expected_tools':['search_product_brochures']}]
    log=('You > Unrelated\nTools used: none\nAssistant > hello\n'
         'You > exact test\nTools used: search_product_brochures\nAssistant > cited answer')
    result=evaluate_transcript(cases,log)
    assert result['matched']==1 and result['route_accuracy']==1


def test_evaluation_output_never_contains_assistant_answer():
    cases=[{'id':'A','prompt':'exact test','expected_tools':[]}]
    result=evaluate_transcript(cases,'You > exact test\nTools used: none\nAssistant > PRIVATE SNIPPET SECRET')
    assert 'PRIVATE SNIPPET SECRET' not in json.dumps(result)


def test_duplicate_ids_are_rejected(tmp_path):
    p=tmp_path/'gold.jsonl'
    rec={'id':'P01','prompt':'x','expected_tools':[]}
    p.write_text(json.dumps(rec)+'\n'+json.dumps(rec)+'\n',encoding='utf8')
    with pytest.raises(EvaluationInputError,match='Duplicate'):
        load_cases(p)


def test_incorrect_gold_route_policy_is_rejected(tmp_path):
    p=tmp_path/'gold.jsonl'
    p.write_text(json.dumps({'id':'P','prompt':'test','expected_tools':[], 'route_policy':'magic'}))
    with pytest.raises(EvaluationInputError):
        load_cases(p)
