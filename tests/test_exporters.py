"""Exporter tests: build a tiny chart PNG and render PDF/PPTX (no API)."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from datacern.reports.exporters import export_pdf, export_pptx


def _chart(tmp_path) -> str:
    fig, ax = plt.subplots()
    ax.bar(["A", "B"], [1, 2])
    target = tmp_path / "chart.png"
    fig.savefig(target, format="png")
    plt.close(fig)
    return str(target)


def test_export_pdf(tmp_path):
    chart = _chart(tmp_path)
    out = Path(export_pdf("# Title\n\nBody text here.", [chart], tmp_path / "out.pdf"))
    assert out.stat().st_size > 1_000


def test_export_pptx(tmp_path):
    chart = _chart(tmp_path)
    out = Path(export_pptx("## Heading\n\n- one\n- two", [chart], tmp_path / "out.pptx"))
    assert out.stat().st_size > 1_000
