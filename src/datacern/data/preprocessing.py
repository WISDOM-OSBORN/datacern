"""Deterministic preprocessing for tabular inputs.

Validation + opt-in cleaning with full lineage. Never mutates silently:
callers pass explicit options and receive ``(cleaned_df, report)`` where
``report`` is JSON-serialisable and suitable for prompts / ``run.json``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class PreprocessOptions:
    """User-controlled cleaning choices (all opt-in, safe defaults)."""

    # duplicates
    drop_duplicates: bool = False
    # missing: keep|drop_rows|fill_median|fill_mean|fill_mode|fill_zero|fill_forward
    missing_strategy: str = "keep"  # global fallback when per-column not set
    missing_per_column: dict[str, str] = field(default_factory=dict)
    # type coercion
    coerce_numeric: bool = True
    coerce_dates: bool = True
    # constant columns
    drop_constant: bool = False
    # trimming of string columns
    trim_strings: bool = True


def _sanitize_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Strip whitespace, deduplicate names, return notes."""
    notes: list[str] = []
    original = list(df.columns)
    cleaned = [str(c).strip() for c in original]
    # deduplicate: same sanitized name -> suffix _2, _3
    seen: dict[str, int] = {}
    deduped: list[str] = []
    for col in cleaned:
        if col not in seen:
            seen[col] = 1
            deduped.append(col)
        else:
            seen[col] += 1
            new = f"{col}_{seen[col]}"
            deduped.append(new)
            notes.append(f"column '{col}' duplicated -> renamed to '{new}'")
    if deduped != original:
        df = df.copy()
        df.columns = deduped
        notes.append(f"columns sanitized: {original} -> {deduped}")
    return df, notes


