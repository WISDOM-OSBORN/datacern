"""Data quality profiling for tabular inputs.

Produces a compact, LLM-friendly quality report: missing values, duplicates,
constant columns, and suspicious values — the basis of the "Data Quality"
report section.
"""

from __future__ import annotations

import pandas as pd


def categorical_columns(df: pd.DataFrame) -> list[str]:
    """Object/category/str columns, tolerant of pandas 2 vs 3 string dtypes."""
    try:
        return df.select_dtypes(include=["object", "category", "str"]).columns.tolist()
    except (TypeError, ValueError):
        return df.select_dtypes(include=["object", "category"]).columns.tolist()


def profile_dataframe(df: pd.DataFrame | None, max_examples: int = 3) -> str:
    """Return a short textual data-quality profile of ``df``."""
    if df is None:
        return "No tabular data available (input was a PDF)."
    if df.empty:
        return "The table is empty (0 rows)."

    lines = [
        f"rows: {len(df)}, columns: {len(df.columns)}",
        f"duplicate rows: {int(df.duplicated().sum())}",
    ]

    missing = df.isna().sum()
    missing_cols = missing[missing > 0]
    if missing_cols.empty:
        lines.append("missing values: none")
    else:
        lines.append("missing values:")
        for col, count in missing_cols.items():
            pct = 100.0 * count / len(df)
            lines.append(f"  - {col}: {count} ({pct:.1f}%)")

    constant = [c for c in df.columns if df[c].nunique(dropna=False) <= 1]
    if constant:
        lines.append(f"constant columns (no variance): {constant}")

    numeric = df.select_dtypes(include="number")
    for col in numeric.columns:
        series = numeric[col].dropna()
        if series.empty:
            continue
        if (series < 0).any() and col.lower() in {"units_sold", "quantity", "count"}:
            examples = series[series < 0].head(max_examples).tolist()
            lines.append(f"suspicious negatives in '{col}': e.g. {examples}")

    return "\n".join(lines)
