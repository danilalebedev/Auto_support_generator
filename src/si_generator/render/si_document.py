from __future__ import annotations

from typing import Any, Literal, TypedDict


DocumentBlockKind = Literal[
    "compound_description",
    "spectrum_page",
]


class DocumentBlock(TypedDict, total=False):
    kind: DocumentBlockKind
    compound_id: str
    content: Any
    nucleus: str
    image_path: str


class SISection(TypedDict, total=False):
    id: str
    title: str
    blocks: list[DocumentBlock]


class SIDocument(TypedDict, total=False):
    title: str
    sections: list[SISection]
    metadata: dict[str, str]
