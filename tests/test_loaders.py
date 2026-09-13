"""Loader tests against the bundled sample dataset (no API calls)."""

from pathlib import Path

import pytest

from datacern.data.loaders import dataframe_summary, load_file

SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "data" / "sales_data.csv"


def test_load_csv_returns_docs_and_dataframe():
    loaded = load_file(str(SAMPLE))
    assert loaded["kind"] == "csv"
    assert loaded["filename"] == "sales_data.csv"
    assert len(loaded["documents"]) >= 1
    assert loaded["dataframe"] is not None
    assert loaded["dataframe"].shape[1] == 10


def test_dataframe_summary_mentions_columns():
    loaded = load_file(str(SAMPLE))
    summary = dataframe_summary(loaded["dataframe"])
    assert "rows x" in summary
    assert "revenue" in summary


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_file("does_not_exist.csv")


def test_unsupported_extension_raises(tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        load_file(str(target))


def test_pdf_summary_without_dataframe():
    assert "PDF" in dataframe_summary(None)
