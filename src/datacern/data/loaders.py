"""Document loaders for CSV and PDF files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from langchain_community.document_loaders import CSVLoader, PyPDFLoader
from langchain_core.documents import Document

from datacern.config import settings as config

SUPPORTED_EXTENSIONS = config.SUPPORTED_EXTENSIONS


def _load_csv(path: Path) -> tuple[list, pd.DataFrame | None]:
    """Load a CSV: returns LangChain Documents plus the raw DataFrame.

    Uses LangChain's CSVLoader for parsing, then merges the per-row documents
    into a single document so the number of chunks (and therefore embedding
    API calls) stays low — important on free-tier rate limits.
    """
    loader = CSVLoader(str(path), encoding="utf-8")
    row_documents = loader.load()
    combined = Document(
        page_content="\n".join(doc.page_content for doc in row_documents),
        metadata={"source": str(path)},
    )
    documents = [combined]
    dataframe = pd.read_csv(path)
    return documents, dataframe


def _load_pdf(path: Path) -> tuple[list, pd.DataFrame | None]:
    """Load a PDF: returns LangChain Documents (no DataFrame available)."""
    loader = PyPDFLoader(str(path))
    documents = loader.load()
    return documents, None


def load_file(file_path: str) -> dict:
    """Dispatch on file extension and load the file.

    Returns::

        {
            "documents": list[Document],
            "dataframe": pd.DataFrame | None,
            "filename":  str,
            "path":      str,
            "kind":      "csv" | "pdf",
        }
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > config.MAX_UPLOAD_MB:
        raise ValueError(f"file is {size_mb:.1f} MB, exceeding the {config.MAX_UPLOAD_MB} MB limit")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"unsupported file type '{ext}'. Use one of {sorted(SUPPORTED_EXTENSIONS)}"
        )

    if ext == ".csv":
        documents, dataframe = _load_csv(path)
        kind = "csv"
    else:
        documents, dataframe = _load_pdf(path)
        kind = "pdf"

    if not documents:
        raise ValueError(f"no text content could be extracted from {path.name}")

    return {
        "documents": documents,
        "dataframe": dataframe,
        "filename": path.name,
        "path": str(path),
        "kind": kind,
    }


def dataframe_summary(dataframe: pd.DataFrame | None) -> str:
    """Build a compact textual description of a DataFrame for the LLM."""
    if dataframe is None:
        return "No tabular data available (input was a PDF)."
    try:
        with pd.option_context("display.max_columns", None, "display.width", 200):
            info = f"shape: {dataframe.shape[0]} rows x {dataframe.shape[1]} columns\n"
            info += f"columns: {list(dataframe.columns)}\n"
            info += "dtypes:\n" + dataframe.dtypes.to_string() + "\n"
            info += "first 5 rows:\n" + dataframe.head(5).to_string()
            return info
    except Exception as exc:  # noqa: BLE001
        return f"DataFrame available but could not be summarised ({exc})."
