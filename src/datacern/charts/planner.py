"""Chart planning: rule-based chart-type recommendations.

Produces a short textual plan embedded in the chart-code prompt so the LLM
picks chart types suited to the data shape and the user's question, instead
of guessing blindly.
"""

from __future__ import annotations

import pandas as pd


def plan_charts(df: pd.DataFrame | None, query: str) -> str:
    """Recommend chart types based on columns and query keywords."""
    if df is None or df.empty:
        return "No tabular data: do not attempt charts."

    numeric = df.select_dtypes(include="number").columns.tolist()
    from datacern.data.profiling import categorical_columns

    cats = [c for c in categorical_columns(df) if 1 < df[c].nunique() <= 30]
    dates = [c for c in df.columns if "date" in c.lower()]
    q = query.lower()

    suggestions = []
    if dates and numeric:
        suggestions.append(
            f"1. Time series: plot {numeric[0]} over {dates[0]} "
            "(line chart, aggregate by month if noisy)."
        )
    if cats and numeric:
        top_cat, top_num = cats[0], numeric[0]
        if any(
            w in q for w in ("compar", "region", "product", "category", "top", "bottom", "rank")
        ):
            suggestions.append(
                f"2. Grouped comparison: total {top_num} by {top_cat} "
                "(bar chart, sorted descending)."
            )
        else:
            suggestions.append(f"2. Distribution: {top_num} across {top_cat} (bar or box plot).")
    if len(numeric) >= 2:
        suggestions.append(f"3. Relationship: {numeric[0]} vs {numeric[1]} (scatter plot).")
    if not suggestions and numeric:
        suggestions.append(f"1. Overview: distribution of {numeric[0]} (histogram).")

    plan = (
        "\n".join(suggestions[:3])
        if suggestions
        else "1. Overview histogram of the main numeric column."
    )
    return f"RECOMMENDED CHART PLAN (follow this unless the query demands otherwise):\n{plan}"
