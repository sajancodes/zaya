"""Document & Presentation Generation.
Created and developed by Sajan Rai for Zaya.
Autonomously generate PowerPoint presentations (.pptx), Excel spreadsheets (.xlsx), and PDF reports.
"""
from __future__ import annotations

import json
import re
import sys
import io
from xml.sax.saxutils import escape
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner
from core.artifact_paths import save_artifact, sheet_title


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _get_output_dir() -> Path:
    desktop = Path.home() / "Desktop"
    if desktop.exists():
        return desktop
    out = get_base_dir() / "output"
    out.mkdir(parents=True, exist_ok=True)
    return out


def create_powerpoint(
    title: str,
    slides_data: List[Dict[str, str]],
    out_path: Optional[Path] = None
) -> str:
    """Generates a styled PowerPoint presentation using python-pptx."""
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[6]

    # Slide 1: Title Slide (Dark luxury blue theme)
    slide1 = prs.slides.add_slide(blank_layout)
    bg1 = slide1.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
    bg1.fill.solid()
    bg1.fill.fore_color.rgb = RGBColor(11, 15, 25)
    bg1.line.color.rgb = RGBColor(11, 15, 25)

    txBox = slide1.shapes.add_textbox(Inches(1.5), Inches(2.2), Inches(10.3), Inches(3.0))
    tf = txBox.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = title
    p.font.name = "Segoe UI"
    p.font.size = Pt(44)
    p.font.bold = True
    p.font.color.rgb = RGBColor(255, 255, 255)
    p.alignment = PP_ALIGN.LEFT

    p2 = tf.add_paragraph()
    p2.text = "Prepared by Zaya AI Assistant"
    p2.font.name = "Segoe UI"
    p2.font.size = Pt(20)
    p2.font.color.rgb = RGBColor(56, 189, 248)
    p2.space_before = Pt(14)

    # Content Slides
    for slide_info in slides_data:
        s = prs.slides.add_slide(blank_layout)
        bg = s.shapes.add_shape(1, 0, 0, prs.slide_width, prs.slide_height)
        bg.fill.solid()
        bg.fill.fore_color.rgb = RGBColor(248, 250, 252)
        bg.line.color.rgb = RGBColor(248, 250, 252)

        # Header bar
        header_box = s.shapes.add_textbox(Inches(1.0), Inches(0.8), Inches(11.3), Inches(1.2))
        htf = header_box.text_frame
        hp = htf.paragraphs[0]
        hp.text = slide_info.get("title", "Key Point")
        hp.font.name = "Segoe UI"
        hp.font.size = Pt(30)
        hp.font.bold = True
        hp.font.color.rgb = RGBColor(15, 23, 42)

        # Body card
        card = s.shapes.add_shape(1, Inches(1.0), Inches(2.0), Inches(11.3), Inches(4.5))
        card.fill.solid()
        card.fill.fore_color.rgb = RGBColor(255, 255, 255)
        card.line.color.rgb = RGBColor(226, 232, 240)

        ctf = card.text_frame
        ctf.word_wrap = True
        ctf.margin_left = Inches(0.4)
        ctf.margin_top = Inches(0.4)

        cp = ctf.paragraphs[0]
        content_text = slide_info.get("content", "")
        lines = content_text.splitlines() if isinstance(content_text, str) else [str(content_text)]
        for i, line in enumerate(lines):
            target_p = cp if i == 0 else ctf.add_paragraph()
            target_p.text = line.strip()
            target_p.font.name = "Segoe UI"
            target_p.font.size = Pt(18)
            target_p.font.color.rgb = RGBColor(51, 65, 85)
            target_p.space_before = Pt(8)

    if not out_path:
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", title.lower())[:35]
        out_path = _get_output_dir() / f"{slug}.pptx"

    return str(save_artifact(lambda path: prs.save(str(path)), out_path))


