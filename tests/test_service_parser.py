from pathlib import Path

import pytest

from metso_agent.ingestion.service_parser import build_ledger, parse_report


def make_fsr(tmp_path: Path, name: str, text: str) -> dict:
    file = tmp_path / name
    file.write_text(text, encoding="utf-8")
    return parse_report(file)


def test_itemized_costs_have_lines(tmp_path):
    record = make_fsr(tmp_path, "FSR-9999.txt", """Field Service Report FSR-9999
Site Location: Demo Mine, Finland
Visit Date: 2024-03-12
Equipment: Synthetic Pump
Total On-Site Hours: 2.0
Travel Hours: 3.5
### Cost Summary
| Description | Qty | Rate (EUR) | Total (EUR) |
|---|---|---|---|
| Travel | 3.5 hrs | 50.00 | 175.00 |
| Labour | 2 hrs | 90.00 | 180.00 |
| **Total** | | | **355.00** |
---
""")
    r = record["report"]
    assert r["reported_total"] == "355.00"
    assert r["total_currency"] == "EUR"
    assert len(r["cost_items"]) == 2
    assert r["cost_items"][0]["source"]["location"].startswith("line:")
    assert r["travel_hours"] == "3.5"


def test_truncated_does_not_invent_total(tmp_path):
    record = make_fsr(tmp_path, "FSR-9999.txt", """Report Reference: FSR-9999
Site: Aitik, Sweden
Visit Date: 2023-05-12
Equipment: Larox PF-DS
Total On-Site Hours: 8.4
Travel Hours: 4.9
### Cost Summary
| Description | Qty | Rate | Total (EUR) |
|---|---|---|---|
| Travel | 4.9 hrs | €62.00/hr | €303.80 |
| Labour | 8.4 hrs | €78.00/hr | €655.20 |
| Fastening Clips | 24 | €2.60/ea | €
""")
    r = record["report"]
    assert r["reported_total"] is None
    assert "TRUNCATED_COST_TABLE" in record["quality_flags"]
    assert "PARTIAL_ITEMIZED_COST_ONLY" in record["quality_flags"]
    assert len(r["cost_items"]) == 2
    assert record["cost_row_candidates"][-1]["reported_amount"] is None


def test_invoice_to_follow_not_zero(tmp_path):
    record = make_fsr(tmp_path, "FSR-9999.txt", """FSR-9999
Site: Example, Australia
On-site hours: 4.2h
Travel: 6h
Invoice to follow.
""")
    assert record["report"]["reported_total"] is None
    assert "PRICE_NOT_AVAILABLE" in record["quality_flags"]


def test_unknown_dollar_does_not_infer_currency(tmp_path):
    record = make_fsr(tmp_path, "FSR-9999.txt", """FSR-9999
Site: Example, Canada
Total Cost: $2,540
""")
    assert record["report"]["reported_total"] == "2540"
    assert record["report"]["total_currency"] is None
    assert "TOTAL_CURRENCY_UNKNOWN" in record["quality_flags"]


def test_country_not_inferred_from_ambiguous_date(tmp_path):
    record = make_fsr(tmp_path, "FSR-9999.txt", """FSR-9999
Site: Factory (AU)
Date: 08/01/24
""")
    assert record["report"]["visit_date"] is None
    assert record["report"]["country"] is None
    assert "DATE_REQUIRES_REVIEW" in record["quality_flags"]


def test_partial_work_and_travel_each_way_flag(tmp_path):
    record = make_fsr(tmp_path, "FSR-9999.txt", """FSR-9999
Site: Example, Sweden
Only partial cloth change, frame stuck.
Traveled 4.5h each way. Invoice to follow.
""")
    assert "PARTIAL_OR_UNFINISHED_WORK" in record["quality_flags"]
    assert "TRAVEL_DIRECTION_REQUIRES_REVIEW" in record["quality_flags"]
    assert record["report"]["travel_hours"] is None


def test_report_id_mismatch_flagged(tmp_path):
    record = make_fsr(tmp_path, "FSR-9999.txt", """Report Reference: FSR-8888
Site: Example, Finland
""")
    assert "REPORT_ID_MISMATCH" in record["quality_flags"]


def test_wrong_report_count_rejected(tmp_path):
    (tmp_path / "FSR-0001.txt").write_text("FSR-0001", encoding="utf-8")
    with pytest.raises(ValueError, match="Expected 50"):
        build_ledger(tmp_path)


def test_no_cross_currency_aggregation(tmp_path):
    record = make_fsr(tmp_path, "FSR-9999.txt", """FSR-9999
Cost Summary:
| Description | Qty | Rate (EUR) | Total (EUR) |
|---|---|---|---|
| Parts | 1 | 2 | 2 |
Total Cost (USD): $300
""")
    assert "MULTIPLE_CURRENCIES_IN_REPORT" in record["quality_flags"]


def test_timeline_is_separate_from_billable_hours(tmp_path):
    record = make_fsr(tmp_path, "FSR-9999.txt", """FSR-9999
| Step | Start Time | End Time | Hrs |
| Safety | 07:30 | 08:00 | 0.5 |
| Repair | 08:00 | 16:15 | 8.25 |
| Total On-Site Hours | | | 8.4 |
""")
    assert record["report"]["labor_hours"] == "8.4"
    assert record["observations"]["activity_window_elapsed_hours"]["value"] == "8.75"
    assert "ELAPSED_VS_REPORTED_HOURS" in record["quality_flags"]


def test_completed_work_and_materials_preserved(tmp_path):
    record = make_fsr(tmp_path, "FSR-9999.txt", """FSR-9999
Equipment: Synthetic Press
### Materials and Parts Used
| Item | Part Number | Quantity | Unit Cost (EUR) | Total (EUR) |
|---|---|---|---|---|
| Filter cloth | EX-100 | 12 | 10.00 | 120.00 |
---
### Work Completed
- Replaced 12 synthetic filter cloths.
- Verified operation.
---
""")
    assert len(record["report"]["tasks"]) == 2
    assert len(record["task_evidence"]) == 2
    assert len(record["material_row_candidates"]) == 1
    assert record["report"]["reported_total"] is None
    assert record["report"]["cost_items"] == []


def test_bundle_is_not_itemized(tmp_path):
    record = make_fsr(tmp_path, "FSR-9999.txt", """FSR-9999
Site: Demo Mine, Sweden
Equipment: Synthetic Motor
Total Cost: SEK 19,850
""")
    assert record["report"]["reported_total"] == "19850"
    assert record["report"]["total_currency"] == "SEK"
    assert record["report"]["cost_items"] == []
    assert "BUNDLED_TOTAL_NOT_ITEMIZED" in record["quality_flags"]
