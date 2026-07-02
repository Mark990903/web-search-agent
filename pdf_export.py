from __future__ import annotations

import re
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from report_engine import ResearchReport


DEFAULT_PDF_NAME = "Research_Report.pdf"
FONT_NAME = "STSong-Light"


def export_report_to_pdf(
    report: ResearchReport | str,
    output_path: str | Path | None = None,
) -> bytes:
    markdown = report.to_markdown() if isinstance(report, ResearchReport) else report
    title = report.title if isinstance(report, ResearchReport) else "Research Report"
    return markdown_to_pdf(markdown, output_path=output_path, title=title)


def markdown_to_pdf(
    markdown: str,
    output_path: str | Path | None = None,
    title: str = "Research Report",
) -> bytes:
    register_fonts()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
    )
    styles = build_styles()
    story = build_story(markdown, styles)
    document.build(
        story,
        onFirstPage=draw_page_number,
        onLaterPages=draw_page_number,
    )
    pdf_bytes = buffer.getvalue()

    if output_path:
        Path(output_path).write_bytes(pdf_bytes)

    return pdf_bytes


def register_fonts() -> None:
    if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))


def build_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=sample["Title"],
            fontName=FONT_NAME,
            fontSize=22,
            leading=28,
            alignment=TA_CENTER,
            spaceAfter=16,
        ),
        "h2": ParagraphStyle(
            "ReportH2",
            parent=sample["Heading2"],
            fontName=FONT_NAME,
            fontSize=15,
            leading=20,
            spaceBefore=12,
            spaceAfter=8,
        ),
        "h3": ParagraphStyle(
            "ReportH3",
            parent=sample["Heading3"],
            fontName=FONT_NAME,
            fontSize=12,
            leading=16,
            spaceBefore=8,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=sample["BodyText"],
            fontName=FONT_NAME,
            fontSize=10.5,
            leading=15,
            alignment=TA_LEFT,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "ReportBullet",
            parent=sample["BodyText"],
            fontName=FONT_NAME,
            fontSize=10,
            leading=14,
            leftIndent=8,
        ),
        "footer": ParagraphStyle(
            "ReportFooter",
            parent=sample["BodyText"],
            fontName=FONT_NAME,
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
        ),
    }


def build_story(
    markdown: str,
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    story: list[Any] = []
    pending_list: list[str] = []

    def flush_list() -> None:
        nonlocal pending_list
        if not pending_list:
            return
        items = [
            ListItem(Paragraph(inline_markdown_to_text(item), styles["bullet"]))
            for item in pending_list
        ]
        story.append(ListFlowable(items, bulletType="bullet", leftIndent=12))
        story.append(Spacer(1, 4))
        pending_list = []

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            flush_list()
            story.append(Spacer(1, 4))
            continue

        if line == "\\pagebreak":
            flush_list()
            story.append(PageBreak())
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            flush_list()
            level = len(heading.group(1))
            text = inline_markdown_to_text(heading.group(2))
            if level == 1:
                story.append(Paragraph(text, styles["title"]))
            elif level == 2:
                story.append(Paragraph(text, styles["h2"]))
            else:
                story.append(Paragraph(text, styles["h3"]))
            continue

        bullet = re.match(r"^(?:[-*+]|\d+[\.\)])\s+(.*)$", line)
        if bullet:
            pending_list.append(bullet.group(1))
            continue

        flush_list()
        story.append(Paragraph(inline_markdown_to_text(line), styles["body"]))

    flush_list()
    return story


def inline_markdown_to_text(value: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", value)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return escape(text, quote=False).replace("&lt;b&gt;", "<b>").replace(
        "&lt;/b&gt;",
        "</b>",
    )


def draw_page_number(canvas: Any, document: SimpleDocTemplate) -> None:
    canvas.saveState()
    canvas.setFont(FONT_NAME, 9)
    page_number = f"Page {document.page}"
    canvas.drawCentredString(A4[0] / 2, 10 * mm, page_number)
    canvas.restoreState()
