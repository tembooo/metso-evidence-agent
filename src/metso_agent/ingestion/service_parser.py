"""Stage 04: conservative FSR extraction. All outputs are PRIVATE.

The parser records observations and source lines; it does NOT issue quotes.
Run: python -m metso_agent.ingestion.service_parser
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from metso_agent.schemas import CostItem, ServiceReport, SourceRef

FSR_ID = re.compile(r"FSR-\d{4}", re.IGNORECASE)
CURRENCIES = {"EUR", "USD", "CAD", "AUD", "SEK", "ZAR", "CLP", "PEN"}
AMOUNT = re.compile(r"(?<![\w.])-?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)")
SITE_LABEL = re.compile(r"^(?:-\s*)?(?:site location|site|location)\s*:\s*(.+)", re.I)
EQUIPMENT_LABEL = re.compile(r"^(?:-\s*)?(?:equipment serviced|equipment worked on|equipment type|equipment|equip)\s*:\s*(.*)", re.I)
DATE_LABEL = re.compile(r"^(?:visit date|date of visit|date)\s*:\s*(.+)", re.I)
ON_SITE = re.compile(r"(?:total\s+)?(?:on[ -]?site\s+hours|hours\s+on\s+site|time\s+on\s+site|hours\s+on[ -]?site)", re.I)
TRAVEL = re.compile(r"(?:travel(?:\s+time|\s+hours|\s+hrs)?|traveled|travelled)", re.I)
UNKNOWN_PRICE = re.compile(r"invoice\s+(?:to\s+)?follow|as\s+per\s+agreement|cost\s+per\s+agreement|see\s+agreement|see\s+PO|cost\s*\(see\s+agreement", re.I)
PARTIAL_WORK = re.compile(r"did not finish|couldn['’]t fully|not finish|partial cloth|only partial|unfinished|did not complete|could not complete", re.I)
REVIEW_SECTIONS = ("cost summary", "materials and parts used", "materials/parts used", "materials / parts used")


def clean(line: str) -> str:
    return re.sub(r"[*`]", "", line).strip()


def number(text: str) -> Decimal | None:
    match = AMOUNT.search(text)
    if not match:
        return None
    try:
        return Decimal(match.group().replace(",", ""))
    except InvalidOperation:
        return None


def source_currency(text: str) -> str | None:
    words = set(re.findall(r"\b[A-Z]{3}\b", text)) & CURRENCIES
    if len(words) == 1:
        return next(iter(words))
    if len(words) > 1:
        return None
    if "€" in text:
        return "EUR"
    return None  # '$' alone is ambiguous; no geographic inference.


def reported_hours(lines: list[str], kind: str) -> tuple[Decimal | None, int | None]:
    for i, original in enumerate(lines, start=1):
        line = clean(original)
        if kind == "labor" and ON_SITE.search(line):
            if "|" in line:
                values = [number(c) for c in line.split("|")[1:]]
                values = [v for v in values if v is not None]
                if values:
                    return values[-1], i
            tail = ON_SITE.split(line, maxsplit=1)[-1]
            m = re.search(r"(?:was|were|for|is|of|about|around|approx\.?|:)\s*(?:about\s*)?(\d+(?:\.\d+)?)", tail, re.I)
            if m:
                return Decimal(m.group(1)), i
            v = number(tail)
            if v is not None:
                return v, i
        if kind == "labor":
            m = re.search(r"(?:spent|worked|on\s+site\s+for)\s+(?:about\s+)?(\d+(?:\.\d+)?)\s*h(?:ours?)?\s*(?:on[ -]?site|at\s+(?:the\s+)?site)", line, re.I)
            if m:
                return Decimal(m.group(1)), i
        if kind == "travel":
            if "each way" in line.casefold():
                # One-way travel is not a reliable round-trip total.
                continue
            if TRAVEL.search(line):
                # Avoid reading the clock in narrative descriptions.
                m = re.search(r"(?:travel\s*(?:time|hours?|hrs?)?\s*(?:\([^)]*\))?|traveled|travelled)\s*[:=]?\s*(?:about|around|roughly)?\s*(\d+(?:\.\d+)?)\s*(?:h|hours?)?\b", line, re.I)
                if m:
                    return Decimal(m.group(1)), i
                m = re.search(r"(?:with|and)\s+(\d+(?:\.\d+)?)\s+hours?\s+(?:spent\s+)?travell?ing", line, re.I)
                if m:
                    return Decimal(m.group(1)), i
                if "|" in line and re.search(r"\bTravel\b", line, re.I):
                    cells = [c.strip() for c in line.strip("|").split("|")]
                    if len(cells) >= 3:
                        v = number(cells[1] if len(cells) == 4 else cells[2])
                        if v is not None:
                            return v, i
    return None, None


def elapsed_hours_from_task_table(lines: list[str]) -> Decimal | None:
    """Elapsed span is a comparison, not a replacement for billable labor."""
    times = []
    for line in lines:
        if "|" not in line or "Total On-Site Hours" in line:
            continue
        found = re.findall(r"\b(?:[01]\d|2[0-3]):[0-5]\d\b", line)
        if len(found) >= 2:
            times.append((found[0], found[1]))
    if len(times) < 2:
        return None
    start = datetime.strptime(times[0][0], "%H:%M")
    end = datetime.strptime(times[-1][1], "%H:%M")
    minutes = (end - start).total_seconds() / 60
    return Decimal(str(minutes / 60)) if minutes >= 0 else None


def parse_date(value: str) -> date | None:
    match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", value)
    if match:
        try:
            return date.fromisoformat(match.group())
        except ValueError:
            return None
    # Slash dates are intentionally not guessed: 08/01/24 is ambiguous.
    return None


def category_of(label: str) -> str:
    if re.search(r"trav(?:el|elling)", label, re.I):
        return "travel"
    if re.search(r"labou?r|technician\s+hours", label, re.I):
        return "labor"
    if re.search(r"cleaning|gloves|lubricant|oil|solvent", label, re.I):
        return "consumables"
    return "parts"


def extract_cost_items(lines: list[str], report_id: str, fallback_currency: str | None) -> tuple[list[CostItem], list[dict], list[str]]:
    """Only explicit cost-table lines become CostItems; uncertain rows remain for review."""
    items: list[CostItem] = []
    candidates: list[dict] = []
    issues: list[str] = []
    active = False
    heading_currency = None
    for i, original in enumerate(lines, start=1):
        line = clean(original)
        lowered = line.lower()
        if "cost summary" in lowered:
            active = True
            heading_currency = None
            continue
        if active and (line.startswith("---") or (line.startswith("#") and not line.startswith("|"))):
            active = False
        if not active or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4 or all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        label = cells[0]
        if re.search(r"^(?:description|item|task|part)", label, re.I):
            heading_currency = source_currency(line) or fallback_currency
            continue
        if re.search(r"\b(?:subtotal|vat|tax|total|amount due)\b", label, re.I):
            continue
        if not label or not any(number(c) is not None for c in cells[1:]):
            continue
        # Last column is the reported monetary extension, not a new derived calculation.
        amount = number(cells[-1])
        qty_cell = cells[-3] if len(cells) >= 5 else cells[1]
        quantity = number(qty_cell)
        rate = number(cells[-2])
        currency = source_currency(line) or heading_currency or fallback_currency
        candidate = {"line": i, "label": label, "reported_amount": str(amount) if amount is not None else None,
                     "currency": currency, "source_line": original.strip()}
        candidates.append(candidate)
        if not currency or amount is None:
            issues.append(f"COST_ROW_REVIEW_LINE_{i}")
            continue
        items.append(CostItem(
            category=category_of(label), description=label,
            quantity=quantity if quantity is not None and quantity > 0 else None,
            unit_rate=rate, currency=currency,
            amount_reported=amount,
            source=SourceRef(source_kind="service_report", document_id=report_id, location=f"line:{i}"),
        ))
    return items, candidates, issues


def extract_total(lines: list[str]) -> tuple[Decimal | None, str | None, int | None]:
    """Prefer a printed total. Never compute a total from rows here."""
    for i, original in reversed(list(enumerate(lines, start=1))):
        line = clean(original)
        if not re.search(r"(?:\btotal\s+(?:due|amount due|cost|for\s+this\s+visit)\b|\bcost\s+total\b|^\|\s*Total\s*\||^Total\s*\(|^Total\s*:\s*)", line, re.I):
            continue
        if re.search(r"on[ -]?site\s+hours|travel\s+hours|total\s+time", line, re.I):
            continue
        amount = number(line.split("|")[-2] if "|" in line else line.split(":", 1)[-1])
        if amount is not None:
            return amount, source_currency(line), i
    return None, None, None


def extract_tasks(lines: list[str]) -> tuple[list[str], list[dict]]:
    """Only explicitly listed completed work / job-summary bullets are extracted."""
    section = None
    tasks: list[str] = []
    observed: list[dict] = []
    for i, original in enumerate(lines, start=1):
        content = clean(original)
        if re.match(r"^(?:#{1,6}\s*)?(?:work completed|job summary)\s*:?$", content, re.I):
            section = "work_completed" if "work completed" in content.lower() else "job_summary"
            continue
        if section and (content.startswith("---") or content.startswith("###") or re.match(r"^[A-Z][A-Za-z /]+:$", content)):
            section = None
        if section and re.match(r"^-\s+\S", content):
            task = content[2:].strip()
            tasks.append(task)
            observed.append({"line": i, "text": task, "section": section})
    return tasks, observed


def extract_material_rows(lines: list[str]) -> list[dict]:
    """Capture material-table rows for review without counting costs twice."""
    results: list[dict] = []
    active = False
    for i, original in enumerate(lines, start=1):
        content = clean(original)
        if re.search(r"^(?:#{1,6}\s*)?materials\s*(?:and|/|&)\s*parts\s*used\s*:?$", content, re.I):
            active = True
            continue
        if active and (content.startswith("---") or content.startswith("#")):
            active = False
        if not active or not content.startswith("|"):
            continue
        cells = [c.strip() for c in content.strip("|").split("|")]
        if len(cells) < 3 or not cells[0] or re.search(r"^(?:item|part/material|part/ material|part|description)$", cells[0], re.I):
            continue
        if all(set(c) <= {"-", ":", " "} for c in cells):
            continue
        results.append({"line": i, "description": cells[0], "cells": cells[1:]})
    return results


def parse_report(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    lines = raw.splitlines()
    report_id = path.stem.upper()
    flags: list[str] = []
    fields: dict[str, dict] = {}
    found_id = FSR_ID.search(raw)
    if found_id and found_id.group().upper() != report_id:
        flags.append("REPORT_ID_MISMATCH")
    if not found_id:
        flags.append("REPORT_ID_NOT_IN_BODY")

    visit_date, site, country, equipment = None, None, None, None
    for i, original in enumerate(lines[:35], start=1):
        line = clean(original)
        if visit_date is None:
            m = DATE_LABEL.match(line)
            if m:
                value = m.group(1)
                parsed = parse_date(value)
                if parsed:
                    visit_date = parsed
                    fields["visit_date"] = {"value": value, "line": i}
                else:
                    flags.append("DATE_REQUIRES_REVIEW")
        if site is None:
            m = SITE_LABEL.match(line)
            if m:
                site = m.group(1).strip()
                fields["site"] = {"value": site, "line": i}
                if "," in site:
                    country = site.rsplit(",", 1)[-1].strip()
        if equipment is None:
            m = EQUIPMENT_LABEL.match(line)
            if m and m.group(1).strip():
                equipment = m.group(1).strip()
                fields["equipment"] = {"value": equipment, "line": i}
            elif (m is not None or re.search(r"^#{1,5}\s*equipment serviced\s*$", original.strip(), re.I)
                  or re.search(r"^equipment serviced\s*$", line, re.I)):
                for j in range(i, min(i + 5, len(lines))):
                    candidate = clean(lines[j]).lstrip("- ").strip()
                    if not candidate or candidate.startswith(("---", "#")):
                        continue
                    candidate = re.sub(r"^Type\s*:\s*", "", candidate, flags=re.I).strip()
                    if candidate and not candidate.lower().startswith("serial"):
                        equipment = candidate
                        fields["equipment"] = {"value": equipment, "line": j+1}
                        break

    labor, labor_line = reported_hours(lines, "labor")
    travel, travel_line = reported_hours(lines, "travel")
    if labor_line:
        fields["labor_hours"] = {"value": str(labor), "line": labor_line}
    if travel_line:
        fields["travel_hours"] = {"value": str(travel), "line": travel_line}

    elapsed = elapsed_hours_from_task_table(lines)
    if elapsed is not None:
        fields["activity_window_elapsed_hours"] = {"value": str(elapsed), "meaning": "elapsed clock span; not billable proof"}
        if labor is not None and abs(elapsed - labor) > Decimal("0.20"):
            flags.append("ELAPSED_VS_REPORTED_HOURS")

    currencies_in_document = set(re.findall(r"\b(?:" + "|".join(CURRENCIES) + r")\b", raw))
    if "€" in raw:
        currencies_in_document.add("EUR")
    fallback = next(iter(currencies_in_document)) if len(currencies_in_document) == 1 else None
    if len(currencies_in_document) > 1:
        flags.append("MULTIPLE_CURRENCIES_IN_REPORT")

    tasks, tasks_evidence = extract_tasks(lines)
    material_candidates = extract_material_rows(lines)
    if not tasks:
        flags.append("TASKS_REQUIRE_REVIEW")
    if labor_line and re.search(r"\b(?:about|roughly|approx|approximately)\b", lines[labor_line-1], re.I):
        flags.append("LABOR_HOURS_APPROXIMATE")
    if travel_line and re.search(r"\b(?:about|roughly|approx|approximately)\b", lines[travel_line-1], re.I):
        flags.append("TRAVEL_HOURS_APPROXIMATE")
    cost_items, cost_candidates, cost_flags = extract_cost_items(lines, report_id, fallback)
    flags.extend(cost_flags)
    total, total_currency, total_line = extract_total(lines)
    if total is not None:
        total_currency = total_currency or fallback
        fields["reported_total"] = {"value": str(total), "currency": total_currency, "line": total_line}
        if total_currency is None:
            flags.append("TOTAL_CURRENCY_UNKNOWN")
    else:
        flags.append("TOTAL_NOT_REPORTED")
    if UNKNOWN_PRICE.search(raw) and total is None:
        flags.append("PRICE_NOT_AVAILABLE")
    if PARTIAL_WORK.search(raw):
        flags.append("PARTIAL_OR_UNFINISHED_WORK")
    if re.search(r"each\s+way", raw, re.I) and TRAVEL.search(raw):
        flags.append("TRAVEL_DIRECTION_REQUIRES_REVIEW")
    if raw.rstrip().endswith(("| €", "|$", "| € ", "| £")) or re.search(r"\|\s*[€$£]\s*$", lines[-1] if lines else ""):
        flags.append("TRUNCATED_COST_TABLE")
    if labor is None:
        flags.append("LABOR_HOURS_UNCERTAIN")
    if travel is None:
        flags.append("TRAVEL_HOURS_UNCERTAIN")
    if not equipment:
        flags.append("EQUIPMENT_REQUIRES_REVIEW")
    if not site:
        flags.append("LOCATION_REQUIRES_REVIEW")
    if not cost_items and total is not None:
        flags.append("BUNDLED_TOTAL_NOT_ITEMIZED")
    if cost_items and total is None:
        flags.append("PARTIAL_ITEMIZED_COST_ONLY")

    report = ServiceReport(
        report_id=report_id,
        source=SourceRef(source_kind="service_report", document_id=report_id, location="entire_report"),
        visit_date=visit_date, country=country, site=site, equipment_model=equipment,
        tasks=tasks, labor_hours=labor, travel_hours=travel,
        cost_items=cost_items, reported_total=total,
        total_currency=total_currency,
        quality_flags=sorted(set(flags)),
    )
    return {"report": report.model_dump(mode="json"), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "observations": fields, "task_evidence": tasks_evidence,
            "material_row_candidates": material_candidates,
            "cost_row_candidates": cost_candidates,
            "review_required": bool(flags), "quality_flags": sorted(set(flags))}


def build_ledger(folder: Path) -> list[dict]:
    files = sorted(folder.glob("FSR-*.txt"))
    if len(files) != 50:
        raise ValueError(f"Expected 50 service reports, found {len(files)}")
    wanted = {f"FSR-{i:04}" for i in range(1, 51)}
    seen = {p.stem.upper() for p in files}
    if wanted != seen:
        raise ValueError(f"FSR numbering mismatch: missing={sorted(wanted-seen)} extra={sorted(seen-wanted)}")
    return [parse_report(p) for p in files]


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Private audit-first extraction of Metso FSRs")
    parser.add_argument("--source", type=Path, default=root / "raw/data/HistoricalServices")
    parser.add_argument("--output", type=Path, default=root / "local_cache/service_ledger.json")
    args = parser.parse_args()
    records = build_ledger(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    issues = [{"report_id": item["report"]["report_id"], "quality_flags": item["quality_flags"]}
              for item in records if item["quality_flags"]]
    issues_path = args.output.with_name("service_quality_issues.json")
    issues_path.write_text(json.dumps(issues, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Processed: {len(records)} reports")
    print(f"Private ledger: {args.output}")
    print(f"Private issue log: {issues_path} ({len(issues)} records flagged)")
    for item in records:
        r = item["report"]
        print(f"{r['report_id']}: {len(r['cost_items'])} cost rows, flags={','.join(item['quality_flags']) or 'none'}")
    print("WARNING: extraction is provisional; review flagged fields against originals before pricing.")


if __name__ == "__main__":
    main()
