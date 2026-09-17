"""Tests for deterministic preprocessing."""

import pandas as pd

from datacern.data.preprocessing import PreprocessOptions, preprocess_dataframe


def test_sanitize_and_trim():
    df = pd.DataFrame({" a ": ["  x ", " y"], "b": [1, 2]})
    cleaned, report = preprocess_dataframe(df, PreprocessOptions(trim_strings=True))
    assert list(cleaned.columns) == ["a", "b"]
    assert cleaned["a"].tolist() == ["x", "y"]
    assert "sanitize_columns" in report["applied"][0]


def test_coerce_numeric_and_missing_fill():
    df = pd.DataFrame({"n": ["1", "2", None], "s": ["a", None, "c"]})
    opts = PreprocessOptions(missing_strategy="keep")
    cleaned, _ = preprocess_dataframe(df, opts)
    # numeric coercion should parse n
    assert pd.api.types.is_numeric_dtype(cleaned["n"])
    # fill median
    opts2 = PreprocessOptions(missing_per_column={"n": "fill_median"})
    cleaned2, report = preprocess_dataframe(df, opts2)
    assert cleaned2["n"].isna().sum() == 0
    assert any("fill_median" in a for a in report["applied"])


def test_drop_duplicates_and_constant():
    df = pd.DataFrame({"a": [1, 1, 2], "const": [5, 5, 5]})
    opts = PreprocessOptions(drop_duplicates=True, drop_constant=True)
    cleaned, report = preprocess_dataframe(df, opts)
    assert len(cleaned) == 2  # one duplicate removed
    assert "const" not in cleaned.columns
    assert any("drop_duplicates" in a for a in report["applied"])
    assert any("drop_constant" in a for a in report["applied"])


def test_no_op_keeps_shape():
    df = pd.DataFrame({"x": [1, 2], "y": ["a", "b"]})
    cleaned, report = preprocess_dataframe(df, PreprocessOptions())
    assert cleaned.shape == df.shape
    assert report["before_shape"] == [2, 2]
    assert report["after_shape"] == [2, 2]


def test_empty_none_passthrough():
    cleaned, report = preprocess_dataframe(None, None)
    assert cleaned is None
    assert "skipping" in report["notes"][0]
