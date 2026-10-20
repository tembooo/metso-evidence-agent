"""Read-only local review of Stage 04 ledger; keep output private."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Review private service-report ledger")
    parser.add_argument("--ledger", type=Path, default=Path("local_cache/service_ledger.json"))
    parser.add_argument("--ids", nargs="*", default=["FSR-0027", "FSR-0028", "FSR-0031", "FSR-0014", "FSR-0035", "FSR-0044"])
    args = parser.parse_args()
    records = json.loads(args.ledger.read_text(encoding="utf-8"))
    lookup = {item["report"]["report_id"]: item for item in records}
    for report_id in args.ids:
        entry = lookup.get(report_id.upper())
        if not entry:
            print(f"{report_id}: MISSING")
            continue
        r = entry["report"]
        print(f"\n{report_id} | {r['visit_date']} | {r['site']} | {r['equipment_model']}")
        print(f"  Labor hours: {r['labor_hours']} | Travel hours: {r['travel_hours']}")
        print(f"  Source printed total: {r['reported_total']} {r['total_currency'] or '(unknown currency)'}")
        print(f"  Parsed cost rows: {len(r['cost_items'])} | Material row candidates: {len(entry['material_row_candidates'])}")
        print(f"  Quality flags: {', '.join(entry['quality_flags']) or '(none: still sample-review)'}")
        print(f"  Source SHA-256: {entry['source_sha256'][:12]}...")


if __name__ == "__main__":
    main()
