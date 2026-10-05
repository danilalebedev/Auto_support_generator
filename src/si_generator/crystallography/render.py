from __future__ import annotations

from copy import deepcopy
import json
import re
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.shared import Inches, Pt, RGBColor
from docx.image.image import Image


def load_data(compound):
    if not compound.crystallography_data_path:
        return None, {}
    path = Path(compound.crystallography_data_path)
    return path.parent, json.loads(path.read_text(encoding="utf-8"))


def append_figures(document, compound):
    base, data = load_data(compound)
    for record in data.get("records", []):
        p = document.add_paragraph()
        p.paragraph_format.keep_with_next = True
        section = document.sections[-1]
        width = min(Inches(4.8), section.page_width - section.left_margin - section.right_margin)
        image_path = base / record["image"]
        img = Image.from_file(str(image_path))
        width = min(width, int(Inches(3.2) * img.px_width / img.px_height))
        p.add_run().add_picture(str(image_path), width=width)
        caption = document.add_paragraph("Crystal structure of ")
        caption.add_run(compound.number)
        caption.add_run(". " + record['caption'].replace('{Product.number}', compound.number))
        caption.paragraph_format.keep_together = True
        if record["ccdc"]:
            caption.add_run(f" Deposition: {record['ccdc']}.")


def _numbered_paragraph(document, text, number):
    text = text.replace("{Product.number}", number)
    p = document.add_paragraph()
    for piece in re.split(r"(?<![A-Za-z0-9])(" + re.escape(number) + r")(?![A-Za-z0-9])", text):
        p.add_run(piece)
    return p


def _table(document, headers, rows):
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for cell, text in zip(table.rows[0].cells, headers):
        cell.text = text
        for run in cell.paragraphs[0].runs:
            run.bold = True
    repeat = OxmlElement("w:tblHeader")
    table.rows[0]._tr.get_or_add_trPr().append(repeat)
    for values in rows:
        row = table.add_row()
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for cell, value in zip(row.cells, values):
            cell.text = str(value)
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(1)
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.line_spacing = 1.0
                for run in p.runs:
                    run.font.size = Pt(10)
    document.add_paragraph()


def append_details(document, compound):
    base, data = load_data(compound)
    template = Document(base / data["template"]) if data.get("template") else None
    for record in data.get("records", []):
        values = {"Product.number": compound.number, "Product.name": compound.display_name,
                  "Crystal.block": record["block"], "Crystal.ccdc": record["ccdc"]}
        paragraphs = template.paragraphs if template else None
        text_lines = [p.text for p in paragraphs] if paragraphs is not None else [
            "Crystallographic data for {Product.number}", "{Crystal.description}", "{Crystal.table}", "{Crystal.geometry}"]
        if template and "{Crystal.table}" not in text_lines:
            raise ValueError("Crystallography template must contain {Crystal.table} in a separate paragraph")
        for i, text in enumerate(text_lines):
            if text == "{Crystal.description}":
                for description in record["description"]:
                    _numbered_paragraph(document, description, compound.number)
                if record["ccdc"]:
                    document.add_paragraph(f"Crystallographic deposition: {record['ccdc']}.")
            elif text == "{Crystal.table}":
                _table(document, ["Crystal data and structure refinement", compound.number],
                       [(r["label"], r["value"]) for r in record["rows"] if r["value"] is not None])
            elif text == "{Crystal.geometry}":
                if record["geometry"]:
                    _table(document, ["Geometry", "Atoms", "Value (angstrom / degrees)", "Symmetry"],
                           [(g["kind"], g["atoms"], g["value"], g["symmetry"]) for g in record["geometry"]])
            else:
                for key, value in values.items():
                    if key == "Product.number":
                        continue
                    text = text.replace("{" + key + "}", value)
                p = document.add_paragraph()
                for part_index, part in enumerate(text.split("{Product.number}")):
                    if part_index:
                        p.add_run(compound.number)
                    p.add_run(part)
                if template and paragraphs[i]._p.pPr is not None:
                    p._p.insert(0, deepcopy(paragraphs[i]._p.pPr))
                if i == 0:
                    p.paragraph_format.keep_with_next = True
                    for run in p.runs:
                        run.bold = True
                        run.font.color.rgb = RGBColor(0, 0, 0)


def write_report(compound, target):
    document = Document()
    for border in document.styles['Title'].element.xpath('.//w:pBdr'):
        border.getparent().remove(border)
    title = document.add_heading(f"X-ray crystallography of {compound.number}", 0)
    for run in title.runs:
        run.font.color.rgb = RGBColor(0, 0, 0)
    append_figures(document, compound)
    document.add_page_break()
    append_details(document, compound)
    document.save(target)
