from __future__ import annotations

from pathlib import Path

from .si_document import DocumentBlock, SIDocument, SISection
from ..models import Compound


def build_si_document_model(compounds: list[Compound]) -> SIDocument:
    compound_blocks = [_compound_description_block(compound) for compound in compounds]
    sections: list[SISection] = [
        {
            "id": "compound_descriptions",
            "title": "Compound descriptions",
            "blocks": compound_blocks,
        }
    ]

    spectra_blocks = _spectrum_blocks(compounds)
    if spectra_blocks:
        sections.append(
            {
                "id": "spectra_appendix",
                "title": "Spectra appendix",
                "blocks": spectra_blocks,
            }
        )

    return {
        "title": "Supporting Information",
        "sections": sections,
        "metadata": {"compound_count": str(len(compounds))},
    }


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
