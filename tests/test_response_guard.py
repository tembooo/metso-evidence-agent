"""Synthetic fixture tests; no private Metso content and no API calls."""
from types import SimpleNamespace as SN
import json
import pytest

from metso_agent.validation.response_guard import validate_answer
from metso_agent.agent.controller import AgentController, AgentRuntimeError


PRODUCT = {"status": "EVIDENCE_FOUND", "items": [
    {"source_id": "synthetic-filter", "page": 2,
     "excerpt": "Synthetic brochure: adjusts the filter cycle under variable feed."}
]}
COST = {"status": "INSUFFICIENT_EVIDENCE_FOR_SITE_SPECIFIC_QUOTE",
        "site_specific_budget": None,
        "task_analogs": [{"report_id": "FSR-0001", "source_printed_total": "1250.00", "source_printed_currency": "EUR"}],
        "best_historical_analog": {"report_id": "FSR-0001", "reconstructed":
            {"amount": "120.00", "currency": "EUR"},
            "components": [
                {"description": "technician labor", "amount": "100.00", "currency": "EUR", "unit_rate": "50.00"},
                {"description": "filter cloths", "amount": "20.00", "currency": "EUR", "unit_rate": "10.00"}]},
        "local_historical_rates_other_scopes": [{"report_id": "FSR-0002", "observations": [
            {"hourly_rate": "60.00", "currency": "USD"}]}]}


def issues(text, tools):
    return validate_answer(text, tools).issues


def test_valid_brochure_citation():
    assert not issues("See synthetic-filter, p.2 for filter cycles.", [("search_product_brochures", PRODUCT)])


def test_made_up_brochure_page_fails():
    assert "UNKNOWN_BROCHURE_PAGE" in issues("See synthetic-filter, p.99", [("search_product_brochures", PRODUCT)])


def test_made_up_brochure_fails():
    assert "UNKNOWN_BROCHURE_PAGE" in issues("See unknown-brochure, p.2", [("search_product_brochures", PRODUCT)])


def test_grounded_report_citation():
    assert not issues("See FSR-0001; 120.00 EUR is provisional, not a Chile quote.", [("compare_service_costs", COST)])


def test_nonexistent_report_citation_fails():
    assert "UNKNOWN_SERVICE_CITATION" in issues("See FSR-9999", [("compare_service_costs", COST)])


def test_unsupported_price_fails():
    assert "UNSUPPORTED_MONETARY_AMOUNT" in issues("It is 9,999.00 EUR", [("compare_service_costs", COST)])


def test_supported_components_and_derived_minus_cloth():
    assert not issues("Historical 120.00 EUR; excluding customer cloths 100.00 EUR.", [("compare_service_costs", COST)])


def test_mixed_currency_arithmetic_fails():
    assert "MIXED_CURRENCY_ADDITION" in issues("100.00 EUR + 60.00 USD = 160", [("compare_service_costs", COST)])


def test_confirmed_site_quote_fails():
    assert "UNSUPPORTED_SITE_SPECIFIC_QUOTE" in issues("Confirmed Chile quote: 120.00 EUR", [("compare_service_costs", COST)])


def test_guaranteed_savings_without_evidence_fails():
    assert "UNSUPPORTED_PERFORMANCE_GUARANTEE" in issues("Guaranteed 50% savings", [("search_product_brochures", PRODUCT)])


def test_euro_symbol_amount_is_grounded():
    assert not issues("Historical €120.00, not a Chile quote.", [("compare_service_costs", COST)])


def test_invented_euro_symbol_amount_rejected():
    assert "UNSUPPORTED_MONETARY_AMOUNT" in issues("Historical €7,777.00", [("compare_service_costs", COST)])


def test_empty_output_rejected():
    assert issues("  ", []) == ("EMPTY_ANSWER",)


def test_missing_evidence_rejects_money():
    assert "UNSUPPORTED_MONETARY_AMOUNT" in issues("It is 100 EUR", [])


class Reply:
    def __init__(self, output=None, final=""):
        self.output = output or []
        self.output_text = final


class FakeClient:
    def __init__(self, *replies):
        self.responses = self
        self.replies = list(replies)

    def create(self, **kwargs):
        return self.replies.pop(0)


class FakeTools:
    def dispatch(self, name, args):
        return COST


def tool_call(name, args):
    return SN(type="function_call", name=name, call_id="abc", arguments=json.dumps(args))


def test_controller_enforcement_prevents_history_pollution():
    from metso_agent.agent.tools import TOOL_SCHEMAS
    args = {"country":"Chile", "equipment":"Larox PF-DS", "task":"cloth replacement",
            "quantity":12,"site":None,"parts_supplier":"unknown"}
    client = FakeClient(Reply([tool_call("compare_service_costs", args)]),
                        Reply(final="Confirmed Chile quote 9999 EUR FSR-9999"))
    agent = AgentController(FakeTools(), client, model="fake", enforce_evidence_guards=True)
    with pytest.raises(AgentRuntimeError, match="Evidence guard rejected"):
        agent.turn("12 cloths in Chile")
    assert agent.history == []


def test_controller_enforcement_permits_supported_answer():
    args = {"country":"Chile", "equipment":"Larox PF-DS", "task":"cloth replacement",
            "quantity":12,"site":None,"parts_supplier":"unknown"}
    client = FakeClient(Reply([tool_call("compare_service_costs", args)]),
                        Reply(final="FSR-0001 has a provisional sum of 120.00 EUR. Not a Chile quote."))
    agent = AgentController(FakeTools(), client, model="fake", enforce_evidence_guards=True)
    answer = agent.turn("12 cloths in Chile")
    assert "120.00 EUR" in answer
