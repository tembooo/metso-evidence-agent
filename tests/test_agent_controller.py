"""Synthetic offline tests: no original Metso material or API key is needed."""
import json
from types import SimpleNamespace as SN

import pytest

from metso_agent.agent.controller import AgentController, AgentRuntimeError
from metso_agent.agent.tools import LocalTools, TOOL_SCHEMAS


class FakeResponse:
    def __init__(self, calls=None, final=""):
        self.output = calls or []
        self.output_text = final


def call(name, args, call_id="call_001"):
    return SN(type="function_call", name=name, arguments=json.dumps(args), call_id=call_id)


class FakeClient:
    def __init__(self, *responses):
        self.queue = list(responses)
        self.inputs = []
        self.responses = self

    def create(self, **kwargs):
        self.inputs.append(kwargs)
        if not self.queue:
            raise RuntimeError("Fake exhausted")
        next_response = self.queue.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return next_response


class FakeTools:
    def __init__(self):
        self.calls = []

    def dispatch(self, name, args):
        self.calls.append((name, args))
        if name == "search_product_brochures":
            return {"status": "EVIDENCE_FOUND", "items": [
                {"source_id": "synthetic-filter", "page": 2, "excerpt": "Synthetic control description"}
            ]}
        if name == "compare_service_costs":
            return {"status": "INSUFFICIENT_EVIDENCE_FOR_SITE_SPECIFIC_QUOTE",
                    "site_specific_budget": None, "questions": ["What is the site?"]}
        raise ValueError("Unknown tool")


REQ = {"country": "Chile", "equipment": "Larox PF-DS", "task": "filter cloth replacement",
       "quantity": 12, "site": None, "parts_supplier": "unknown"}


def test_product_tool_routed_from_natural_language():
    tools = FakeTools()
    fake = FakeClient(FakeResponse([call("search_product_brochures", {"query": "changing filtration"})]),
                      FakeResponse(final="Synthetic brochure p.2 suggests checking settings."))
    agent = AgentController(tools, fake, "test-model")
    text = agent.turn("Feed conditions vary; what product helps?")
    assert "Synthetic" in text
    assert [c[0] for c in tools.calls] == ["search_product_brochures"]
    assert fake.inputs[0]["store"] is False


def test_cost_tool_routed_and_budget_remains_null():
    tools = FakeTools()
    fake = FakeClient(FakeResponse([call("compare_service_costs", REQ)]),
                      FakeResponse(final="No supported Chile quote; what is the site?"))
    agent = AgentController(tools, fake, "test-model")
    agent.turn("Chile, 12 cloths on PF-DS: cost?")
    assert tools.calls[0][1]["quantity"] == 12
    supplied = fake.inputs[1]["input"][-1]
    assert json.loads(supplied["output"])["site_specific_budget"] is None


def test_combined_question_can_call_both_tools():
    tools = FakeTools()
    fake = FakeClient(
        FakeResponse([call("search_product_brochures", {"query": "filter optimization"}, "a")]),
        FakeResponse([call("compare_service_costs", REQ, "b")]),
        FakeResponse(final="Product evidence and historical context are separate."))
    agent = AgentController(tools, fake, "test-model")
    agent.turn("What helps changing feed, and how much for 12 cloths on PF-DS in Chile?")
    assert agent.last_trace == ["search_product_brochures", "compare_service_costs"]


def test_followup_carries_chat_history_not_private_tool_results():
    tools = FakeTools()
    fake = FakeClient(FakeResponse(final="Which country?"), FakeResponse(final="Thanks: Chile."))
    agent = AgentController(tools, fake, "test-model")
    agent.turn("How much to visit?")
    agent.turn("Chile")
    inputs = fake.inputs[1]["input"]
    assert inputs[-1]["content"] == "Chile"
    assert inputs[-2]["content"] == "Which country?"


def test_bounded_tool_calls_fail_closed():
    tools = FakeTools()
    fake = FakeClient(FakeResponse([call("search_product_brochures", {"query": "filter"})]))
    agent = AgentController(tools, fake, "test-model", max_calls=0)
    with pytest.raises(AgentRuntimeError, match="limit"):
        agent.turn("Question")
    assert not tools.calls


def test_api_failure_reports_only_class_name():
    tools = FakeTools()
    fake = FakeClient(RuntimeError("SECRET FROM INTERNAL REQUEST BODY"))
    agent = AgentController(tools, fake, "test-model")
    with pytest.raises(AgentRuntimeError) as exc:
        agent.turn("Hello")
    assert "SECRET" not in str(exc.value)


def test_invalid_argument_or_unknown_tool_is_rejected_without_crash():
    tools = FakeTools()
    fake = FakeClient(FakeResponse([call("drop_database", {"x": 1})]),
                      FakeResponse(final="Tool not available."))
    agent = AgentController(tools, fake, "test-model")
    agent.turn("Do something disallowed")
    assert tools.calls == [("drop_database", {"x": 1})]
    assert json.loads(fake.inputs[-1]["input"][-1]["output"])["status"] == "TOOL_ERROR"


def test_product_arguments_reject_extra_properties_without_reading_sources(tmp_path):
    tools = LocalTools(tmp_path)
    with pytest.raises(ValueError, match="arguments"):
        tools.dispatch("search_product_brochures", {"query": "x", "raw": "leak"})


def test_service_request_rejects_unknown_quantity_without_reading_ledger(tmp_path):
    tools = LocalTools(tmp_path)
    with pytest.raises(ValueError, match="integer"):
        tools.dispatch("compare_service_costs", {**REQ, "quantity": None})


def test_api_tool_schemas_are_strict():
    for tool in TOOL_SCHEMAS:
        assert tool["strict"] is True
        params = tool["parameters"]
        assert params["additionalProperties"] is False
        assert set(params["required"]) == set(params["properties"])


def test_blank_message_rejected():
    agent = AgentController(FakeTools(), FakeClient(), "test-model")
    with pytest.raises(ValueError, match="empty"):
        agent.turn("   ")


def test_failed_api_turn_does_not_add_session_history():
    agent = AgentController(FakeTools(), FakeClient(RuntimeError("fail")), "test-model")
    with pytest.raises(AgentRuntimeError):
        agent.turn("One")
    assert not agent.history
