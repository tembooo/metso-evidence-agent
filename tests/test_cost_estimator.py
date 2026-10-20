"""Synthetic Stage05 tests: no employer report text or prices copied."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from metso_agent.estimation.cost_estimator import (
    EvidenceError,
    ServiceRequest,
    build_planning_comparison,
    dec,
    exact_line,
    extracted_cost_items,
    historical_local_rates,
    load_ledger,
    money,
    reconstructed_case,
    same_currency_sum,
    score_task,
    verify_original,
)


def make_case(tmp_path: Path, report_id="FSR-9999", country="Sweden", quantity=12,
              equipment="Demo PF-DS", work="Replaced 12 demo filter cloths"):
    lines = [
        "# Synthetic maintenance example",
        "### Materials and Parts Used",
        "| Item | Part Number | Quantity | Unit Cost (EUR) | Total Cost (EUR) |",
        "|---|---|---|---|---|",
        "| Synthetic cloth | X-000 | 12 | 10.00 | 120.00 |",
        "| Test clips | X-001 | 2 | 3.00 | 6.00 |",
        "| Test solvent | X-002 | 1 lot | 4.00 | 4.00 |",
        "### Cost Summary",
        "| Description | Quantity | Rate | Total (EUR) |",
        "|---|---|---|---|",
        "| Labour | 2 | 20.00 | 40.00 |",
        "| Travel | 1 | 15.00 | 15.00 |",
        "| Synthetic cloth | 12 | 10.00 | 120.00 |",
        "| Test clips | 2 | 3.00 | €",  # intentionally truncated
    ]
    path = tmp_path / f"{report_id}.txt"
    payload = "\n".join(lines) + "\n"
    path.write_text(payload, encoding="utf-8")
    items = []
    for desc, q, rate, total, lineno, category in [
        ("Labour", "2", "20.00", "40.00", 11, "labor"),
        ("Travel", "1", "15.00", "15.00", 12, "travel"),
        ("Synthetic cloth", str(quantity), "10.00", "120.00", 13, "parts"),
    ]:
        items.append({"description": desc, "quantity": q, "unit_rate": rate,
                      "amount_reported": total, "currency": "EUR", "category": category,
                      "source": {"location": f"line:{lineno}", "document_id": report_id}})
    record = {
        "report": {"report_id": report_id,
                   "source": {"document_id": report_id, "source_kind": "service_report"},
                   "country": country,
                   "equipment_model": equipment,
                   "visit_date": "2023-01-01",
                   "tasks": [work],
                   "cost_items": items,
                   "reported_total": None,
                   "total_currency": None},
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "material_row_candidates": [
            {"line": 5, "description": "Synthetic cloth", "cells": ["X-000", "12", "10.00", "120.00"]},
            {"line": 6, "description": "Test clips", "cells": ["X-001", "2", "3.00", "6.00"]},
            {"line": 7, "description": "Test solvent", "cells": ["X-002", "1 lot", "4.00", "4.00"]},
        ],
        "quality_flags": ["TRUNCATED_COST_TABLE", "TOTAL_NOT_REPORTED"],
    }
    return record, path


def test_decimal_amounts_are_exact():
    assert exact_line("3", "12.50", "37.50") == Decimal("37.50")


def test_invalid_line_arithmetic_rejected():
    with pytest.raises(EvidenceError, match="conflicts"):
        exact_line("3", "12.50", "99.00")


def test_unknown_is_not_zero():
    with pytest.raises(EvidenceError):
        dec(None)


def test_non_finite_numeric_rejected():
    with pytest.raises(EvidenceError):
        dec("NaN")


def test_mixed_currency_sum_rejected():
    with pytest.raises(EvidenceError, match="currencies"):
        same_currency_sum([{"currency": "EUR", "amount": "12"},
                           {"currency": "USD", "amount": "20"}])


def test_same_currency_sum():
    currency, value = same_currency_sum([{"currency": "EUR", "amount": "12.50"},
                                         {"currency": "EUR", "amount": "3.10"}])
    assert currency == "EUR" and money(value) == "15.60"


def test_request_rejects_zero_quantity():
    with pytest.raises(EvidenceError):
        ServiceRequest("Chile", "PF-DS", "cloths", 0)


def test_request_rejects_invalid_supplier():
    with pytest.raises(EvidenceError):
        ServiceRequest("Chile", "PF-DS", "cloths", 12, parts_supplier="maybe")


def test_loader_rejects_duplicates(tmp_path):
    record, _ = make_case(tmp_path)
    p = tmp_path / "ledger.json"
    p.write_text(json.dumps([record, record]))
    with pytest.raises(EvidenceError, match="Duplicate"):
        load_ledger(p)


def test_original_digest_detects_tamper(tmp_path):
    record, p = make_case(tmp_path)
    assert len(verify_original(record, tmp_path)) > 0
    p.write_text("changed source")
    with pytest.raises(EvidenceError, match="SHA-256"):
        verify_original(record, tmp_path)


def test_partial_materials_reconstructed_without_double_count(tmp_path):
    record, _ = make_case(tmp_path)
    result = reconstructed_case(record, tmp_path)
    assert result["status"] == "PROVISIONAL_COMPONENT_SUM_NOT_SOURCE_TOTAL"
    assert result["printed_total"] is None
    assert result["reconstructed"] == {"amount": "185.00", "currency": "EUR"}
    assert len(result["components"]) == 5
    assert len({c["source"] for c in result["components"]}) == 5


def test_missing_material_currency_header_not_supplemented(tmp_path):
    record, p = make_case(tmp_path)
    p.write_text(p.read_text().replace("Unit Cost (EUR)", "Unit Cost"), encoding="utf-8")
    record["source_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    result = reconstructed_case(record, tmp_path)
    assert result["reconstructed"] == {"amount": "175.00", "currency": "EUR"}
    assert len(result["components"]) == 3


def test_printed_total_kept_separate_from_reconstruction(tmp_path):
    record, _ = make_case(tmp_path)
    record["report"]["reported_total"] = "240.00"
    record["report"]["total_currency"] = "EUR"
    result = reconstructed_case(record, tmp_path)
    assert result["printed_total"] == "240.00"
    assert result["reconstructed"] is None


def test_exact_equipment_filter_excludes_pf_without_ds(tmp_path):
    record, _ = make_case(tmp_path)
    req = ServiceRequest("Chile", "Larox PF-DS", "cloth replacement", 12)
    assert score_task(record, req)[0] > 0
    record["report"]["equipment_model"] = "Larox PF Filter"
    assert score_task(record, req)[0] == 0
    req_pf = ServiceRequest("Chile", "Larox PF", "cloth replacement", 12)
    record["report"]["equipment_model"] = "Larox PF-DS filter"
    assert score_task(record, req_pf)[0] == 0


def test_local_rates_keep_original_currency_and_provenance(tmp_path):
    record, _ = make_case(tmp_path, country="Chile")
    rates = historical_local_rates([record], "Chile")
    assert rates[0]["rates"][0]["currency"] == "EUR"
    assert rates[0]["rates"][0]["source"].startswith("FSR-9999:line:")


def test_no_site_specific_price_is_invented(tmp_path):
    record, _ = make_case(tmp_path)
    request = ServiceRequest("Chile", "Larox PF-DS", "filter cloth replacement", 12)
    comparison = build_planning_comparison([record], request, tmp_path)
    assert comparison["site_specific_budget"] is None
    assert comparison["best_historical_analog"]["reconstructed"]["amount"] == "185.00"
    assert len(comparison["questions"]) == 2


def test_extracted_line_has_source_location(tmp_path):
    record, _ = make_case(tmp_path)
    lines = extracted_cost_items(record)
    assert all("line:" in part["source"] for part in lines)


def test_unpriced_report_keeps_unknown(tmp_path):
    record, _ = make_case(tmp_path)
    record["report"]["cost_items"] = []
    record["material_row_candidates"] = []
    res = reconstructed_case(record, tmp_path)
    assert res["reconstructed"] is None
    assert res["status"] == "INSUFFICIENT"
