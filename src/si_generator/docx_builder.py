from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches
from docx.shared import RGBColor
from docx.shared import Pt

from .chemistry import calc_hrms_mz, ion_formula
from .models import Compound
from .style_config import DEFAULT_STYLE_CONFIG, apply_paragraph_style, apply_run_style, config_get


def build_document(
    compounds: list[Compound],
    output_path: str | Path,
    style_config: dict[str, Any] | None = None,
    template_path: str | Path | None = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    style_config = style_config or DEFAULT_STYLE_CONFIG

    document = Document(str(template_path)) if template_path else Document()
    if template_path:
        document._body.clear_content()
    else:
        _configure_styles(document)

    for index, compound in enumerate(compounds):
        if index:
            document.add_paragraph()
        _add_compound_block(document, compound, style_config)

    _add_spectra_appendix(document, compounds, style_config)
    document.save(output_path)
    return output_path


def _configure_styles(document: Document) -> None:
    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)

    for section in document.sections:
        section.top_margin = Pt(56.7)
        section.bottom_margin = Pt(56.7)
        section.left_margin = Pt(85.05)
        section.right_margin = Pt(42.5)


def _add_compound_block(document: Document, compound: Compound, style_config: dict[str, Any]) -> None:
    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    title.paragraph_format.space_after = Pt(0)
    apply_paragraph_style(title, style_config, "compound.title")
    title_run = title.add_run(f"{compound.name} ")
    apply_run_style(title_run, style_config, "compound.title")
    number_run = title.add_run(compound.label)
    apply_run_style(number_run, style_config, "compound.number")

    summary_parts = []
    if compound.preparation:
        summary_parts.append(compound.preparation.rstrip("."))
    if compound.yield_text:
        summary_parts.append(f"Yield {compound.yield_text}")
    appearance = " ".join(part for part in [compound.color, compound.state] if part)
    if appearance:
        summary_parts.append(appearance)
    if compound.melting_point:
        summary_parts.append(f"mp {compound.melting_point}")
    if compound.rf:
        summary_parts.append(compound.rf)

    if compound.structure_path or compound.has_word_structure:
        _add_structure_paragraph(document, compound)

    if summary_parts:
        text = "; ".join(summary_parts) + "." if summary_parts else ""
        _add_summary_paragraph(document, text, style_config)

    if compound.h1_nmr:
        _add_nmr_line(document, "1H NMR", compound.h1_nmr, compound.h1_conditions, style_config)
    if compound.c13_nmr:
        _add_nmr_line(document, "13C{1H} NMR", compound.c13_nmr, compound.c13_conditions, style_config)
    if compound.extra_nmr:
        _add_sentence_paragraph(document, compound.extra_nmr, style_config)
    if compound.formula and compound.hrms_found:
        _add_hrms_line(document, compound, style_config)
    if compound.ir:
        _add_ir_line(document, compound.ir, style_config)
    if compound.nmr_check_warning:
        _add_nmr_warning(document, compound.nmr_check_warning)


def _add_sentence_paragraph(document: Document, text: str, style_config: dict[str, Any]):
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(0)
    _add_chem_text_runs(paragraph, text, style_config)
    return paragraph


def _add_structure_paragraph(document: Document, compound: Compound):
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1.0
    paragraph.add_run(f"[[STRUCTURE:{compound.number}]]")
    return paragraph


def _add_summary_paragraph(document: Document, text: str, style_config: dict[str, Any]):
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(0)
    apply_paragraph_style(paragraph, style_config, "compound.summary")
    paragraph.add_run(text)
    return paragraph


