from __future__ import annotations

from pathlib import Path

from ..domain.references import select_references_for_compounds
from ..domain.types import JournalProfile
from ..domain.types import ReferenceStore
from ..models import Compound
from .si_document import DocumentBlock, SIDocument, SISection


def build_si_document_model(
    compounds: list[Compound],
    journal_profile: JournalProfile | None = None,
    reference_store: ReferenceStore | None = None,
) -> SIDocument:
    compound_blocks = [_compound_description_block(compound) for compound in compounds]
    sections_by_id: dict[str, SISection] = {
        "compound_descriptions": {
            "id": "compound_descriptions",
            "title": "Compound descriptions",
            "blocks": compound_blocks,
        }
    }

    spectra_blocks = _spectrum_blocks(compounds)
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
            "journal_profile": (journal_profile or {}).get("id", "default"),
        },
    }


def _section_order(journal_profile: JournalProfile | None) -> list[str]:
    order = (journal_profile or {}).get("section_order", [])
    return list(order) if isinstance(order, list) else ["compound_descriptions", "spectra_appendix", "references"]


def _compound_description_block(compound: Compound) -> DocumentBlock:
    return {
        "kind": "compound_description",
        "compound_id": compound.id,
        "content": compound,
    }


def _spectrum_blocks(compounds: list[Compound]) -> list[DocumentBlock]:
    blocks: list[DocumentBlock] = []
    for compound in compounds:
        if compound.h1_image_path and Path(compound.h1_image_path).exists():
            blocks.append(_spectrum_block(compound, "1H", compound.h1_image_path))
        if compound.c13_image_path and Path(compound.c13_image_path).exists():
            blocks.append(_spectrum_block(compound, "13C", compound.c13_image_path))
    return blocks


def _spectrum_block(compound: Compound, nucleus: str, image_path: str) -> DocumentBlock:
    return {
        "kind": "spectrum_page",
        "compound_id": compound.id,
        "content": compound,
        "nucleus": nucleus,
        "image_path": image_path,
    }


def _reference_blocks(compounds: list[Compound], reference_store: ReferenceStore | None) -> list[DocumentBlock]:
    if not reference_store:
        return []
    references = select_references_for_compounds(reference_store, [compound.references for compound in compounds])
    return [
        {
            "kind": "reference",
            "content": {"index": index, "reference": reference},
        }
        for index, reference in enumerate(references, start=1)
    ]
