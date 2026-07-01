from __future__ import annotations

import argparse
import re
from html import escape
from pathlib import Path
from typing import Sequence

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Paragraph,
        Preformatted,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ModuleNotFoundError as exc:
    raise SystemExit(
        "reportlab is required to render this PDF. Install it with "
        "`python -m pip install reportlab`, or run this script with the Codex "
        "bundled PDF runtime."
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MARKDOWN = REPO_ROOT / "papers" / "gpt55-direct-quality-frontier-50-run-white-paper.md"
DEFAULT_PDF = REPO_ROOT / "papers" / "gpt55-direct-quality-frontier-50-run-white-paper.pdf"
TITLE = "GPT-5.5 Direct-Edit Quality Frontier: Six Leaves vs Three Leaves"
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
LIST_ITEM_RE = re.compile(r"^(\d+)\.\s+(.*)")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    markdown_path = _resolve(args.markdown)
    pdf_path = _resolve(args.pdf)
    render_pdf(markdown_path, pdf_path)
    print(f"Rendered portrait Letter PDF: {pdf_path}")
    return 0


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the GPT-5.5 leaf-count white paper as a portrait Letter PDF.")
    parser.add_argument("--markdown", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--pdf", default=str(DEFAULT_PDF))
    return parser.parse_args(argv)


def render_pdf(markdown_path: Path, pdf_path: Path) -> None:
    lines = markdown_path.read_text(encoding="utf-8").splitlines()
    styles = _styles()
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.52 * inch,
        bottomMargin=0.54 * inch,
        title=TITLE,
        author="Adam Owada, with Codex",
    )
    story = build_story(lines, styles, doc.width)
    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleCustom",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=8,
            textColor=colors.HexColor("#050505"),
        ),
        "subtitle": ParagraphStyle(
            "SubtitleCustom",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#334155"),
            spaceAfter=16,
        ),
        "author": ParagraphStyle(
            "AuthorCustom",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12,
            alignment=TA_LEFT,
            spaceAfter=13,
        ),
        "h2": ParagraphStyle(
            "Heading2Custom",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#111827"),
            spaceBefore=9,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "BodyCustom",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=12.2,
            spaceAfter=6,
        ),
        "list": ParagraphStyle(
            "ListCustom",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=12.2,
            leftIndent=0.34 * inch,
            firstLineIndent=0,
            bulletIndent=0.04 * inch,
            spaceAfter=4,
        ),
        "code": ParagraphStyle(
            "CodeCustom",
            parent=base["Code"],
            fontName="Courier",
            fontSize=6.8,
            leading=8.4,
            leftIndent=0.08 * inch,
            textColor=colors.HexColor("#334155"),
            spaceAfter=7,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=5.9,
            leading=7.0,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=5.8,
            leading=7.0,
            textColor=colors.white,
        ),
    }


def build_story(lines: list[str], styles: dict[str, ParagraphStyle], usable_width: float) -> list[object]:
    story: list[object] = []
    index = 0
    seen_title = False
    seen_subtitle = False
    while index < len(lines):
        raw = lines[index]
        line = raw.strip()
        if not line:
            index += 1
            continue

        if line.startswith("# "):
            story.append(Paragraph(_paragraph_text(line[2:]), styles["title"]))
            seen_title = True
            index += 1
            continue

        if seen_title and not seen_subtitle and not line.startswith("By ") and not line.startswith("##"):
            story.append(Paragraph(_paragraph_text(line), styles["subtitle"]))
            seen_subtitle = True
            index += 1
            continue

        if line.startswith("## "):
            story.append(Paragraph(_paragraph_text(line[3:]), styles["h2"]))
            index += 1
            continue

        if line.startswith("```"):
            index += 1
            code_lines = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            story.append(Preformatted("\n".join(code_lines), styles["code"]))
            continue

        if _is_table_start(line):
            table_lines = []
            while index < len(lines) and _is_table_start(lines[index].strip()):
                table_lines.append(lines[index])
                index += 1
            story.extend(_make_table(table_lines, styles, usable_width))
            continue

        match = LIST_ITEM_RE.match(line)
        if match:
            index = _append_list_items(lines, index, story, styles)
            continue

        paragraph, index = _collect_paragraph(lines, index)
        style_name = "author" if paragraph.startswith("By ") else "body"
        story.append(Paragraph(_paragraph_text(paragraph), styles[style_name]))
    return story


