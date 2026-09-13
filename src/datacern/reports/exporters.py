"""Multi-format exporters: styled PDF and PPTX from a generated report.

Converts the Markdown report text plus chart PNGs into shareable artifacts.
"""

from __future__ import annotations

import re
from pathlib import Path


def _strip_markdown(text: str) -> str:
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.MULTILINE)
    return text.strip()


def export_pdf(
    report_md: str, chart_paths: list[str], target: Path, title: str = "DataCern Report"
) -> str:
    """Render a styled PDF. Returns the saved path. Requires ``reportlab``."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image as RLImage
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 0.5 * cm)]

    for block in report_md.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("#"):
            story.append(Paragraph(_strip_markdown(block), styles["Heading2"]))
        else:
            for para in block.split("\n"):
                para = para.strip()
                if para:
                    story.append(Paragraph(_strip_markdown(para), styles["BodyText"]))
        story.append(Spacer(1, 0.3 * cm))

    for chart in chart_paths:
        story.append(PageBreak())
        story.append(RLImage(chart, width=16 * cm, height=9 * cm, kind="proportional"))

    target.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(target), pagesize=A4).build(story)
    return str(target)


def export_pptx(
    report_md: str, chart_paths: list[str], target: Path, title: str = "DataCern Report"
) -> str:
    """Render a PPTX deck. Returns the saved path. Requires ``python-pptx``."""
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.33), Inches(7.5)

    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    title_slide.shapes.title.text = title

    sections: list[tuple[str, list[str]]] = []
    current = ("Overview", [])
    for line in report_md.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            sections.append(current)
            current = (stripped[3:].strip(), [])
        elif stripped:
            current[1].append(_strip_markdown(stripped))
    sections.append(current)

    for heading, bullets in sections[:8]:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = heading[:80]
        body = slide.placeholders[1].text_frame
        body.text = ""
        for bullet in bullets[:8]:
            body.add_paragraph().text = bullet[:300]

    for chart in chart_paths:
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        slide.shapes.add_picture(chart, Inches(0.5), Inches(0.5), width=Inches(12.33))

    target.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(target))
    return str(target)
