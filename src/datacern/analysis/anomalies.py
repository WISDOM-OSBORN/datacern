"""Lightweight anomaly detection over tabular data.

Uses IQR-based outlier detection on numeric measure columns, plus simple
time-series spike checks when a date column is present. Results are textual
so they can be embedded directly in report prompts.
"""

from __future__ import annotations

import pandas as pd

from datacern.analysis.kpis import _measure_columns


def _iqr_outliers(series: pd.Series, k: float = 1.5) -> pd.Series:
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0 or pd.isna(iqr):
        return series.iloc[0:0]
    return series[(series < q1 - k * iqr) | (series > q3 + k * iqr)]


def detect_anomalies(df: pd.DataFrame | None, max_examples: int = 5) -> str:
    """Return a textual anomaly summary (outliers and spikes)."""
    if df is None or df.empty:
        return "No anomaly scan possible (no tabular data)."

    lines = ["ANOMALY SCAN (IQR outliers, deterministic):"]
    found = False
    for measure in _measure_columns(df):
        series = df[measure].dropna()
        if len(series) < 8:
            continue
        outliers = _iqr_outliers(series)
        if outliers.empty:
            lines.append(f"- {measure}: no outliers detected")
            continue
        found = True
        examples = ", ".join(f"{v:,.2f}" for v in outliers.head(max_examples).tolist())
        lines.append(
            f"- {measure}: {len(outliers)} outlier(s) out of {len(series)} (e.g. {examples})"
        )

    date_cols = [c for c in df.columns if "date" in c.lower()]
    if date_cols and _measure_columns(df):
        try:
            dates = pd.to_datetime(df[date_cols[0]], errors="coerce")
            measure = _measure_columns(df)[0]
            monthly = (
                df.assign(_d=dates)
                .dropna(subset=["_d"])
                .groupby(pd.Grouper(key="_d", freq="ME"))[measure]
                .sum()
            )
            if len(monthly) >= 4:
                pct = monthly.pct_change().dropna()
                spikes = pct[pct.abs() > 0.5]
                if not spikes.empty:
                    found = True
                    examples = "; ".join(
                        f"{idx.date()} {v:+.0%}" for idx, v in spikes.head(max_examples).items()
                    )
                    lines.append(f"- {measure} monthly swings >50%: {examples}")
        except Exception:  # noqa: BLE001
            pass

    if not found:
        lines.append("No strong anomalies detected.")
    return "\n".join(lines)
