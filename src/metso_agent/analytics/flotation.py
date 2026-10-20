"""Stage 08 — deterministic, source-traceable flotation-quality comparison.

Uses only the supplied local CSV. Historical frequency is not a plant quality
standard, a causal inference, or permission to prescribe operating settings.
No API use. No raw records are written to disk.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DATE_COL = "date"
IRON_COL = "% Iron Concentrate"
SILICA_COL = "% Silica Concentrate"
REQUIRED_COLUMNS = (DATE_COL, IRON_COL, SILICA_COL)


class FlotationEvidenceError(ValueError):
    """Invalid CSV schema, observation, or requested threshold."""


def _threshold(label: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise FlotationEvidenceError(f"{label} must be a numeric percentage")
    result = float(value)
    if not math.isfinite(result) or not 0 <= result <= 100:
        raise FlotationEvidenceError(f"{label} must be finite and within [0, 100]")
    return result


def _describe(series: pd.Series) -> dict[str, float]:
    # pandas standard deviation uses ddof=1; do not present as population std.
    return {
        "mean": round(float(series.mean()), 6),
        "median": round(float(series.median()), 6),
        "sample_std": round(float(series.std(ddof=1)), 6) if len(series) > 1 else None,
        "min": float(series.min()),
        "q25": round(float(series.quantile(0.25)), 6),
        "q75": round(float(series.quantile(0.75)), 6),
        "max": float(series.max()),
    }


def analyze_csv(path: str | Path, silica_pct: float, iron_pct: float) -> dict[str, Any]:
    """Read CSV and compare requested concentrate values against observed rows.

    For a customer with silica s and iron f, compare:
       historical silica >= s, iron <= f, and the conjunction.
    Comparisons are inclusive. Rates are descriptive sample frequencies.
    """
    s = _threshold("silica_pct", silica_pct)
    f = _threshold("iron_pct", iron_pct)
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Missing local flotation CSV: {source}")
    try:
        df = pd.read_csv(source, encoding="utf-8")
    except (pd.errors.ParserError, UnicodeError, ValueError) as exc:
        raise FlotationEvidenceError("Unable to parse flotation CSV") from exc
    absent = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if absent:
        raise FlotationEvidenceError(f"Missing required CSV columns: {', '.join(absent)}")
    if df.empty:
        raise FlotationEvidenceError("Flotation CSV is empty")
    try:
        timestamps = pd.to_datetime(df[DATE_COL], format="%Y-%m-%d %H:%M:%S", errors="raise")
        silica = pd.to_numeric(df[SILICA_COL], errors="raise")
        iron = pd.to_numeric(df[IRON_COL], errors="raise")
    except (ValueError, TypeError) as exc:
        raise FlotationEvidenceError("Invalid date or numeric quality measurement") from exc
    if timestamps.isna().any() or silica.isna().any() or iron.isna().any():
        raise FlotationEvidenceError("Required timestamps or concentrate values contain nulls")
    if not (np.isfinite(silica.to_numpy(dtype=float)).all()
            and np.isfinite(iron.to_numpy(dtype=float)).all()):
        raise FlotationEvidenceError("Non-finite concentrate measurements")
    if not silica.between(0, 100).all() or not iron.between(0, 100).all():
        raise FlotationEvidenceError("Concentrate percentages outside [0, 100]")
    count = len(df)
    silica_cond = silica >= s
    iron_cond = iron <= f
    both_cond = silica_cond & iron_cond
    metrics = {
        "silica_at_or_above": int(silica_cond.sum()),
        "iron_at_or_below": int(iron_cond.sum()),
        "both_conditions": int(both_cond.sum()),
    }
    pct = {name: round(100.0 * c / count, 4) for name, c in metrics.items()}
    sorted_dates = timestamps.sort_values()
    gaps = sorted_dates.diff().dropna()
    gap_over_one_hour = gaps[gaps > pd.Timedelta(hours=1)]
    max_gap_hours = round(float(gaps.max() / pd.Timedelta(hours=1)), 3) if len(gaps) else None
    corr = float(silica.corr(iron)) if count > 1 else float("nan")

    return {
        "status": "HISTORICAL_DESCRIPTION_ONLY",
        "source": {"kind": "flotation_csv", "filename": source.name,
                   "row_count": count, "column_count": len(df.columns)},
        "customer": {"silica_pct": s, "iron_pct": f},
        "reference": {"silica": _describe(silica), "iron": _describe(iron),
                      "pearson_correlation": round(corr, 6) if math.isfinite(corr) else None},
        "counts": metrics,
        "percent_of_rows": pct,
        "data_quality": {
            "first_timestamp": sorted_dates.iloc[0].isoformat(sep=" "),
            "last_timestamp": sorted_dates.iloc[-1].isoformat(sep=" "),
            "duplicate_timestamps": int(timestamps.duplicated().sum()),
            "gaps_over_one_hour": len(gap_over_one_hour),
            "max_gap_hours": max_gap_hours,
        },
        "interpretation": (
            "The measurements are compared with historical hourly observations. "
            "Historical prevalence is NOT a contractual or technical acceptability limit."
        ),
        "limitations": [
            "No customer quality contract or acceptable specification is provided.",
            "Correlation is not evidence of causation.",
            "This is descriptive historical evidence, not a forecast or a process-control prescription.",
            "One or more timestamp gaps may exist; check data_quality before claiming continuity.",
        ],
    }


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Optional Stage 08 flotation quality comparison")
    parser.add_argument("--silica", type=float, required=True, help="Customer silica concentrate percentage")
    parser.add_argument("--iron", type=float, required=True, help="Customer iron concentrate percentage")
    parser.add_argument("--csv", type=Path, default=root / "raw/data/flotation_process_data_hourly.csv")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON to stdout")
    parser.add_argument("--output", type=Path, help="Optional local JSON output (use an ignored directory)")
    args = parser.parse_args()
    try:
        result = analyze_csv(args.csv, args.silica, args.iron)
    except (FileNotFoundError, FlotationEvidenceError) as exc:
        parser.error(str(exc))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        n = result["source"]["row_count"]
        c = result["counts"]
        p = result["percent_of_rows"]
        r = result["reference"]
        q = result["data_quality"]
        print("Stage 08 — flotation historical comparison (NOT a specification)")
        print(f"Evidence: {result['source']['filename']} | observations: {n} | columns: {result['source']['column_count']}")
        print(f"Silica {args.silica:g}% vs historical mean {r['silica']['mean']:.3f}%: "
              f"{c['silica_at_or_above']}/{n} ({p['silica_at_or_above']:.2f}%) >= threshold")
        print(f"Iron {args.iron:g}% vs historical mean {r['iron']['mean']:.3f}%: "
              f"{c['iron_at_or_below']}/{n} ({p['iron_at_or_below']:.2f}%) <= threshold")
        print(f"Both conditions: {c['both_conditions']}/{n} ({p['both_conditions']:.2f}%)")
        print(f"Pearson correlation: {r['pearson_correlation']}")
        print(f"Max time gap (hours): {q['max_gap_hours']} | gaps >1h: {q['gaps_over_one_hour']}")
        print("WARNING: Historical occurrence does not prove customer-contract acceptability.")
        print("Follow-up: What are the customer's maximum silica and minimum iron contract limits?")


if __name__ == "__main__":
    main()
