"""Synthetic tests for Stage09 reliability and disclosure. No external API calls."""
from __future__ import annotations

from types import SimpleNamespace as SN
import json
import pytest

from metso_agent.agent.controller import AgentController, AgentRuntimeError, _stage09_safe_fallback
from metso_agent.validation.response_guard import validate_answer

EVIDENCE = {
    'status': 'INSUFFICIENT_EVIDENCE_FOR_SITE_SPECIFIC_QUOTE',
    'site_specific_budget': None,
    'task_analogs': [{'report_id':'FSR-0001'}],
    'best_historical_analog': {
        'report_id':'FSR-0001',
        'reconstructed': {'amount':'120.00', 'currency':'EUR'},
        'components':[{'description':'Labour','amount':'120.00','currency':'EUR'}],
    },
    'local_historical_rates_other_scopes':[],
}

@pytest.mark.parametrize('text', [
    'I cannot guarantee 50% cost savings.',
    'We do not promise 40% improvement.',
    'This brochure does not guarantee 25% savings.',
    'No guaranteed 50% improvement can be concluded.',
])
def test_negated_performance_guarantee_permitted(text):
    result = validate_answer(text, [])
    assert result.ok, result.issues

@pytest.mark.parametrize('text', [
    'I guarantee 50% savings.',
    'I guarantee 50.5% savings.',
    'The official guarantee is 40% improvement.',
    'I cannot guarantee 50% savings, but I guarantee 40% savings.',
    'No guaranteed 50% improvement is established; however I guarantee 30% savings.',
])
def test_unsupported_positive_guarantee_blocked(text):
    result = validate_answer(text, [])
    assert 'UNSUPPORTED_PERFORMANCE_GUARANTEE' in result.issues


def test_cost_fallback_uses_current_tool_evidence_only():
    out = _stage09_safe_fallback('A filter needs service in Chile',
        ('UNSUPPORTED_SITE_SPECIFIC_QUOTE',), [('compare_service_costs', EVIDENCE)])
    assert 'FSR-0001' in out and '120.00 EUR' in out
    assert validate_answer(out, [('compare_service_costs', EVIDENCE)]).ok
    assert 'confirmed price' not in out


def test_no_quote_without_current_turn_cost_evidence():
    assert _stage09_safe_fallback('Quote for Chile', ('UNSUPPORTED_SITE_SPECIFIC_QUOTE',), []) is None


def test_mixed_currency_fallback_never_repeats_customer_amounts():
    question = 'Can I add 300 EUR to 500 USD and call it 800 EUR?'
    response = _stage09_safe_fallback(question, ('UNSUPPORTED_MONETARY_AMOUNT',), [])
    assert response and '300' not in response and '500' not in response and '800' not in response
    assert validate_answer(response, []).ok


def test_conservative_guarantee_fallback():
    response = _stage09_safe_fallback('Can you guarantee 50% savings?',
        ('UNSUPPORTED_PERFORMANCE_GUARANTEE',), [])
    assert response and validate_answer(response, []).ok


class FakeClient:
    def __init__(self, *messages):
        self.responses = self
        self.messages = list(messages)
    def create(self, **kwargs):
        return self.messages.pop(0)


def reply(text='', calls=None):
    return SN(output=calls or [], output_text=text)


def call():
    return SN(type='function_call', name='compare_service_costs', call_id='123',
        arguments=json.dumps({'country':'Chile','equipment':'PF-DS',
            'task':'cloth replacement', 'quantity':12,
            'site':None,'parts_supplier':'unknown'}))

class FakeTools:
    def dispatch(self, name, args):
        assert name == 'compare_service_costs'
        return EVIDENCE


def test_controller_emits_validated_fallback_after_failed_cost_repair():
    agent = AgentController(FakeTools(), FakeClient(
        reply(calls=[call()]), reply('The final Chile quote is 10000 EUR.'),
        reply('The confirmed Chile budget is 20000 EUR.')),
        model='fake', enforce_evidence_guards=True, max_guard_repairs=1,
        use_safe_evidence_fallback=True)
    result = agent.turn('A customer in Chile needs 12 filter cloths replaced on a Larox PF-DS tower press. What should I budget?')
    assert '120.00 EUR' in result
    assert '10000' not in result and '20000' not in result
    assert agent.history[-1]['content'] == result
    assert agent.last_trace == ['compare_service_costs']


def test_controller_keeps_old_failure_behavior_when_fallback_disabled():
    agent = AgentController(FakeTools(), FakeClient(
        reply(calls=[call()]), reply('The final Chile quote is 10000 EUR.'),
        reply('The confirmed Chile budget is 20000 EUR.')),
        model='fake', enforce_evidence_guards=True, max_guard_repairs=1)
    with pytest.raises(AgentRuntimeError, match='Evidence guard rejected'):
        agent.turn('A customer in Chile needs 12 filter cloths replaced on a Larox PF-DS tower press. What should I budget?')
    assert not agent.history


def test_private_session_log_only_allows_local_cache(tmp_path):
    from metso_agent.agent.chat import _stage09_session_path
    approved = tmp_path / 'local_cache' / 'session.txt'
    assert _stage09_session_path(tmp_path, str(approved)) == approved
    with pytest.raises(ValueError, match='local_cache'):
        _stage09_session_path(tmp_path, str(tmp_path / 'README.md'))


def test_private_session_log_rejects_overwrite(tmp_path):
    from metso_agent.agent.chat import _stage09_session_path
    dest = tmp_path / 'local_cache' / 'old.txt'
    dest.parent.mkdir()
    dest.write_text('PRIVATE EXISTING CONTENT')
    with pytest.raises(ValueError, match='already exists'):
        _stage09_session_path(tmp_path, str(dest))
    assert dest.read_text() == 'PRIVATE EXISTING CONTENT'
