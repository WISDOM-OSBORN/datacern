"""Multi-format exporters: styled PDF and PPTX from a generated report."""

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


def _register_dejavu() -> dict[str, str]:
    """Register DejaVu Sans if available; fall back to Helvetica."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # Common linux paths (Docker: fonts-dejavu-core)
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
        ]
        # Windows fallback: use Helvetica if files missing
        import os

        base = "/usr/share/fonts/truetype/dejavu"
        if os.path.exists(f"{base}/DejaVuSans.ttf"):
            pdfmetrics.registerFont(TTFont("DejaVu", f"{base}/DejaVuSans.ttf"))
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", f"{base}/DejaVuSans-Bold.ttf"))
            pdfmetrics.registerFont(TTFont("DejaVu-Oblique", f"{base}/DejaVuSans-Oblique.ttf"))
            pdfmetrics.registerFont(
                TTFont("DejaVu-BoldOblique", f"{base}/DejaVuSans-BoldOblique.ttf")
            )
            pdfmetrics.registerFontFamily(
                "DejaVu",
                normal="DejaVu",
                bold="DejaVu-Bold",
                italic="DejaVu-Oblique",
                boldItalic="DejaVu-BoldOblique",
            )
            return {"normal": "DejaVu", "bold": "DejaVu-Bold", "italic": "DejaVu-Oblique"}
        # Try Windows DejaVu if present
        for p in candidates:
            if os.path.exists(p):
                # generic fallback already handled
                pass
    except Exception:
        pass
    return {"normal": "Helvetica", "bold": "Helvetica-Bold", "italic": "Helvetica-Oblique"}


def _header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColorRGB(0.55, 0.58, 0.66)
    canvas.drawString(1.5 * 2.54 * 28.35 / 72, 28, "DataCern — evidence-grounded reports")
    canvas.drawRightString(doc.pagesize[0] - 1.5 * 2.54 * 28.35 / 72, 28, f"Page {doc.page}")
    canvas.restoreState()


def export_pdf(
    report_md: str,
    chart_paths: list[str],
    target: Path,
    title: str = "DataCern Report",
    captions: list[str] | None = None,
) -> str:
    """Render a styled PDF with DejaVu Sans. Short captions per Figure."""
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image as RLImage
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    fonts = _register_dejavu()
    styles = getSampleStyleSheet()
    # Brand palette
    ink = HexColor("#1a1a2e")
    muted = HexColor("#4a5568")
    accent = HexColor("#2563eb")

    title_style = ParagraphStyle(
        "TitleDejaVu",
        parent=styles["Title"],
        fontName=fonts["bold"],
        fontSize=22,
        leading=26,
        textColor=ink,
        spaceAfter=6,
    )
    h2 = ParagraphStyle(
        "H2DejaVu",
        parent=styles["Heading2"],
        fontName=fonts["bold"],
        fontSize=13,
        leading=16,
        textColor=accent,
        spaceBefore=10,
        spaceAfter=6,
    )
    h3 = ParagraphStyle(
        "H3DejaVu",
        parent=styles["Heading3"],
        fontName=fonts["bold"],
        fontSize=11,
        leading=14,
        textColor=ink,
        spaceBefore=8,
        spaceAfter=4,
    )
    body = ParagraphStyle(
        "BodyDejaVu",
        parent=styles["BodyText"],
        fontName=fonts["normal"],
        fontSize=9.5,
        leading=14,
        textColor=muted,
        spaceAfter=4,
        alignment=4,  # justify
    )
    bullet_style = ParagraphStyle(
        "BulletDejaVu",
        parent=body,
        leftIndent=12,
        bulletIndent=6,
        spaceAfter=2,
    )
    caption_style = ParagraphStyle(
        "CaptionDejaVu",
        parent=styles["Normal"],
        fontName=fonts["italic"],
        fontSize=8,
        leading=10,
        textColor=HexColor("#718096"),
        alignment=1,
    )

    story = [Paragraph(_strip_markdown(title), title_style), Spacer(1, 0.4 * cm)]
    # Decorative line
    from reportlab.platypus import HRFlowable

    story.append(HRFlowable(width="100%", thickness=1, color=accent, spaceAfter=8, spaceBefore=4))

    for block in report_md.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("### "):
            story.append(Paragraph(_strip_markdown(block), h3))
        elif block.startswith("## "):
            story.append(Paragraph(_strip_markdown(block), h2))
        elif block.startswith("# "):
            story.append(Paragraph(_strip_markdown(block), h2))
        else:
            for para in block.split("\n"):
                para = para.strip()
                if not para:
                    continue
                is_bullet = para.startswith("• ")
                style = bullet_style if is_bullet else body
                # wrap bullet char
                story.append(Paragraph(_strip_markdown(para), style))
        story.append(Spacer(1, 0.2 * cm))

    captions = captions or [f"Figure {i}" for i in range(1, len(chart_paths) + 1)]
    for i, chart in enumerate(chart_paths, 1):
        cap = captions[i - 1] if i - 1 < len(captions) else f"Figure {i}"
        story.append(PageBreak())
        story.append(Paragraph(f"Figure {i} — {_strip_markdown(cap)[:140]}", caption_style))
        story.append(Spacer(1, 0.15 * cm))
        # short insight line under caption
        if " — " in cap:
            insight = cap.split(" — ", 1)[1].strip()
            if insight:
                story.append(Paragraph(_strip_markdown(insight)[:200], body))
                story.append(Spacer(1, 0.15 * cm))
        story.append(RLImage(chart, width=16 * cm, height=9 * cm, kind="proportional"))

    target.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=title,
        author="DataCern",
    )
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return str(target)


def export_pptx(
    report_md: str,
    chart_paths: list[str],
    target: Path,
    title: str = "DataCern Report",
    captions: list[str] | None = None,
) -> str:
    """Render a clean professional PPTX: title per chart + short caption."""
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

    captions = captions or [f"Figure {i}" for i in range(1, len(chart_paths) + 1)]
    for i, chart in enumerate(chart_paths, 1):
        cap = captions[i - 1] if i - 1 < len(captions) else f"Figure {i}"
        # clean slide: title = short caption title, caption textbox below image
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        title_text = cap.split(" — ")[0][:60] if " — " in cap else cap[:60]
        # title box
        txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(12.33), Inches(0.5))
        tf = txBox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = f"Figure {i}: {title_text}"
        p.runs[0].font.size = Inches(0.18)
        p.runs[0].font.bold = True
        slide.shapes.add_picture(
            chart, Inches(0.5), Inches(0.7), width=Inches(12.33), height=Inches(5.5)
        )
        # short insight below image (max 22 words, not wordy)
        insight = cap.split(" — ", 1)[1].strip() if " — " in cap else ""
        if insight:
            capBox = slide.shapes.add_textbox(Inches(0.5), Inches(6.4), Inches(12.33), Inches(0.7))
            ctf = capBox.text_frame
            ctf.word_wrap = True
            cp = ctf.paragraphs[0]
            cp.text = insight[:180]
            cp.runs[0].font.size = Inches(0.12)
            cp.runs[0].font.italic = True

    target.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(target))
    return str(target)
