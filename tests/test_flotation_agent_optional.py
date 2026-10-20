"""Stage08 optional agent integration; these tests require Stage08 patch first."""
import json
from metso_agent.agent.tools import TOOL_SCHEMAS, LocalTools


def test_fl_tool_schema_is_registered_and_strict():
    candidates = [x for x in TOOL_SCHEMAS if x['name'] == 'analyze_flotation']
    assert len(candidates) == 1
    schema = candidates[0]
    assert schema['strict'] is True
    assert set(schema['parameters']['required']) == {'silica_pct', 'iron_pct'}
    assert schema['parameters']['additionalProperties'] is False


def test_agent_adapter_dispatches_to_real_local_csv(tmp_path):
    raw = tmp_path / 'raw' / 'data'
    raw.mkdir(parents=True)
    csv = raw / 'flotation_process_data_hourly.csv'
    csv.write_text('date,% Silica Concentrate,% Iron Concentrate\n'
                   '2026-01-01 00:00:00,3.1,64.5\n'
                   '2026-01-01 01:00:00,2.0,65.0\n', encoding='utf-8')
    result = LocalTools(tmp_path).dispatch('analyze_flotation', {'silica_pct': 3.1, 'iron_pct': 64.5})
    assert result['counts']['both_conditions'] == 1
    assert result['source']['kind'] == 'flotation_csv'


def test_agent_adapter_rejects_extra_field(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        LocalTools(tmp_path).dispatch('analyze_flotation', {'silica_pct': 3.1, 'iron_pct': 64.5, 'secret': 1})


def test_mock_llm_calls_optional_tool_and_agent_responds(tmp_path):
    """Fake API: test routing contract, not real-world LLM route accuracy."""
    from types import SimpleNamespace as SN
    from metso_agent.agent.controller import AgentController
    raw = tmp_path / 'raw' / 'data'
    raw.mkdir(parents=True)
    (raw / 'flotation_process_data_hourly.csv').write_text(
        'date,% Silica Concentrate,% Iron Concentrate\n'
        '2026-01-01 00:00:00,3.1,64.5\n'
        '2026-01-01 01:00:00,2.0,65.0\n', encoding='utf-8'
    )

    class FakeClient:
        def __init__(self):
            self.responses = self
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                call = SN(type='function_call', name='analyze_flotation',
                          arguments=json.dumps({'silica_pct': 3.1, 'iron_pct': 64.5}),
                          call_id='call_test')
                return SN(output=[call], output_text='')
            return SN(output=[], output_text='Historical sample: 1/2 rows met both conditions; '
                      'this does not establish contractual acceptance.')

    client = FakeClient()
    agent = AgentController(LocalTools(tmp_path), client, 'fake', enforce_evidence_guards=True)
    text = agent.turn('3.1% silica and 64.5% iron: is that normal?')
    assert '1/2' in text
    assert agent.last_trace == ['analyze_flotation']
    assert client.calls == 2
