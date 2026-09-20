"""Chart planning: rule-based + intelligence for up to 6 visuals.

Ranked suggestions combine column profiling, keyword intent, and
diversity so the LLM produces complementary charts (not 6 histograms).
User selections override the auto-ranked list.
"""

from __future__ import annotations

import pandas as pd

CHART_CATALOG: dict[str, str] = {
    "time_series": "Time series: line chart of a numeric over a date (monthly avg if noisy)",
    "grouped_bar": "Grouped comparison: total numeric by categorical (sorted bar)",
    "distribution": "Distribution: histogram / box plot of numeric by categorical",
    "scatter": "Relationship: scatter of two numerics (with trend)",
    "correlation": "Correlation: heatmap of numeric correlations",
    "treemap": "Composition: treemap/pie of categorical share (top categories)",
}


def _catalog_options(df: pd.DataFrame | None) -> list[str]:
    if df is None or df.empty:
        return []
    numeric = df.select_dtypes(include="number").columns.tolist()
    from datacern.data.profiling import categorical_columns

    cats = [c for c in categorical_columns(df) if 1 < df[c].nunique() <= 30]
    dates = [c for c in df.columns if "date" in c.lower()]
    opts: list[str] = []
    if dates and numeric:
        opts.append("time_series")
    if cats and numeric:
        opts.append("grouped_bar")
        opts.append("distribution")
    if len(numeric) >= 2:
        opts.extend(["scatter", "correlation"])
    if cats:
        opts.append("treemap")
    # dedupe, keep order
    seen: list[str] = []
    for o in opts:
        if o not in seen:
            seen.append(o)
    return seen


def plan_charts(
    df: pd.DataFrame | None,
    query: str,
    selected: list[str] | None = None,
    max_charts: int = 6,
) -> str:
    """Recommend chart types. ``selected`` overrides auto ranking."""
    if df is None or df.empty:
        return "No tabular data: do not attempt charts."

    max_charts = max(1, min(6, max_charts))

    if selected:
        # validate and map to descriptions
        sel = [s for s in selected if s in CHART_CATALOG]
        if sel:
            lines = [f"{i + 1}. {CHART_CATALOG[s]} ({s})" for i, s in enumerate(sel[:max_charts])]
            return "USER-SELECTED CHART PLAN (follow exactly, one chart per item):\n" + "\n".join(
                lines
            )

    numeric = df.select_dtypes(include="number").columns.tolist()
    from datacern.data.profiling import categorical_columns

    cats = [c for c in categorical_columns(df) if 1 < df[c].nunique() <= 30]
    dates = [c for c in df.columns if "date" in c.lower()]
    q = query.lower()

    suggestions: list[str] = []
    # 1 time series if date present
    if dates and numeric:
        suggestions.append(
            f"1. Time series: plot {numeric[0]} over {dates[0]} (line, resample monthly mean if >30 points)"  # noqa: E501
        )
    # 2 grouped bar (sorted) — strongest intent signal
    if cats and numeric:
        top_cat, top_num = cats[0], numeric[0]
        # pick cat with strongest variance for second chart
        second_cat = cats[1] if len(cats) > 1 else top_cat
        if any(
            w in q for w in ("compar", "region", "product", "category", "top", "bottom", "rank")
        ):
            suggestions.append(
                f"2. Grouped comparison: total {top_num} by {top_cat} (sorted bar, annotate values)"
            )
            if len(cats) > 1 and len(suggestions) < max_charts:
                suggestions.append(
                    f"3. Second comparison: total {top_num} by {second_cat} (bar, sorted)"
                )
        else:
            suggestions.append(f"2. Distribution: {top_num} across {top_cat} (bar or box)")
    # correlation heatmap for numerics
    if len(numeric) >= 3 and len(suggestions) < max_charts:
        suggestions.append(
            f"{len(suggestions) + 1}. Correlation: heatmap of {', '.join(numeric[:4])}"
        )
    # scatter for relationship
    if len(numeric) >= 2 and len(suggestions) < max_charts:
        suggestions.append(
            f"{len(suggestions) + 1}. Relationship: {numeric[0]} vs {numeric[1]} (scatter + trend)"
        )
    # treemap/composition
    if cats and len(suggestions) < max_charts:
        suggestions.append(
            f"{len(suggestions) + 1}. Composition: share of {cats[0]} (treemap/pie, top 8)"
        )
    # fallback histogram
    if not suggestions and numeric:
        suggestions.append(f"1. Overview: distribution of {numeric[0]} (histogram with KDE)")

    # diversity + cap
    dedup: list[str] = []
    seen_keys: set[str] = set()
    for s in suggestions:
        key = s.split(":")[0]
        if key not in seen_keys:
            seen_keys.add(key)
            dedup.append(s)
        if len(dedup) >= max_charts:
            break

    plan = "\n".join(dedup[:max_charts])
    return f"SMART CHART PLAN (follow; produce {len(dedup[:max_charts])} diverse charts):\n{plan}"


def available_chart_options(df: pd.DataFrame | None) -> list[str]:
    """Return catalog keys feasible for this dataframe."""
    return _catalog_options(df)