"""Validation of chart execution results."""

from __future__ import annotations

MIN_IMAGE_BYTES = 5_000
MAX_IMAGES = 6


def validate_execution(exec_detail: dict | None, *, want_images: bool = True) -> list[str]:
    """Return a list of human-readable warnings (empty = looks good)."""
    warnings: list[str] = []
    if not exec_detail:
        return ["no chart execution was attempted"] if want_images else []
    if not exec_detail.get("success"):
        return [f"chart execution failed: {exec_detail.get('error', 'unknown error')}"]
    images = exec_detail.get("images") or []
    if want_images and not images:
        warnings.append("chart code ran but produced no figures")
    if len(images) > MAX_IMAGES:
        warnings.append(f"unusually many figures ({len(images)}); expected <= {MAX_IMAGES}")
    for i, png in enumerate(images, start=1):
        if len(png) < MIN_IMAGE_BYTES:
            warnings.append(f"chart {i} is suspiciously small ({len(png)} bytes)")
    return warnings
