"""Stage 05: local, deterministic and currency-safe service cost evidence.

This module NEVER produces a binding service quote. Read Stage04's private
service_ledger.json. Never paste employer source data or private ledger into Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


class EvidenceError(ValueError):
    """A source is missing, stale, inconsistent or insufficient for arithmetic."""


MONEY_PLACES = Decimal("0.01")
NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


def dec(value: object) -> Decimal:
    """Parse a recorded number strictly; missing values never become zero."""
    if value is None or isinstance(value, bool):
        raise EvidenceError("Missing/invalid numeric value")
    try:
        result = Decimal(str(value).replace(",", "").strip())
    except InvalidOperation as exc:
        raise EvidenceError(f"Invalid numeric value: {value!r}") from exc
    if not result.is_finite():
        raise EvidenceError("Non-finite numeric evidence")
    return result


def money(amount: Decimal) -> str:
    return str(amount.quantize(MONEY_PLACES))


def exact_line(quantity: object, unit_rate: object, amount: object) -> Decimal:
    """Demand arithmetic consistency between recorded quantity/rate/extension."""
    q, rate, total = dec(quantity), dec(unit_rate), dec(amount)
    if q <= 0 or rate < 0 or total < 0:
        raise EvidenceError("Negative or zero quantity, or negative monetary amount")
    if (q * rate).quantize(MONEY_PLACES) != total.quantize(MONEY_PLACES):
        raise EvidenceError("Cost line arithmetic conflicts with source amount")
    return total


def same_currency_sum(components: list[dict]) -> tuple[str, Decimal]:
    if not components:
        raise EvidenceError("No supported components available")
    currencies = {part.get("currency") for part in components}
    if None in currencies or len(currencies) != 1:
        raise EvidenceError("Mixed or unknown currencies cannot be summed")
    currency = next(iter(currencies))
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise EvidenceError("Invalid currency code")
    return currency, sum((dec(part["amount"]) for part in components), Decimal("0"))


@dataclass(frozen=True)
class ServiceRequest:
    country: str
    equipment: str
    task: str
    quantity: int
    site: str | None = None
    parts_supplier: str = "unknown"

    def __post_init__(self):
        if not self.country.strip() or not self.equipment.strip() or not self.task.strip():
            raise EvidenceError("Country, equipment and task are required")
        if self.quantity <= 0:
            raise EvidenceError("Quantity must be positive")
        if self.parts_supplier not in {"unknown", "customer", "supplier"}:
            raise EvidenceError("parts_supplier must be unknown/customer/supplier")


def load_ledger(path: Path) -> list[dict]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise EvidenceError("Stage04 ledger must be an array")
    ids = []
    for entry in raw:
        if not isinstance(entry, dict) or not isinstance(entry.get("report"), dict):
            raise EvidenceError("Ledger record has no nested report")
        r = entry["report"]
        report_id = r.get("report_id")
        if not isinstance(report_id, str) or not re.fullmatch(r"FSR-\d{4}", report_id):
            raise EvidenceError("Malformed report ID")
        if r.get("source", {}).get("document_id") != report_id:
            raise EvidenceError("Source document ID mismatch")
        ids.append(report_id)
    if len(ids) != len(set(ids)):
        raise EvidenceError("Duplicate report ID in ledger")
    return raw


def verify_original(entry: dict, raw_dir: Path) -> list[str]:
    """Prevent use of cached numeric data after the original report changed."""
    report_id = entry["report"]["report_id"]
    source = Path(raw_dir) / f"{report_id}.txt"
    if not source.is_file():
        raise EvidenceError(f"Original source missing for {report_id}")
    contents = source.read_bytes()
    recorded_hash = entry.get("source_sha256")
    if not recorded_hash or hashlib.sha256(contents).hexdigest() != recorded_hash:
        raise EvidenceError(f"Source SHA-256 does not match ledger for {report_id}")
    return contents.decode("utf-8-sig").splitlines()


def extracted_cost_items(entry: dict) -> list[dict]:
    result: list[dict] = []
    r = entry["report"]
    for item in r.get("cost_items", []):
        if not item.get("currency") or item.get("amount_reported") is None:
            continue
        # Preserve reported item amount; do not invent missing rate or quantity.
        if item.get("quantity") is not None and item.get("unit_rate") is not None:
            exact_line(item["quantity"], item["unit_rate"], item["amount_reported"])
        loc = item.get("source", {}).get("location")
        if not loc or not loc.startswith("line:"):
            raise EvidenceError(f"Untraceable cost line in {r['report_id']}")
        result.append({
            "description": item["description"],
            "quantity": item.get("quantity"),
            "unit_rate": item.get("unit_rate"),
            "amount": money(dec(item["amount_reported"])),
            "currency": item["currency"],
            "source": f"{r['report_id']}:{loc}",
            "basis": "reported_cost_summary_line",
        })
    return result


def verified_material_supplements(entry: dict, original_lines: list[str], base: list[dict]) -> list[dict]:
    """Use clearly priced material rows only if original line/header are verified.

    A supplement is still PROVISIONAL: a truncated final cost table is not a
    confirmed invoice. The exact same quantity/rate/extension may not be counted
    once in Materials and again in Cost Summary.
    """
    report_id = entry["report"]["report_id"]
    candidates = entry.get("material_row_candidates", [])
    # Check source contains an explicit, currency-labeled materials cost table.
    original = "\n".join(original_lines)
    if not (re.search(r"Materials\s+and\s+Parts\s+Used", original, re.I)
            and re.search(r"Unit\s+Cost\s*\(EUR\)", original, re.I)
            and re.search(r"Total\s+Cost\s*\(EUR\)", original, re.I)):
        return []
    if {c["currency"] for c in base} != {"EUR"}:
        return []
    seen = {(dec(c["quantity"]) if c["quantity"] is not None else None,
             dec(c["unit_rate"]) if c["unit_rate"] is not None else None,
             dec(c["amount"])) for c in base}
    additions = []
    for row in candidates:
        line_no = row.get("line")
        if not isinstance(line_no, int) or not 1 <= line_no <= len(original_lines):
            raise EvidenceError("Invalid source line for material candidate")
        original_line = original_lines[line_no - 1]
        if not original_line.lstrip().startswith("|") or row["description"] not in original_line:
            raise EvidenceError("Material candidate does not match original source line")
        cells = row.get("cells") or []
        if len(cells) < 4:
            continue
        # Candidate cells are: part number, quantity, unit cost, extended cost.
        matches = [NUMBER.search(v) for v in cells[-3:]]
        if any(match is None for match in matches):
            continue
        q, rate, amount = [dec(match.group(0)) for match in matches]
        exact_line(q, rate, amount)
        signature = (q, rate, amount)
        if signature in seen:
            continue
        seen.add(signature)
        additions.append({
            "description": row["description"],
            "quantity": str(q), "unit_rate": str(rate),
            "amount": money(amount), "currency": "EUR",
            "source": f"{report_id}:line:{line_no}",
            "basis": "priced_material_table_not_in_truncated_cost_summary",
        })
    return additions


def reconstructed_case(entry: dict, raw_dir: Path) -> dict:
    r = entry["report"]
    lines = verify_original(entry, raw_dir)
    components = extracted_cost_items(entry)
    flags = set(entry.get("quality_flags", []))
    if r.get("reported_total") is not None:
        # Printed total always remains distinct; it cannot be silently replaced.
        reported_currency = r.get("total_currency")
        return {
            "report_id": r["report_id"], "printed_total": r["reported_total"],
            "printed_currency": reported_currency,
            "reconstructed": None, "components": components,
            "status": ("PRINTED_TOTAL_AVAILABLE" if reported_currency
                       else "PRINTED_TOTAL_CURRENCY_UNKNOWN"),
        }
    if "TRUNCATED_COST_TABLE" in flags:
        components.extend(verified_material_supplements(entry, lines, components))
    if not components:
        return {"report_id": r["report_id"], "printed_total": None,
                "reconstructed": None, "components": [], "status": "INSUFFICIENT"}
    currency, value = same_currency_sum(components)
    return {
        "report_id": r["report_id"], "printed_total": None,
        "reconstructed": {"amount": money(value), "currency": currency},
        "components": components,
        "status": "PROVISIONAL_COMPONENT_SUM_NOT_SOURCE_TOTAL",
        "warnings": sorted(flags),
    }


def score_task(entry: dict, req: ServiceRequest) -> tuple[int, list[str]]:
    r = entry["report"]
    equipment = r.get("equipment_model") or ""
    # Strict PF-DS matching: do not collapse PF and PF-DS into the same model.
    pfds_requested = bool(re.search(r"\bPF[- ]?DS\b", req.equipment, re.I))
    pfds_report = bool(re.search(r"\bPF[- ]?DS\b", equipment, re.I))
    if pfds_requested != pfds_report:
        # No implicit equivalence between the PF and PF-DS variants.
        return 0, []
    if not pfds_requested and req.equipment.casefold() not in equipment.casefold():
        return 0, []
    score, reasons = 10, ["equipment_model_matches"]
    tasks = " ".join(r.get("tasks") or [])
    if re.search(r"\bcloths?\b", tasks, re.I) and re.search(r"\breplac\w*\b|\bchang\w*\b", tasks, re.I):
        score += 6
        reasons.append("completed_cloth_work_mentioned")
        if re.search(r"\breplac\w*\b.{0,70}\b" + str(req.quantity)
                     + r"\b.{0,70}\bcloths?\b", tasks, re.I):
            score += 4
            reasons.append("requested_cloth_quantity_in_completed_work")
    if "PARTIAL_OR_UNFINISHED_WORK" in entry.get("quality_flags", []):
        score -= 5
        reasons.append("partial_work_penalty")
    if not tasks:
        reasons.append("tasks_not_verified_in_structured_ledger")
    return max(score, 0), reasons


def historical_local_rates(ledger: list[dict], country: str) -> list[dict]:
    result = []
    for entry in ledger:
        r = entry["report"]
        if (r.get("country") or "").casefold() != country.casefold():
            continue
        observations = []
        for item in r.get("cost_items", []):
            if item.get("category") not in {"labor", "travel"}:
                continue
            if item.get("unit_rate") is None or item.get("currency") is None:
                continue
            if item.get("amount_reported") is None or item.get("quantity") is None:
                continue
            exact_line(item["quantity"], item["unit_rate"], item["amount_reported"])
            observations.append({
                "category": item["category"],
                "hourly_rate": str(dec(item["unit_rate"])),
                "currency": item["currency"],
                "source": f"{r['report_id']}:{item['source']['location']}",
            })
        if observations:
            result.append({"report_id": r["report_id"], "equipment": r.get("equipment_model"),
                           "date": r.get("visit_date"), "rates": observations})
    return result


def build_planning_comparison(ledger: list[dict], req: ServiceRequest, raw_dir: Path) -> dict:
    indexed = {entry["report"]["report_id"]: entry for entry in ledger}
    scored = []
    for entry in ledger:
        score, reasons = score_task(entry, req)
        if score > 0:
            r = entry["report"]
            scored.append({"report_id": r["report_id"], "equipment": r.get("equipment_model"),
                           "country": r.get("country"), "date": r.get("visit_date"),
                           "score": score, "reasons": reasons,
                           "source_printed_total": r.get("reported_total"),
                           "source_printed_currency": r.get("total_currency"),
                           "quality_flags": entry.get("quality_flags", [])})
    scored.sort(key=lambda x: (-x["score"], x["report_id"]))
    # Validate every raw source used in the displayed comparison, not just the
    # top match, so a stale Stage04 cache cannot silently support an answer.
    local_rates = historical_local_rates(ledger, req.country)
    referenced_ids = {r["report_id"] for r in scored[:5]}
    referenced_ids.update(r["report_id"] for r in local_rates)
    for report_id in referenced_ids:
        verify_original(indexed[report_id], raw_dir)
    analog = None
    if scored:
        analog = reconstructed_case(indexed[scored[0]["report_id"]], raw_dir)
    return {
        "request": {"country": req.country, "equipment": req.equipment,
                    "task": req.task, "quantity": req.quantity,
                    "site": req.site, "parts_supplier": req.parts_supplier},
        "task_analogs": scored[:5],
        "best_historical_analog": analog,
        "local_historical_rates_other_scopes": local_rates,
        "site_specific_budget": None,
        "site_specific_budget_currency": None,
        "status": "INSUFFICIENT_EVIDENCE_FOR_SITE_SPECIFIC_QUOTE",
        "questions": (["What is the exact customer site in " + req.country + "?"] if not req.site else [])
                     + (["Who supplies the replacement cloths?"] if req.parts_supplier == "unknown" else []),
        "warnings": [
            "Historical analog amounts are not current prices or binding quotations.",
            "Do not convert or add currencies without an authorized exchange rate.",
            "Unknown technician origin, travel, accommodation and taxes are excluded rather than guessed.",
            "PF-DS endless-cloth brochure terminology differs from multi-cloth service reports; confirm part identity.",
            "Stage04 manual gold-case review is pending; treat extracted values as provisional.",
        ],
    }


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Local Stage05 historical cost comparison (not a quote)")
    parser.add_argument("--country", required=True)
    parser.add_argument("--equipment", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--quantity", type=int, required=True)
    parser.add_argument("--site")
    parser.add_argument("--parts-supplier", choices=["unknown", "customer", "supplier"], default="unknown")
    parser.add_argument("--ledger", type=Path, default=root / "local_cache/service_ledger.json")
    parser.add_argument("--raw", type=Path, default=root / "raw/data/HistoricalServices")
    parser.add_argument("--output", type=Path, default=root / "local_cache/stage05_cost_comparison.json")
    args = parser.parse_args()
    try:
        request = ServiceRequest(args.country, args.equipment, args.task, args.quantity,
                                 args.site, args.parts_supplier)
        result = build_planning_comparison(load_ledger(args.ledger), request, args.raw)
    except (EvidenceError, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Stage05 evidence error: {exc}\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Stage05 historical evidence comparison — NOT A COMMERCIAL QUOTE")
    print(f"Target: {request.quantity} {request.task} on {request.equipment} in {request.country}")
    print(f"Task analogs: {[r['report_id'] for r in result['task_analogs']]}")
    analog = result["best_historical_analog"]
    if analog:
        reconstructed = analog.get("reconstructed")
        if reconstructed:
            print(f"Closest historical item sum: {reconstructed['amount']} {reconstructed['currency']} ")
            print("PROVISIONAL reconstruction — NOT an invoice total or Chile price")
        elif analog.get("printed_total"):
            if analog.get("printed_currency"):
                print(f"Historical printed total: {analog['printed_total']} {analog['printed_currency']}")
            else:
                print("Historical printed total has UNKNOWN CURRENCY; not usable for costing")
    print(f"Geographic comparator reports with supported hourly rates: {len(result['local_historical_rates_other_scopes'])}")
    print("Site-specific budget: INSUFFICIENT EVIDENCE (no invented number)")
    for q in result['questions']:
        print(f"Follow-up: {q}")
    print(f"Private comparison: {args.output}")


if __name__ == "__main__":
    main()
