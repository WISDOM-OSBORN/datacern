"""Tests for profiling, KPIs, anomalies, chart planning/validation, storage."""

import pandas as pd

from datacern.analysis.anomalies import detect_anomalies
from datacern.analysis.insights import build_insight_context
from datacern.analysis.kpis import compute_kpis
from datacern.charts.planner import plan_charts
from datacern.charts.validator import validate_execution
from datacern.data.profiling import profile_dataframe
from datacern.rag.pipeline import collection_name_for
from datacern.services.storage import RunStore, sanitize_stem


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "region": ["N", "N", "S", "S", "E", "W", "N", "S", "E", "W"],
            "revenue": [100, 200, 150, 50, 10_000, 120, 130, 140, 110, 105],
            "profit": [10, 20, 15, 5, 900, 12, 13, 14, 11, 10],
        }
    )


def _small_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "region": ["N", "N", "S", "S", "E", "W"],
            "revenue": [100, 200, 150, 50, 300, 120],
            "profit": [10, 20, 15, 5, 30, 12],
        }
    )


def test_kpis_contain_exact_totals():
    text = compute_kpis(_small_df())
    assert "total=920.00" in text
    assert "by region" in text


def test_anomalies_flag_outlier():
    text = detect_anomalies(_df())
    assert "10,000.00" in text


def test_profiling_reports_shape_and_duplicates():
    text = profile_dataframe(_small_df())
    assert "rows: 6" in text
    assert "duplicate rows:" in text


def test_insight_context_combines_sections():
    text = build_insight_context(_small_df())
    assert "KEY PERFORMANCE INDICATORS" in text
    assert "ANOMALY SCAN" in text
    assert "DATA QUALITY" in text


def test_chart_plan_mentions_columns():
    plan = plan_charts(_small_df(), "compare revenue by region")
    assert "revenue" in plan and "region" in plan


def test_validator_flags_failures():
    assert validate_execution({"success": False, "error": "boom", "images": []})
    assert validate_execution({"success": True, "error": "", "images": [b"x" * 10]})
    assert validate_execution({"success": True, "error": "", "images": [b"x" * 10_000]}) == []


def test_collection_name_is_content_sensitive():
    a = collection_name_for("sales.csv", "hash-1")
    b = collection_name_for("sales.csv", "hash-2")
    c = collection_name_for("sales.csv", "hash-1")
    assert a != b
    assert a == c


def test_run_store_sanitizes_temp_names(tmp_path, monkeypatch):
    import datacern.services.storage as storage_mod

    monkeypatch.setattr(storage_mod.config, "OUTPUT_PATH", tmp_path)
    store = RunStore("abc123", "sales_data.csv")
    assert "abc123" in store.report_path.name
    assert "sales_data" in store.report_path.name
    assert sanitize_stem("../../etc/passwd") == "passwd"
    assert sanitize_stem("my report (final).csv") == "my_report_final"
