"""Synthetic offline regression tests for the Stage07 live-response hotfix."""
from types import SimpleNamespace as SN
import json
import pytest

from metso_agent.agent.controller import AgentController, AgentRuntimeError, _complete_cost_request

COST = {
    'status': 'INSUFFICIENT_EVIDENCE_FOR_SITE_SPECIFIC_QUOTE',
    'site_specific_budget': None,
    'task_analogs': [{'report_id': 'FSR-0001'}],
    'best_historical_analog': {
        'report_id': 'FSR-0001',
        'reconstructed': {'amount': '120.00', 'currency': 'EUR'},
        'components': [{'description': 'labor', 'amount': '120.00', 'currency': 'EUR'}]
    },
    'local_historical_rates_other_scopes': [],
}
COMPLETE = ('A customer in Chile needs 12 filter cloths replaced on a Larox PF-DS '
            'tower press. What should I budget for the service visit?')


class Reply:
    def __init__(self, calls=None, final=''):
        self.output = calls or []
        self.output_text = final


class FakeClient:
    def __init__(self, *replies):
        self.responses = self
        self.replies = list(replies)
        self.options = []

    def create(self, **kwargs):
        self.options.append(kwargs['tool_choice'])
        return self.replies.pop(0)


class FakeTools:
    def dispatch(self, name, arguments):
        if name != 'compare_service_costs':
            raise ValueError('unexpected tool')
        return COST


def call():
    return SN(type='function_call', name='compare_service_costs', call_id='c1',
              arguments=json.dumps({'country': 'Chile', 'equipment': 'Larox PF-DS',
                                    'task': 'cloth replacement', 'quantity': 12,
                                    'site': None, 'parts_supplier': 'unknown'}))


def test_complete_cost_request_classifier_does_not_hardcode_city_or_device():
    assert _complete_cost_request(COMPLETE)
    assert _complete_cost_request('A customer in Sweden needs 8 filter cloths replaced on a belt filter; what is the cost?')
    assert not _complete_cost_request('Need cloth replacements. What is the budget?')


def test_missing_cost_tool_is_forced_once():
    client = FakeClient(Reply(final='I can find historical prices after you confirm your site.'),
                        Reply(calls=[call()]),
                        Reply(final='FSR-0001 has a historical sum of 120.00 EUR, not a Chile quote.'))
    agent = AgentController(FakeTools(), client, model='fake',
                            enforce_evidence_guards=True, enforce_complete_cost_routing=True)
    answer = agent.turn(COMPLETE)
    assert '120.00 EUR' in answer
    assert agent.last_trace == ['compare_service_costs']
    assert client.options[1] == {'type': 'function', 'name': 'compare_service_costs'}


def test_one_evidence_guard_repair_without_history_pollution():
    client = FakeClient(Reply(calls=[call()]), Reply(final='Confirmed Chile quote 9999 EUR'),
                        Reply(final='FSR-0001 has provisional 120.00 EUR, not an official Chile quote.'))
    agent = AgentController(FakeTools(), client, model='fake',
                            enforce_evidence_guards=True, max_guard_repairs=1)
    answer = agent.turn(COMPLETE)
    assert '120.00 EUR' in answer
    assert len(agent.history) == 2
    assert '9999 EUR' not in str(agent.history)


def test_failed_repair_never_publishes_or_stores_unverified_answer():
    client = FakeClient(Reply(calls=[call()]), Reply(final='Confirmed Chile quote 9999 EUR'),
                        Reply(final='Still a confirmed Chile quote 8888 EUR'))
    agent = AgentController(FakeTools(), client, model='fake',
                            enforce_evidence_guards=True, max_guard_repairs=1)
    with pytest.raises(AgentRuntimeError, match='Evidence guard rejected'):
        agent.turn(COMPLETE)
    assert agent.history == []


def test_negated_quote_is_not_automatically_misclassified():
    from metso_agent.validation.response_guard import validate_answer
    valid = validate_answer('FSR-0001 has a historical sum of 120.00 EUR. This is not an official Chile quote.',
                            [('compare_service_costs', COST)])
    assert valid.ok, valid.issues
    invalid = validate_answer('The official Chile quote is 120.00 EUR (FSR-0001).',
                              [('compare_service_costs', COST)])
    assert 'UNSUPPORTED_SITE_SPECIFIC_QUOTE' in invalid.issues


def test_negated_clause_cannot_hide_later_real_quote():
    from metso_agent.validation.response_guard import validate_answer
    result = validate_answer('This is not an official Chile quote, but the confirmed Chile quote is 120.00 EUR.',
                             [('compare_service_costs', COST)])
    assert 'UNSUPPORTED_SITE_SPECIFIC_QUOTE' in result.issues
