"""Synthetic-only, independent Stage08 tests; do not include supplied CSV in Git."""
from pathlib import Path
import math

import pandas as pd
import pytest

from metso_agent.analytics.flotation import analyze_csv, FlotationEvidenceError


def fixture_csv(tmp_path: Path, values=((3.1, 64.5), (1.0, 67.0), (4.2, 63.0))):
    p = tmp_path / "small.csv"
    pd.DataFrame({
        "date": [f"2026-01-01 {hour:02d}:00:00" for hour in range(len(values))],
        "% Silica Concentrate": [x[0] for x in values],
        "% Iron Concentrate": [x[1] for x in values],
    }).to_csv(p, index=False)
    return p


def test_inclusive_threshold_counts(tmp_path):
    result = analyze_csv(fixture_csv(tmp_path), 3.1, 64.5)
    assert result['counts'] == {'silica_at_or_above': 2, 'iron_at_or_below': 2, 'both_conditions': 2}
    assert result['percent_of_rows']['both_conditions'] == pytest.approx(66.6667)


def test_source_and_n_are_reported(tmp_path):
    result = analyze_csv(fixture_csv(tmp_path), 3.1, 64.5)
    assert result['source']['filename'] == 'small.csv'
    assert result['source']['row_count'] == 3


def test_means_are_computed(tmp_path):
    result = analyze_csv(fixture_csv(tmp_path), 3.1, 64.5)
    assert result['reference']['silica']['mean'] == pytest.approx((3.1 + 1 + 4.2) / 3, abs=1e-5)


def test_distinct_thresholds_change_counts(tmp_path):
    p = fixture_csv(tmp_path)
    assert analyze_csv(p, 4, 64.5)['counts']['both_conditions'] == 1
    assert analyze_csv(p, 5, 60)['counts']['both_conditions'] == 0


def test_reject_missing_csv(tmp_path):
    with pytest.raises(FileNotFoundError):
        analyze_csv(tmp_path / 'absent.csv', 3.1, 64.5)


def test_reject_invalid_threshold_nan(tmp_path):
    with pytest.raises(FlotationEvidenceError):
        analyze_csv(fixture_csv(tmp_path), math.nan, 64.5)


def test_reject_threshold_boolean(tmp_path):
    with pytest.raises(FlotationEvidenceError):
        analyze_csv(fixture_csv(tmp_path), True, 64.5)


def test_reject_percentage_outside_range(tmp_path):
    with pytest.raises(FlotationEvidenceError):
        analyze_csv(fixture_csv(tmp_path), 3.1, 101)


def test_reject_missing_quality_column(tmp_path):
    p = tmp_path / 'invalid.csv'
    p.write_text('date,% Silica Concentrate\n2026-01-01 00:00:00,3.1\n', encoding='utf-8')
    with pytest.raises(FlotationEvidenceError, match='Missing required'):
        analyze_csv(p, 3.1, 64.5)


def test_reject_non_numeric_measurement(tmp_path):
    p = fixture_csv(tmp_path)
    df = pd.read_csv(p)
    df['% Iron Concentrate'] = df['% Iron Concentrate'].astype(object)
    df.loc[1, '% Iron Concentrate'] = 'NA_NOT_A_NUMBER'
    df.to_csv(p, index=False)
    with pytest.raises(FlotationEvidenceError):
        analyze_csv(p, 3.1, 64.5)


def test_detect_timestamp_gap(tmp_path):
    p = fixture_csv(tmp_path)
    df = pd.read_csv(p)
    df.loc[2, 'date'] = '2026-01-05 02:00:00'
    df.to_csv(p, index=False)
    result = analyze_csv(p, 3.1, 64.5)
    assert result['data_quality']['gaps_over_one_hour'] == 1
    assert result['data_quality']['max_gap_hours'] == pytest.approx(97.0)


def test_no_contractual_claim(tmp_path):
    result = analyze_csv(fixture_csv(tmp_path), 3.1, 64.5)
    assert result['status'] == 'HISTORICAL_DESCRIPTION_ONLY'
    assert 'NOT a contractual' in result['interpretation']
