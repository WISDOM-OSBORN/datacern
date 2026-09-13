"""Insight assembly: combine deterministic analysis into prompt context."""

from __future__ import annotations

import pandas as pd

from datacern.analysis.anomalies import detect_anomalies
from datacern.analysis.kpis import compute_kpis
from datacern.data.profiling import profile_dataframe


def build_insight_context(df: pd.DataFrame | None) -> str:
    """Assemble KPI + anomaly + quality context for report prompts."""
    sections = [
        compute_kpis(df),
        "",
        detect_anomalies(df),
        "",
        "DATA QUALITY:",
        profile_dataframe(df),
    ]
    return "\n".join(sections)
