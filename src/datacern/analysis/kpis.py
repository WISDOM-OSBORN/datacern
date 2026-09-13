"""Automatic KPI computation over tabular data.

Detects numeric measure columns and categorical group columns and computes
totals, means, and top/bottom groups — deterministic facts the LLM can cite
instead of estimating from text chunks.
"""

from __future__ import annotations

import pandas as pd

MEASURE_HINTS = (
    "revenue",
    "profit",
    "sales",
    "amount",
    "total",
    "cost",
    "units_sold",
    "quantity",
    "price",
    "value",
)


def _measure_columns(df: pd.DataFrame) -> list[str]:
    numeric = df.select_dtypes(include="number").columns.tolist()
    hinted = [c for c in numeric if any(h in c.lower() for h in MEASURE_HINTS)]
    return hinted or numeric[:4]


def _group_columns(df: pd.DataFrame) -> list[str]:
    from datacern.data.profiling import categorical_columns

    cats = categorical_columns(df)
    return [c for c in cats if 1 < df[c].nunique() <= 50][:3]


def compute_kpis(df: pd.DataFrame | None, top_n: int = 5) -> str:
    """Return a textual KPI summary with exact computed figures."""
    if df is None or df.empty:
        return "No KPI data available."

    measures = _measure_columns(df)
    groups = _group_columns(df)
    if not measures:
        return "No numeric measure columns detected."

    lines = ["KEY PERFORMANCE INDICATORS (computed, cite these exactly):"]
    for measure in measures:
        series = df[measure].dropna()
        lines.append(
            f"- {measure}: total={series.sum():,.2f} mean={series.mean():,.2f} "
            f"min={series.min():,.2f} max={series.max():,.2f} (n={len(series)})"
        )
        for group in groups:
            try:
                grouped = df.groupby(group)[measure].sum().sort_values(ascending=False)
            except Exception:  # noqa: BLE001
                continue
            top = grouped.head(top_n)
            bottom = grouped.tail(top_n)
            lines.append(
                f"  by {group} — top {top_n}: "
                + "; ".join(f"{idx}={val:,.2f}" for idx, val in top.items())
            )
            lines.append(
                f"  by {group} — bottom {top_n}: "
                + "; ".join(f"{idx}={val:,.2f}" for idx, val in bottom.items())
            )
    return "\n".join(lines)
