from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from docx.text.paragraph import Paragraph

from .domain.compound import Compound
from .domain.elemental_analysis import calculate_elemental_analysis_block, found_from_block
from .domain.ir import parse_ir_block
from .domain.massspec import build_hrms_block, hrms_adduct_text, hrms_found_text, hrms_label_text
from .domain.references import format_reference
from .domain.reactions import calculate_reaction_loadings
from .render.si_document import DocumentBlock, SIDocument
from .runtime_paths import bundled_resource_path


DEFAULT_TEMPLATE_RESOURCE = Path("si_generator/templates/SI_template.docx")

PLACEHOLDER_RE = re.compile(r"\[\{([^{}]+)\}\]|\{([^{}]+)\}")


def default_template_path() -> Path:
    candidates = [
        bundled_resource_path(DEFAULT_TEMPLATE_RESOURCE, package_file=__file__),
        Path(__file__).resolve().parent / "templates" / "SI_template.docx",
        Path(__file__).resolve().parents[2] / "examples" / "templates" / "SI_template_visual_current.docx",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def render_document_from_template(
    document_model: SIDocument,
    output_path: str | Path,
    template_path: str | Path | None = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    template = Path(template_path) if template_path else default_template_path()

    template_document = Document(str(template))
    segments = _split_template_segments(template_document)
    output_document = Document(str(template))
    output_document._body.clear_content()

    for section in document_model.get("sections", []):
        blocks = section.get("blocks", [])
        if section.get("id") == "compound_descriptions":
            _render_compound_blocks(output_document, segments["compound"], blocks)
        elif section.get("id") == "spectra_appendix" and blocks:
            _render_spectrum_blocks(output_document, segments, blocks)
        elif section.get("id") == "references" and blocks:
            _render_reference_blocks(output_document, blocks)

    output_document.save(output_path)
    return output_path


def _split_template_segments(document: DocumentObject) -> dict[str, list[Paragraph]]:
    pages: list[list[Paragraph]] = [[]]
    for paragraph in document.paragraphs:
        if _paragraph_has_page_break(paragraph):
            pages.append([])
            continue
        pages[-1].append(paragraph)

    return {
        "compound": pages[0] if pages else [],
        "appendix_1h": pages[1] if len(pages) > 1 else [],
        "appendix_13c": pages[2] if len(pages) > 2 else (pages[1] if len(pages) > 1 else []),
    }


def _paragraph_has_page_break(paragraph: Paragraph) -> bool:
    return bool(paragraph._p.xpath('.//w:br[@w:type="page"]'))


def _render_compound_blocks(document: DocumentObject, template_paragraphs: list[Paragraph], blocks: list[DocumentBlock]) -> None:
    for index, block in enumerate(blocks):
        if index:
            document.add_paragraph()
        first_index = len(document.paragraphs)
        compound: Compound = block["content"]
        values = _compound_values(compound)
        _render_template_paragraphs(document, template_paragraphs, values, compound=compound)
        _add_bookmark_range(document.paragraphs[first_index], document.paragraphs[-1], block.get("bookmark", ""))


def _render_spectrum_blocks(document: DocumentObject, segments: dict[str, list[Paragraph]], blocks: list[DocumentBlock]) -> None:
    first = True
    for block in blocks:
        if first:
            document.add_page_break()
            first = False
        else:
            document.add_page_break()
        first_index = len(document.paragraphs)
        compound: Compound = block["content"]
        nucleus = str(block.get("nucleus") or "")
        template_paragraphs = segments["appendix_1h"] if nucleus == "1H" else segments["appendix_13c"]
        values = _compound_values(compound)
        values.update(_spectrum_values(compound, nucleus))
        _render_template_paragraphs(document, template_paragraphs, values, compound=compound, spectrum_block=block)
        _add_bookmark_range(document.paragraphs[first_index], document.paragraphs[-1], block.get("bookmark", ""))


def _render_reference_blocks(document: DocumentObject, blocks: list[DocumentBlock]) -> None:
    document.add_page_break()
    title = document.add_paragraph()
    title.paragraph_format.space_after = Pt(0)
    title.add_run("References").bold = True
    for block in blocks:
        content = block.get("content", {})
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(0)
        _add_bookmark_range(paragraph, paragraph, block.get("bookmark", ""))
        paragraph.add_run(format_reference(content["reference"], int(content["index"])))


def _render_template_paragraphs(
    document: DocumentObject,
    template_paragraphs: list[Paragraph],
    values: dict[str, str],
    *,
    compound: Compound,
    spectrum_block: DocumentBlock | None = None,
) -> None:
    for template_paragraph in template_paragraphs:
        text = template_paragraph.text
        if text.startswith("[[STRUCTURE:") and not (compound.has_word_structure or compound.structure_path):
            continue
        if _should_skip_paragraph(text, values):
            continue
        if "[[SPECTRUM:" in text:
            _render_spectrum_artifact(document, spectrum_block)
            continue

        paragraph = _clone_paragraph(document, template_paragraph)
        _replace_placeholders(paragraph, values)
        if compound.nmr_check_warning and "{compound.support_warning}" in text:
            _style_warning_paragraph(paragraph)


def _clone_paragraph(document: DocumentObject, paragraph: Paragraph) -> Paragraph:
    new_p = deepcopy(paragraph._p)
    body = document._body._element
    sect_pr = body.sectPr
    if sect_pr is None:
        body.append(new_p)
    else:
        body.insert(body.index(sect_pr), new_p)
    return Paragraph(new_p, document._body)


def _replace_placeholders(paragraph: Paragraph, values: dict[str, str]) -> None:
    for run in paragraph.runs:
        if not run.text:
            continue

        def replace(match: re.Match[str]) -> str:
            key = match.group(1) or match.group(2) or ""
            return values.get(_key(key), "")

        run.text = PLACEHOLDER_RE.sub(replace, run.text)


def _render_spectrum_artifact(document: DocumentObject, block: DocumentBlock | None) -> None:
    if not block:
        return
    compound: Compound = block["content"]
    nucleus = str(block.get("nucleus") or "")
    embed_mode = str(block.get("embed_mode") or "png")
    image_path = str(block.get("image_path") or "")
    mnova_path = str(block.get("mnova_path") or "")

    if embed_mode in {"mnova", "both"} and mnova_path:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.add_run(f"[[MNOVA:{compound.number}:{nucleus}]]")

    if embed_mode in {"png", "both"} and image_path:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(0)
        section = document.sections[-1]
        picture_width = section.page_width - section.left_margin - section.right_margin
        paragraph.add_run().add_picture(image_path, width=picture_width)


def _should_skip_paragraph(text: str, values: dict[str, str]) -> bool:
    keys = {_key(match.group(1) or match.group(2) or "") for match in PLACEHOLDER_RE.finditer(text)}
    if not keys:
        return False
    if any(key.startswith("nmr.1h.") for key in keys) and not values.get("nmr.1h.peaks"):
        return True
    if any(key.startswith("nmr.13c.") for key in keys) and not values.get("nmr.13c.peaks"):
        return True
    if "nmr.extra" in keys and not values.get("nmr.extra"):
        return True
    if any(key.startswith("hrms.") for key in keys) and not values.get("hrms.found"):
        return True
    if any(key.startswith("anal.") for key in keys) and not values.get("anal.calculated"):
        return True
    if any(key.startswith("ir.") for key in keys) and not values.get("ir.peaks"):
        return True
    if "compound.preparation" in keys and not values.get("compound.preparation"):
        return True
    if "reaction.loadings" in keys and not values.get("reaction.loadings"):
        return True
    if _has_loadings_placeholders(keys) and not values.get("number.product"):
        return True
    if "compound.support_warning" in keys and not values.get("compound.support_warning"):
        return True
    return False


def _compound_values(compound: Compound) -> dict[str, str]:
    loadings_values = {str(key): str(value) for key, value in compound.reaction.get("template_values", {}).items()}
    values = {
        "compound.name": compound.name,
        "compound.number": compound.number,
        "compound.label": compound.label,
        "compound.preparation": "" if loadings_values else _summary_text(compound),
        "compound.support_warning": f"(Support check: {compound.nmr_check_warning})" if compound.nmr_check_warning else "",
        "reaction.loadings": _reaction_loadings_text(compound),
        "nmr.1h.label": "1H NMR",
        "nmr.1h.conditions": compound.h1_conditions,
        "nmr.1h.peaks": compound.h1_nmr.strip(),
        "nmr.13c.label": "13C{1H} NMR",
        "nmr.13c.conditions": compound.c13_conditions,
        "nmr.13c.peaks": compound.c13_nmr.strip(),
        "nmr.extra": compound.extra_nmr.strip(),
    }
    values.update(_hrms_values(compound))
    values.update(_elemental_values(compound))
    values.update(_ir_values(compound))
    values.update(loadings_values)
    return {_key(key): value for key, value in values.items()}


def _spectrum_values(compound: Compound, nucleus: str) -> dict[str, str]:
    if nucleus == "1H":
        return {
            "spectrum.nucleus": "1H",
            "spectrum.label": "1H NMR",
            "spectrum.conditions": compound.h1_conditions,
            "spectrum.structure.marker": f"[[SPECTRUM_STRUCTURE:{compound.number}:1H]]",
        }
    return {
        "spectrum.nucleus": "13C",
        "spectrum.label": "13C{1H} NMR",
        "spectrum.conditions": compound.c13_conditions,
        "spectrum.structure.marker": f"[[SPECTRUM_STRUCTURE:{compound.number}:13C]]",
    }


def _summary_text(compound: Compound) -> str:
    parts = []
    preparation_includes_summary = bool(compound.reaction.get("preparation_includes_summary"))
    if compound.preparation:
        parts.append(compound.preparation.rstrip("."))
    if compound.yield_text and not preparation_includes_summary:
        parts.append(f"Yield {compound.yield_text}")
    appearance = " ".join(part for part in [compound.color, compound.state] if part)
    if appearance and not preparation_includes_summary:
        parts.append(appearance)
    if compound.melting_point and not preparation_includes_summary:
        parts.append(f"mp {compound.melting_point}")
    if compound.rf and not preparation_includes_summary:
        parts.append(compound.rf)
    return "; ".join(parts) + "." if parts else ""


def _reaction_loadings_text(compound: Compound) -> str:
    if not compound.reaction or compound.reaction.get("hide_loadings_line"):
        return ""
    block = compound.reaction
    if not block.get("formatted_text"):
        block = calculate_reaction_loadings(block)
        compound.reaction = block
    text = str(block.get("formatted_text", "")).strip()
    if not text:
        return ""
    return f"Reaction loadings: {text.rstrip('.')}."


def _hrms_values(compound: Compound) -> dict[str, str]:
    found = hrms_found_text(compound.hrms, compound.hrms_found)
    if not (compound.formula and found):
        return {}
    try:
        block = build_hrms_block(
            formula=compound.formula,
            label=hrms_label_text(compound.hrms, compound.hrms_label),
            adduct=hrms_adduct_text(compound.hrms, compound.hrms_adduct),
            found_text=found,
            isotope_labels=compound.hrms.get("isotope_labels") if compound.hrms else None,
        )
    except Exception:
        return {}
    return {
        "hrms.label": str(block.get("label") or ""),
        "hrms.adduct": str(block.get("adduct") or ""),
        "hrms.formula": _formula_with_isotope_labels(str(block.get("ion_formula") or ""), block.get("isotope_labels", {})),
        "hrms.calculated": f"{float(block.get('calculated_mz', 0.0)):.4f}",
        "hrms.found": str(block.get("found_text") or found).replace(",", "."),
    }


def _elemental_values(compound: Compound) -> dict[str, str]:
    if not (compound.formula and compound.elemental_analysis):
        return {}
    try:
        block = calculate_elemental_analysis_block(compound.formula, found_from_block(compound.elemental_analysis))
    except Exception:
        return {}
    calculated = block.get("calculated", {})
    found = block.get("found", {})
    elements = list(calculated)
    for element in found:
        if element not in elements:
            elements.append(element)
    return {
        "anal.label": "Anal.",
        "anal.formula": str(block.get("formula") or compound.formula),
        "anal.calculated": "; ".join(f"{element}, {calculated[element]:.2f}" for element in elements if element in calculated),
        "anal.found": "; ".join(f"{element}, {found[element]:.2f}" for element in elements if element in found),
    }


def _ir_values(compound: Compound) -> dict[str, str]:
    block = parse_ir_block(compound.ir)
    peaks = block.get("peaks_cm1", [])
    if not peaks:
        return {}
    return {
        "ir.label": "IR",
        "ir.method": str(block.get("method") or "KBr"),
        "ir.peaks": ", ".join(str(peak) for peak in peaks),
    }


def _formula_with_isotope_labels(formula: str, isotope_labels: Any) -> str:
    if not formula or not isinstance(isotope_labels, dict) or not isotope_labels:
        return formula

    def replace(match: re.Match[str]) -> str:
        element = match.group(0)
        label = isotope_labels.get(element)
        return f"{label}{element}" if label else element

    return re.sub(r"[A-Z][a-z]?", replace, formula)


def _style_warning_paragraph(paragraph: Paragraph) -> None:
    for run in paragraph.runs:
        run.bold = True
        run.font.color.rgb = RGBColor(192, 0, 0)


def _has_loadings_placeholders(keys: set[str]) -> bool:
    prefixes = ("name.reagent", "mg.reagent", "mmol.reagent", "number.product", "mg.yield.product")
    return any(key.startswith(prefix) for key in keys for prefix in prefixes)


def _add_bookmark_range(start_paragraph: Paragraph, end_paragraph: Paragraph, name: str) -> None:
    if not name:
        return
    bookmark_id = str(int(hashlib.sha1(name.encode("utf-8")).hexdigest()[:8], 16))
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), bookmark_id)
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), bookmark_id)
    insert_at = 1 if len(start_paragraph._p) and start_paragraph._p[0].tag == qn("w:pPr") else 0
    start_paragraph._p.insert(insert_at, start)
    end_paragraph._p.append(end)


def _key(value: Any) -> str:
    text = str(value).strip().replace("\u03bc", "u")
    return re.sub(r"[^a-z0-9]+", ".", text.lower()).strip(".")
