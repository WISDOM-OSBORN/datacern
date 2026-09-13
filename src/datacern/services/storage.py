"""Run-scoped output storage.

Every generation gets a unique run directory::

    var/outputs/<run_id>/
        report.md
        charts/chart_1.png ...
        report.pdf (optional)
        report.pptx (optional)
        run.json (ledger)

Output filenames preserve the original upload name plus the run id, so
uploads with random temp names never leak into user-visible artifacts.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from datacern.config import settings as config


def sanitize_stem(name: str) -> str:
    """Make a filesystem-safe stem from an original filename."""
    stem = Path(name).stem
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "report"
    return stem[:48]


class RunStore:
    """Filesystem layout for a single generation run."""

    def __init__(self, run_id: str, original_filename: str):
        self.run_id = run_id
        self.stem = sanitize_stem(original_filename)
        self.root = config.OUTPUT_PATH / run_id
        self.chart_dir = self.root / "charts"
        self.root.mkdir(parents=True, exist_ok=True)
        self.chart_dir.mkdir(parents=True, exist_ok=True)

    @property
    def report_path(self) -> Path:
        return self.root / f"{self.stem}_{self.run_id}_report.md"

    def chart_path(self, index: int) -> Path:
        return self.chart_dir / f"{self.stem}_{self.run_id}_chart_{index}.png"

    def save_images(self, images: list[bytes]) -> list[str]:
        paths = []
        for i, data in enumerate(images, start=1):
            target = self.chart_path(i)
            target.write_bytes(data)
            paths.append(str(target))
        return paths

    def save_report(self, report_md: str) -> str:
        self.report_path.write_text(report_md, encoding="utf-8")
        return str(self.report_path)

    def save_ledger(self, ledger: dict) -> str:
        ledger = {
            **ledger,
            "run_id": self.run_id,
            "original_filename": self.stem,
            "finished_at": datetime.now(UTC).isoformat(),
        }
        target = self.root / "run.json"
        target.write_text(json.dumps(ledger, indent=2, default=str), encoding="utf-8")
        return str(target)
