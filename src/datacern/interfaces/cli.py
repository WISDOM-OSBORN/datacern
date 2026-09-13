"""Command-line entry point for DataCern.

Usage:
    datacern --file examples/data/sales_data.csv --query "What were the top regions?"
    datacern --file data/report.pdf --query "Summarise this document" --pdf --pptx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from datacern import __version__
from datacern.config.settings import EXEC_TIMEOUT
from datacern.reports.generator import ReportGenerator


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="datacern",
        description="Generate evidence-grounded reports from CSV/PDF with RAG + charts.",
    )
    parser.add_argument("--file", required=True, help="Path to the input CSV or PDF file.")
    parser.add_argument(
        "--query",
        default="Provide a comprehensive summary and key insights of the data.",
        help="User request the report should answer.",
    )
    parser.add_argument("--pdf", action="store_true", help="Also export a styled PDF.")
    parser.add_argument("--pptx", action="store_true", help="Also export a PPTX deck.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    try:
        generator = ReportGenerator()
        result = generator.generate(
            args.file,
            args.query,
            original_filename=Path(args.file).name,
            export_pdf_=args.pdf,
            export_pptx_=args.pptx,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print("=" * 72)
    print(f"DATACERN REPORT GENERATED (run {result['run_id']})")
    print("=" * 72)
    print(result["report"])
    if result["charts"]:
        print("\n[CHARTS SAVED]")
        for chart in result["charts"]:
            print(f"  {chart}")
    else:
        print("\n[NO CHARTS PRODUCED]")
    if result.get("warnings"):
        print("\n[WARNINGS]")
        for warning in result["warnings"]:
            print(f"  - {warning}")
    print(f"\n[REPORT SAVED] {result['outputs']['report_path']}")
    for key in ("pdf_path", "pptx_path"):
        if result["outputs"].get(key):
            print(f"[{'PDF' if key == 'pdf_path' else 'PPTX'} SAVED] {result['outputs'][key]}")
    print(f"[LEDGER] {result['ledger_path']}")
    usage = result.get("usage", {})
    print(
        f"[USAGE] provider={result.get('embedding_provider')} "
        f"llm_seconds={usage.get('total_seconds_llm', 0)} "
        f"est_cost_usd={usage.get('estimated_cost_usd', 0)}"
    )
    if result.get("exec_detail"):
        d = result["exec_detail"]
        print(
            f"[CHART EXEC] success={d.get('success')} images={len(d.get('images') or [])} "
            f"elapsed={d.get('elapsed', 0):.2f}s (timeout={EXEC_TIMEOUT}s)"
        )
        if d.get("error"):
            print(f"[CHART EXEC ERROR] {d['error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