def _coerce_types(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    notes: list[str] = []
    df = df.copy()
    for col in df.columns:
        s = df[col]
        if s.dtype == object or pd.api.types.is_string_dtype(s.dtype):
            # try numeric coercion
            coerced = pd.to_numeric(s, errors="coerce")
            # only accept if at least 70% parse and at least one numeric
            non_null = s.notna().sum()
            parsed = coerced.notna().sum()
            if non_null > 0 and parsed / max(non_null, 1) >= 0.7 and parsed > 0:
                df[col] = coerced
                notes.append(f"coerced '{col}' to numeric ({parsed}/{non_null} parsed)")
                continue
            # try datetime
            try:
                dt = pd.to_datetime(s, errors="coerce")
                parsed_dt = dt.notna().sum()
                if non_null > 0 and parsed_dt / max(non_null, 1) >= 0.7:
                    df[col] = dt
                    notes.append(f"coerced '{col}' to datetime ({parsed_dt}/{non_null} parsed)")
            except Exception:
                pass
    return df, notes


def preprocess_dataframe(
    df: pd.DataFrame | None,
    options: PreprocessOptions | None = None,
) -> tuple[pd.DataFrame | None, dict]:
    """Apply opt-in cleaning and return ``(cleaned_df, report)``.

    ``report`` contains ``applied: list[str]`` and per-column stats so
    callers can inject lineage into prompts and ``run.json``.
    """
    if df is None or df.empty:
        return df, {"applied": [], "notes": ["no tabular data or empty — skipping preprocessing"]}

    if options is None:
        options = PreprocessOptions()

    report: dict = {"applied": [], "notes": [], "before_shape": list(df.shape), "per_column": {}}
    # capture before stats for lineage
    before_missing = df.isna().sum().to_dict()
    before_dupes = int(df.duplicated().sum())

    # 1 column sanitization (always)
    df, notes = _sanitize_columns(df)
    report["notes"].extend(notes)
    if notes:
        report["applied"].append("sanitize_columns")

    # 2 trim strings
    if options.trim_strings:
        obj_cols = df.select_dtypes(include=["object"]).columns.tolist()
        trimmed = 0
        for col in obj_cols:
            before = df[col].astype(str)
            after = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
            if not before.equals(after):
                trimmed += 1
        if trimmed:
            df = df.copy()
            for col in obj_cols:
                df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
            report["applied"].append(f"trim_strings ({trimmed} cols)")
            report["notes"].append(f"trimmed whitespace in {trimmed} string columns")

    # 3 type coercion
    if options.coerce_numeric or options.coerce_dates:
        df, coerce_notes = _coerce_types(df)
        report["notes"].extend(coerce_notes)
        if coerce_notes:
            report["applied"].append("coerce_types")

    # 4 constant columns
    if options.drop_constant:
        constant = [c for c in df.columns if df[c].nunique(dropna=False) <= 1]
        if constant:
            df = df.drop(columns=constant)
            report["applied"].append(f"drop_constant {constant}")
            report["notes"].append(f"dropped constant columns: {constant}")

    # 5 missing handling
    strategy = options.missing_strategy
    per_col = options.missing_per_column or {}
    # normalize alias
    alias = {"drop": "drop_rows", "median": "fill_median", "mean": "fill_mean", "mode": "fill_mode"}
    strategy = alias.get(strategy, strategy)
    per_col = {k: alias.get(v, v) for k, v in per_col.items()}

    if strategy != "keep" or per_col:
        # global drop_rows
        if strategy == "drop_rows" and not per_col:
            before = len(df)
            df = df.dropna()
            report["applied"].append(f"drop_rows (global): {before} -> {len(df)}")
        else:
            for col in df.columns:
                col_strategy = per_col.get(col, strategy)
                if col_strategy == "keep" or col_strategy == "drop_rows" and col not in per_col:
                    continue
                if col_strategy == "drop_rows":
                    before = len(df)
                    df = df.dropna(subset=[col])
                    report["applied"].append(f"drop_rows '{col}': {before}->{len(df)}")
                elif col_strategy == "fill_median" and pd.api.types.is_numeric_dtype(df[col]):
                    fill = df[col].median()
                    df[col] = df[col].fillna(fill)
                    report["applied"].append(f"fill_median '{col}'={fill}")
                elif col_strategy == "fill_mean" and pd.api.types.is_numeric_dtype(df[col]):
                    fill = df[col].mean()
                    df[col] = df[col].fillna(fill)
                    report["applied"].append(f"fill_mean '{col}'={fill:.4g}")
                elif col_strategy == "fill_mode":
                    mode = df[col].mode(dropna=True)
                    if not mode.empty:
                        fill = mode.iloc[0]
                        df[col] = df[col].fillna(fill)
                        report["applied"].append(f"fill_mode '{col}'={fill!r}")
                elif col_strategy == "fill_zero":
                    df[col] = df[col].fillna(0)
                    report["applied"].append(f"fill_zero '{col}'")
                elif col_strategy == "fill_forward":
                    df[col] = df[col].ffill().bfill()
                    report["applied"].append(f"fill_forward '{col}'")

    # 6 duplicates
    if options.drop_duplicates:
        before = len(df)
        df = df.drop_duplicates()
        if len(df) != before:
            report["applied"].append(
                f"drop_duplicates: {before}->{len(df)} (removed {before - len(df)})"
            )
            report["notes"].append(
                f"removed {before - len(df)} dupes (was {before_dupes} before)"
            )

    # final stats
    after_missing = df.isna().sum().to_dict() if df is not None else {}
    report["after_shape"] = list(df.shape) if df is not None else []
    report["before_missing"] = {k: int(v) for k, v in before_missing.items()}
    report["after_missing"] = {k: int(v) for k, v in after_missing.items()}
    # per column lineage
    for col in df.columns if df is not None else []:
        report["per_column"][col] = {
            "before_missing": int(before_missing.get(col, 0)),
            "after_missing": int(after_missing.get(col, 0)),
        }
    # human summary line for prompts
    if report["applied"]:
        report["summary"] = (
            f"Preprocessing: {'; '.join(report['applied'])}. "
            f"Shape {report['before_shape']}->{report['after_shape']}."
        )
    else:
        report["summary"] = (
            f"No cleaning applied (conservative defaults). Shape {report['before_shape']}."
        )

    # sanitize string values that may exceed JSON limits
    report["summary"] = report["summary"][:800]

    return df, report


def format_preprocessing_report(report: dict) -> str:
    """One-line + bullet text for LLM prompts."""
    lines = [report.get("summary", "")]
    if report.get("notes"):
        lines.append("Notes: " + "; ".join(report["notes"][:6]))
    return "\n".join(line for line in lines if line)
