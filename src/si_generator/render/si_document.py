from __future__ import annotations

from typing import Any, Literal, TypedDict


DocumentBlockKind = Literal[
    "compound_description",
    "spectrum_page",
    "reference",
]


class DocumentBlock(TypedDict, total=False):
    kind: DocumentBlockKind
    block_id: str
    compound_id: str
    display_number: str
    title_text: str
    content: Any
    structure_placeholder: str
    nucleus: str
    embed_mode: str
    image_path: str
    mnova_path: str
    expected_artifact_path: str


class SISection(TypedDict, total=False):
    id: str
    title: str
    blocks: list[DocumentBlock]


class SIDocument(TypedDict, total=False):
    title: str
    sections: list[SISection]
    metadata: dict[str, str]