def _append_list_items(
    lines: list[str],
    index: int,
    story: list[object],
    styles: dict[str, ParagraphStyle],
) -> int:
    while index < len(lines):
        current = lines[index].strip()
        match = LIST_ITEM_RE.match(current)
        if not match:
            break
        number = match.group(1)
        parts = [match.group(2)]
        index += 1
        while index < len(lines):
            next_line = lines[index]
            stripped = next_line.strip()
            if not stripped:
                index += 1
                break
            if LIST_ITEM_RE.match(stripped) or stripped.startswith("##") or _is_table_start(stripped) or stripped.startswith("```"):
                break
            if next_line.startswith(" ") or next_line.startswith("\t"):
                parts.append(stripped)
                index += 1
            else:
                break
        story.append(Paragraph(_paragraph_text(" ".join(parts)), styles["list"], bulletText=f"{number}."))
    story.append(Spacer(1, 3))
    return index


def _collect_paragraph(lines: list[str], index: int) -> tuple[str, int]:
    parts = []
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            break
        if line.startswith("#") or line.startswith("```") or _is_table_start(line) or LIST_ITEM_RE.match(line):
            break
        parts.append(line)
        index += 1
    return " ".join(parts), index


def _make_table(table_lines: list[str], styles: dict[str, ParagraphStyle], usable_width: float) -> list[object]:
    rows = [_split_pipe_row(line) for line in table_lines if not _is_separator(line)]
    if not rows:
        return []
    col_count = max(len(row) for row in rows)
    header = [cell.lower() for cell in rows[0]]
    body_style = styles["table_cell"]
    header_style = styles["table_header"]
    data = []
    for row_index, row in enumerate(rows):
        style = header_style if row_index == 0 else body_style
        padded = row + [""] * (col_count - len(row))
        data.append([Paragraph(_paragraph_text(cell), style) for cell in padded])

    table = Table(
        data,
        colWidths=_column_widths(header, rows, usable_width),
        repeatRows=1,
        hAlign="LEFT",
        splitByRow=1,
    )
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for row_index in range(1, len(data)):
        if row_index % 2 == 0:
            commands.append(("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#f8fafc")))
    table.setStyle(TableStyle(commands))
    return [table, Spacer(1, 8)]


def _column_widths(header: list[str], rows: list[list[str]], usable_width: float) -> list[float]:
    col_count = len(header)
    if "configuration" in header and col_count == 9:
        proportions = [0.052, 0.225, 0.054, 0.082, 0.118, 0.127, 0.056, 0.150, 0.136]
    elif "reasoning pair" in header and col_count == 7:
        proportions = [0.235, 0.105, 0.105, 0.120, 0.190, 0.125, 0.120]
    elif "developer goal" in header and col_count == 3:
        proportions = [0.290, 0.345, 0.365]
    elif "directory" in header and col_count == 4:
        proportions = [0.185, 0.440, 0.105, 0.270]
    elif "effect" in header and col_count == 5:
        proportions = [0.425, 0.145, 0.210, 0.120, 0.100]
    elif col_count == 7:
        proportions = [0.075, 0.135, 0.190, 0.190, 0.135, 0.155, 0.120]
    elif col_count == 2:
        proportions = [0.245, 0.755]
    else:
        weights = []
        for column in range(col_count):
            longest = max(len(_strip_inline_code(row[column] if column < len(row) else "")) for row in rows)
            weights.append(max(5, min(longest, 30)))
        total = sum(weights)
        proportions = [weight / total for weight in weights]
    return [usable_width * proportion for proportion in proportions]


def _split_pipe_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_table_start(line: str) -> bool:
    return line.startswith("|") and "|" in line[1:]


def _is_separator(line: str) -> bool:
    cells = _split_pipe_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _strip_inline_code(text: str) -> str:
    return INLINE_CODE_RE.sub(lambda match: match.group(1), text)


def _paragraph_text(text: str) -> str:
    text = _strip_inline_code(text).replace("<br>", "<br/>")
    text = escape(text, quote=False)
    return text.replace("&lt;br/&gt;", "<br/>")


def draw_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(doc.leftMargin, 0.28 * inch, TITLE)
    canvas.drawRightString(letter[0] - doc.rightMargin, 0.28 * inch, f"Page {doc.page}")
    canvas.restoreState()


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


if __name__ == "__main__":
    raise SystemExit(main())
