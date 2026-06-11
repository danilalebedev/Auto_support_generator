from __future__ import annotations

from pathlib import Path

from ..domain.bookmarks import bookmark_name_for_block_id
from ..domain.references import select_references_for_compounds
from ..domain.types import JournalProfile
from ..domain.types import ReferenceStore
from ..domain.types import SpectrumEmbedMode
from ..models import Compound
from .si_document import DocumentBlock, SIDocument, SISection


def build_si_document_model(
    compounds: list[Compound],
    journal_profile: JournalProfile | None = None,
    reference_store: ReferenceStore | None = None,
    spectra_embed_mode: SpectrumEmbedMode = "png",
) -> SIDocument:
    compound_blocks = [_compound_description_block(compound) for compound in compounds]
    sections_by_id: dict[str, SISection] = {
        "compound_descriptions": {
            "id": "compound_descriptions",
            "title": "Compound descriptions",
            "blocks": compound_blocks,
        }
    }

    spectra_blocks = _spectrum_blocks(compounds, spectra_embed_mode)
    if spectra_blocks:
        sections_by_id["spectra_appendix"] = {
            "id": "spectra_appendix",
            "title": "Spectra appendix",
            "blocks": spectra_blocks,
        }
    reference_blocks = _reference_blocks(compounds, reference_store)
    if reference_blocks:
        sections_by_id["references"] = {
            "id": "references",
            "title": "References",
            "blocks": reference_blocks,
        }
    section_order = _section_order(journal_profile)
    sections = [sections_by_id[section_id] for section_id in section_order if section_id in sections_by_id]
    sections.extend(section for section_id, section in sections_by_id.items() if section_id not in section_order)

    return {
        "title": "Supporting Information",
        "sections": sections,
        "metadata": {
            "compound_count": str(len(compounds)),
            "spectrum_count": str(len(spectra_blocks)),
            "references_count": str(len(reference_blocks)),
            "journal_profile": (journal_profile or {}).get("id", "default"),
        },
    }


def _section_order(journal_profile: JournalProfile | None) -> list[str]:
    order = (journal_profile or {}).get("section_order", [])
    return list(order) if isinstance(order, list) else ["compound_descriptions", "spectra_appendix", "references"]


def _compound_description_block(compound: Compound) -> DocumentBlock:
    compound_id = _compound_id(compound)
    block_id = f"compound:{compound_id}"
    return {
        "kind": "compound_description",
        "block_id": block_id,
        "bookmark": bookmark_name_for_block_id(block_id),
        "compound_id": compound_id,
        "display_number": compound.number,
        "title_text": f"{compound.name} {compound.label}",
        "structure_placeholder": f"STRUCTURE:{compound.number}",
        "content": compound,
    }


def _spectrum_blocks(compounds: list[Compound], embed_mode: SpectrumEmbedMode) -> list[DocumentBlock]:
    if embed_mode == "none":
        return []

    blocks: list[DocumentBlock] = []
    for compound in compounds:
        if _should_include_spectrum(compound, "1H", embed_mode):
            blocks.append(_spectrum_block(compound, "1H", embed_mode))
        if _should_include_spectrum(compound, "13C", embed_mode):
            blocks.append(_spectrum_block(compound, "13C", embed_mode))
    return blocks


def _should_include_spectrum(compound: Compound, nucleus: str, embed_mode: SpectrumEmbedMode) -> bool:
    image_path = _spectrum_image_path(compound, nucleus)
    has_png = bool(image_path and Path(image_path).exists())
    has_mnova = bool(compound.mnova_path and Path(compound.mnova_path).exists())
    if embed_mode == "png":
        return has_png
    if embed_mode == "mnova":
        return has_mnova and _has_spectrum_source(compound, nucleus)
    if embed_mode == "both":
        return (has_png or has_mnova) and _has_spectrum_source(compound, nucleus)
    return False


def _spectrum_block(compound: Compound, nucleus: str, embed_mode: SpectrumEmbedMode) -> DocumentBlock:
    compound_id = _compound_id(compound)
    image_path = _spectrum_image_path(compound, nucleus)
    block_id = f"spectrum:{compound_id}:{nucleus}"
    return {
        "kind": "spectrum_page",
        "block_id": block_id,
        "bookmark": bookmark_name_for_block_id(block_id),
        "compound_id": compound_id,
        "display_number": compound.number,
        "title_text": f"{compound.name} {compound.label}",
        "content": compound,
        "structure_placeholder": f"SPECTRUM_STRUCTURE:{compound.number}:{nucleus}",
        "nucleus": nucleus,
        "embed_mode": embed_mode,
        "image_path": image_path,
        "mnova_path": compound.mnova_path,
        "expected_artifact_path": image_path if embed_mode in {"png", "both"} and image_path else compound.mnova_path,
    }


def _spectrum_image_path(compound: Compound, nucleus: str) -> str:
    return compound.h1_image_path if nucleus == "1H" else compound.c13_image_path


def _has_spectrum_source(compound: Compound, nucleus: str) -> bool:
    if nucleus == "1H":
        return bool(compound.h1_spectrum_path or compound.h1_nmr or compound.h1_image_path)
    return bool(compound.c13_spectrum_path or compound.c13_nmr or compound.c13_image_path)


def _compound_id(compound: Compound) -> str:
    return compound.id or compound.number


def _reference_blocks(compounds: list[Compound], reference_store: ReferenceStore | None) -> list[DocumentBlock]:
    if not reference_store:
        return []
    references = select_references_for_compounds(reference_store, [compound.references for compound in compounds])
    return [
        {
            "kind": "reference",
            "block_id": f"reference:{index}",
            "bookmark": bookmark_name_for_block_id(f"reference:{index}"),
            "title_text": f"Reference {index}",
            "content": {"index": index, "reference": reference},
        }
        for index, reference in enumerate(references, start=1)
    ]
