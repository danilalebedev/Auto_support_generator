from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..config_yaml import parse_simple_yaml
from .types import Reference, ReferenceStore


def empty_reference_store() -> ReferenceStore:
    return {"references": {}, "order": []}


def parse_reference_keys(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list | tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in re.split(r"[,;]", str(value)) if part.strip()]


def load_reference_store(path: str | Path | None = None) -> ReferenceStore:
    if not path:
        return empty_reference_store()
    source = Path(path)
    data = parse_simple_yaml(source.read_text(encoding="utf-8-sig"))
    raw_references = data.get("references", data)
    if not isinstance(raw_references, dict):
        raise ValueError(f"References file must contain a mapping: {source}")

    references: dict[str, Reference] = {}
    for key, raw_reference in raw_references.items():
        if key == "order":
            continue
        if not isinstance(raw_reference, dict):
            raise ValueError(f"Reference '{key}' must be a mapping in {source}")
        reference: Reference = {str(field): value for field, value in raw_reference.items()}
        reference["key"] = str(key)
        reference["authors"] = _normalize_authors(reference.get("authors", []))
        references[str(key)] = reference

    order = parse_reference_keys(data.get("order", [])) or list(references)
    order = [key for key in order if key in references]
    for key in references:
        if key not in order:
            order.append(key)
    return {"references": references, "order": order}


def select_references_for_compounds(reference_store: ReferenceStore, compound_reference_keys: list[list[str]]) -> list[Reference]:
    references = reference_store.get("references", {})
    selected_keys: list[str] = []
    for keys in compound_reference_keys:
        for key in keys:
            if key in references and key not in selected_keys:
                selected_keys.append(key)
    if not selected_keys:
        selected_keys = [key for key in reference_store.get("order", []) if key in references]
    return [references[key] for key in selected_keys]


def format_reference(reference: Reference, index: int) -> str:
    parts: list[str] = []
    authors = reference.get("authors", [])
    if authors:
        parts.append(", ".join(str(author) for author in authors))
    if reference.get("title"):
        parts.append(str(reference["title"]))

    journal_parts: list[str] = []
    if reference.get("journal"):
        journal_parts.append(str(reference["journal"]))
    if reference.get("year"):
        journal_parts.append(str(reference["year"]))
    if reference.get("volume"):
        journal_parts.append(str(reference["volume"]))
    if reference.get("pages"):
        journal_parts.append(str(reference["pages"]))
    if journal_parts:
        parts.append(", ".join(journal_parts))
    if reference.get("doi"):
        parts.append(f"DOI: {reference['doi']}")
    cleaned_parts = [_clean_sentence_part(part) for part in parts if _clean_sentence_part(part)]
    return f"[{index}] " + ". ".join(cleaned_parts).rstrip(".") + "."


def _normalize_authors(value: Any) -> list[str]:
    if isinstance(value, list | tuple):
        return [str(author).strip() for author in value if str(author).strip()]
    if not value:
        return []
    return [author.strip() for author in re.split(r"\s*;\s*", str(value)) if author.strip()]


def _clean_sentence_part(value: Any) -> str:
    return str(value).strip().rstrip(".")