def create_excel_sheet(
    title: str,
    headers: List[str],
    rows: List[List[Any]],
    out_path: Optional[Path] = None
) -> str:
    """Generates an Excel workbook using openpyxl."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title(title)

    # Header styling
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    ws.append(headers)
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # Add data rows
    for row in rows:
        ws.append(row)

    # Style data rows and auto-adjust column width
    for row_num in range(2, len(rows) + 2):
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=row_num, column=col_num)
            cell.border = thin_border

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    if not out_path:
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", title.lower())[:35]
        out_path = _get_output_dir() / f"{slug}.xlsx"

    return str(save_artifact(lambda path: wb.save(str(path)), out_path))


def create_pdf_document(
    title: str,
    sections: List[Dict[str, str]],
    out_path: Optional[Path] = None
) -> str:
    """Generates a clean PDF document using ReportLab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

    if not out_path:
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", title.lower())[:35]
        out_path = _get_output_dir() / f"{slug}.pdf"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#0F172A')
    )
    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#2563EB')
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        textColor=colors.HexColor('#334155')
    )

    story = [
        Paragraph(escape(str(title)), title_style),
        Spacer(1, 12),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=18)
    ]

    for sec in sections:
        sec_title = sec.get("title", "")
        sec_content = sec.get("content", "")
        if sec_title:
            story.append(Paragraph(escape(str(sec_title)), h2_style))
            story.append(Spacer(1, 6))
        for line in sec_content.splitlines():
            if line.strip():
                story.append(Paragraph(escape(line.strip()), body_style))
                story.append(Spacer(1, 4))
        story.append(Spacer(1, 10))

    doc.build(story)
    return str(save_artifact(lambda path: path.write_bytes(buffer.getvalue()), out_path))


def generate_document(parameters: dict, **_kwargs) -> str:
    """Document Generation Action handler."""
    require_owner()
    doc_type = str(parameters.get("doc_type", "presentation")).lower().strip()
    title = str(parameters.get("title", "Generated Document")).strip()

    if doc_type in ("presentation", "ppt", "powerpoint"):
        slides = parameters.get("slides") or [
            {"title": "Overview", "content": "Summary of requirements and objectives."},
            {"title": "Milestones", "content": "Key phases and implementation targets."}
        ]
        out_path = create_powerpoint(title, slides)
        return json.dumps({
            "status": "success",
            "doc_type": "presentation",
            "file_path": out_path,
            "message": f"PowerPoint presentation generated successfully: {out_path}"
        }, indent=2)

    elif doc_type in ("spreadsheet", "excel", "xlsx"):
        headers = parameters.get("headers") or ["Item", "Category", "Value", "Status"]
        rows = parameters.get("rows") or [
            ["Project Kickoff", "Planning", "100%", "Complete"],
            ["Execution Engine", "Development", "95%", "In Progress"]
        ]
        out_path = create_excel_sheet(title, headers, rows)
        return json.dumps({
            "status": "success",
            "doc_type": "spreadsheet",
            "file_path": out_path,
            "message": f"Excel spreadsheet generated successfully: {out_path}"
        }, indent=2)

    elif doc_type in ("pdf", "report"):
        sections = parameters.get("sections") or [
            {"title": "Executive Summary", "content": "Autonomous report compilation and status verification."},
            {"title": "Details", "content": "System architecture operational without external dependencies."}
        ]
        out_path = create_pdf_document(title, sections)
        return json.dumps({
            "status": "success",
            "doc_type": "pdf",
            "file_path": out_path,
            "message": f"PDF report generated successfully: {out_path}"
        }, indent=2)

    else:
        return json.dumps({"status": "error", "message": f"Unsupported doc_type: {doc_type}"})


TOOL = {
    "name": "generate_document",
    "description": "Document & Presentation Generation: Autonomously generate complete PowerPoint presentations (.pptx), Excel spreadsheets (.xlsx), and PDF reports from raw data.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "doc_type": {
                "type": "STRING",
                "enum": ["presentation", "spreadsheet", "pdf"],
                "description": "Type of document to generate."
            },
            "title": {
                "type": "STRING",
                "description": "The title or subject of the document."
            },
            "slides": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING", "description": "Slide title"},
                        "content": {"type": "STRING", "description": "Slide content"}
                    }
                },
                "description": "List of slide objects with 'title' and 'content' (for presentations)."
            },
            "headers": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "List of column headers (for spreadsheets)."
            },
            "rows": {
                "type": "ARRAY",
                "items": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"}
                },
                "description": "List of row arrays (for spreadsheets)."
            },
            "sections": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING", "description": "Section title"},
                        "content": {"type": "STRING", "description": "Section text"}
                    }
                },
                "description": "List of sections with 'title' and 'content' (for PDFs)."
            }
        },
        "required": ["doc_type", "title"]
    },
    "handler": generate_document
}