def _add_labelled_line(document: Document, label: str, text: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(0)
    label_run = paragraph.add_run(f"{label}: ")
    label_run.bold = True
    paragraph.add_run(text.strip())


def _add_nmr_line(document: Document, label: str, text: str, conditions: str, style_config: dict[str, Any]) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(0)
    apply_paragraph_style(paragraph, style_config, "nmr")
    if label == "1H NMR":
        run = _add_isotope_run(paragraph, "1", style_config)
        apply_run_style(run, style_config, "nmr.label")
        run = paragraph.add_run("H NMR")
        apply_run_style(run, style_config, "nmr.label")
        if conditions:
            _add_conditions_runs(paragraph, conditions, style_config)
        paragraph.add_run(" ")
    elif label == "13C{1H} NMR":
        run = _add_isotope_run(paragraph, "13", style_config)
        apply_run_style(run, style_config, "nmr.label")
        run = paragraph.add_run("C{")
        apply_run_style(run, style_config, "nmr.label")
        run = _add_isotope_run(paragraph, "1", style_config)
        apply_run_style(run, style_config, "nmr.label")
        run = paragraph.add_run("H} NMR")
        apply_run_style(run, style_config, "nmr.label")
        if conditions:
            _add_conditions_runs(paragraph, conditions, style_config)
        paragraph.add_run(" ")
    else:
        run = paragraph.add_run(f"{label}: ")
        apply_run_style(run, style_config, "nmr.label")
    _add_chem_text_runs(paragraph, text.strip(), style_config, "nmr.body")


def _add_ir_line(document: Document, text: str, style_config: dict[str, Any]) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(0)
    apply_paragraph_style(paragraph, style_config, "ir")
    run = paragraph.add_run("IR (KBr, cm")
    apply_run_style(run, style_config, "ir.label")
    run = paragraph.add_run("-1")
    run.font.superscript = bool(config_get(style_config, "ir.unit.superscript_minus_one", True))
    apply_run_style(run, style_config, "ir.label")
    run = paragraph.add_run("): ")
    apply_run_style(run, style_config, "ir.label")
    paragraph.add_run(text.strip())


def _add_hrms_line(document: Document, compound: Compound, style_config: dict[str, Any]) -> None:
    calcd = calc_hrms_mz(compound.formula, compound.hrms_adduct)
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(0)
    apply_paragraph_style(paragraph, style_config, "hrms")
    label_run = paragraph.add_run(f"{compound.hrms_label}: ")
    apply_run_style(label_run, style_config, "hrms.label")
    _add_adduct_runs(paragraph, compound.hrms_adduct, style_config)
    paragraph.add_run(" calcd for ")
    _add_formula_runs(paragraph, ion_formula(compound.formula, compound.hrms_adduct), style_config)
    paragraph.add_run(f" {calcd:.4f}. Found {float(compound.hrms_found):.4f}.")


def _add_nmr_warning(document: Document, text: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run(f"(Support check: {text})")
    run.font.color.rgb = RGBColor(192, 0, 0)
    run.bold = True


def _add_spectra_appendix(document: Document, compounds: list[Compound], style_config: dict[str, Any]) -> None:
    spectra = []
    for compound in compounds:
        if compound.h1_image_path and Path(compound.h1_image_path).exists():
            spectra.append((compound, "1H", compound.h1_image_path))
        if compound.c13_image_path and Path(compound.c13_image_path).exists():
            spectra.append((compound, "13C", compound.c13_image_path))
    if not spectra:
        return

    document.add_page_break()
    for index, (compound, nucleus, image_path) in enumerate(spectra):
        if index:
            document.add_page_break()
        _add_spectrum_page(document, compound, nucleus, image_path, style_config)


def _add_spectrum_page(document: Document, compound: Compound, nucleus: str, image_path: str, style_config: dict[str, Any]) -> None:
    _add_spectrum_compound_title(document, compound, style_config)
    conditions = compound.h1_conditions if nucleus == "1H" else compound.c13_conditions
    _add_spectrum_nmr_title(document, nucleus, conditions, style_config)

    structure = document.add_paragraph()
    structure.paragraph_format.space_after = Pt(0)
    structure.add_run(f"[[SPECTRUM_STRUCTURE:{compound.number}:{nucleus}]]")

    picture = document.add_paragraph()
    picture.paragraph_format.space_after = Pt(0)
    picture.alignment = WD_ALIGN_PARAGRAPH.CENTER
    section = document.sections[-1]
    picture_width = section.page_width - section.left_margin - section.right_margin
    picture.add_run().add_picture(image_path, width=picture_width)


def _add_spectrum_compound_title(document: Document, compound: Compound, style_config: dict[str, Any]) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(0)
    apply_paragraph_style(paragraph, style_config, "appendix.title")
    run = paragraph.add_run(f"{compound.name} {compound.label}")
    apply_run_style(run, style_config, "appendix.title")


def _add_spectrum_nmr_title(document: Document, nucleus: str, conditions: str, style_config: dict[str, Any]) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(0)
    apply_paragraph_style(paragraph, style_config, "appendix.spectrum_title")
    if nucleus == "1H":
        run = _add_isotope_run(paragraph, "1", style_config)
        apply_run_style(run, style_config, "appendix.spectrum_title")
        run = paragraph.add_run("H NMR")
        apply_run_style(run, style_config, "appendix.spectrum_title")
    else:
        run = _add_isotope_run(paragraph, "13", style_config)
        apply_run_style(run, style_config, "appendix.spectrum_title")
        run = paragraph.add_run("C{")
        apply_run_style(run, style_config, "appendix.spectrum_title")
        run = _add_isotope_run(paragraph, "1", style_config)
        apply_run_style(run, style_config, "appendix.spectrum_title")
        run = paragraph.add_run("H} NMR")
        apply_run_style(run, style_config, "appendix.spectrum_title")
    if conditions:
        _add_conditions_runs(paragraph, conditions, style_config, "appendix.spectrum_title")


def _add_formula_runs(paragraph, formula: str, style_config: dict[str, Any]) -> None:
    chunks = []
    current = ""
    current_is_digit = None

    for char in formula:
        is_digit = char.isdigit()
        if current and is_digit != current_is_digit:
            chunks.append((current, current_is_digit))
            current = ""
        current += char
        current_is_digit = is_digit
    if current:
        chunks.append((current, current_is_digit))

    for text, is_digit in chunks:
        run = paragraph.add_run(text)
        run.font.subscript = bool(is_digit and config_get(style_config, "hrms.formula.subscripts", True))
        if text in {"+", "-"}:
            run.font.superscript = bool(config_get(style_config, "hrms.formula.charge_superscript", True))


def _add_isotope_run(paragraph, text: str, style_config: dict[str, Any]):
    run = paragraph.add_run(text)
    run.font.superscript = bool(config_get(style_config, "chem_formatting.isotope_numbers.superscript", True))
    return run


def _add_conditions_runs(paragraph, conditions: str, style_config: dict[str, Any], style_path: str = "nmr.conditions") -> None:
    run = paragraph.add_run(" (")
    apply_run_style(run, style_config, style_path)
    _add_formula_text_runs(paragraph, conditions, style_config, style_path)
    run = paragraph.add_run(")")
    apply_run_style(run, style_config, style_path)


def _add_adduct_runs(paragraph, adduct: str, style_config: dict[str, Any]) -> None:
    for index, char in enumerate(adduct):
        run = paragraph.add_run(char)
        if index == len(adduct) - 1 and char in "+-":
            run.font.superscript = bool(config_get(style_config, "hrms.adduct.superscript_charge", False))


def _add_formula_text_runs(paragraph, text: str, style_config: dict[str, Any], style_path: str = "") -> None:
    pos = 0
    for match in re.finditer(r"\b(?:CDCl3|DMSO-d6|C\d*H\d*(?:[A-Z][a-z]?\d*)*)\b", text):
        if match.start() > pos:
            run = paragraph.add_run(text[pos:match.start()])
            if style_path:
                apply_run_style(run, style_config, style_path)
        formula = match.group(0)
        for char in formula:
            run = paragraph.add_run(char)
            if style_path:
                apply_run_style(run, style_config, style_path)
            run.font.subscript = bool(char.isdigit() and config_get(style_config, "chem_formatting.formulas.subscripts", True))
        pos = match.end()
    if pos < len(text):
        run = paragraph.add_run(text[pos:])
        if style_path:
            apply_run_style(run, style_config, style_path)


def _add_chem_text_runs(paragraph, text: str, style_config: dict[str, Any], style_path: str = "") -> None:
    if config_get(style_config, "chem_formatting.ranges.en_dash", False):
        text = re.sub(r"(?<=\d)\s+-\s+(?=\d)", "\u2013", text)

    pattern = re.compile(r"(?<![A-Za-z])(?:(\d+)(J)([A-Z]{1,3})?|\b(J)\b)")
    pos = 0
    for match in pattern.finditer(text):
        if match.start() > pos:
            run = paragraph.add_run(text[pos:match.start()])
            if style_path:
                apply_run_style(run, style_config, style_path)
        if match.group(2):
            order, j_text, partner = match.group(1), match.group(2), match.group(3) or ""
            run = paragraph.add_run(order)
            if style_path:
                apply_run_style(run, style_config, style_path)
            run.font.superscript = bool(config_get(style_config, "chem_formatting.coupling_constants.order_superscript", False))
            run = paragraph.add_run(j_text)
            if style_path:
                apply_run_style(run, style_config, style_path)
            run.italic = bool(config_get(style_config, "chem_formatting.coupling_constants.j_italic", False))
            if partner:
                run = paragraph.add_run(partner)
                if style_path:
                    apply_run_style(run, style_config, style_path)
                run.font.subscript = bool(config_get(style_config, "chem_formatting.coupling_constants.coupling_partner_subscript", False))
        else:
            run = paragraph.add_run(match.group(4))
            if style_path:
                apply_run_style(run, style_config, style_path)
            run.italic = bool(config_get(style_config, "chem_formatting.coupling_constants.j_italic", False))
        pos = match.end()
    if pos < len(text):
        run = paragraph.add_run(text[pos:])
        if style_path:
            apply_run_style(run, style_config, style_path)
