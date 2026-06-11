from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", WORD_NS)


def parse_renumber_map(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise ValueError(f"Invalid renumber item '{chunk}'. Use OLD=NEW, e.g. 2a=3a.")
        old, new = [part.strip() for part in chunk.split("=", 1)]
        if not old or not new:
            raise ValueError(f"Invalid renumber item '{chunk}'. Use OLD=NEW, e.g. 2a=3a.")
        result[old] = new
    if not result:
        raise ValueError("Renumber map is empty. Use OLD=NEW, e.g. 2a=3a.")
    return result


def parse_reorder_list(text: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in text.split(",") if item.strip())


def parse_remove_list(text: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in text.split(",") if item.strip())


def renumber_manifest(manifest: dict[str, Any], renumber: dict[str, str]) -> tuple[dict[str, Any], dict[str, str]]:
    patched = json.loads(json.dumps(manifest, ensure_ascii=False))
    compounds = patched.get("compounds", {})
    applied: dict[str, str] = {}

    for compound_id, compound in compounds.items():
        if not isinstance(compound, dict):
            continue
        old_number = str(compound.get("number") or "")
        new_number = renumber.get(compound_id) or renumber.get(old_number)
        if not new_number or new_number == old_number:
            continue
        compound["number"] = new_number
        _renumber_domain_snapshot(compound, new_number)
        if compound.get("structure_placeholder"):
            compound["structure_placeholder"] = str(compound["structure_placeholder"]).replace(old_number, new_number)
        applied[old_number] = new_number

    if not applied:
        raise ValueError("None of the requested renumber keys matched manifest compound ids or numbers.")
    _raise_on_duplicate_numbers(patched)
    return patched, applied


def _renumber_domain_snapshot(compound: dict[str, Any], new_number: str) -> None:
    snapshot = compound.get("domain_snapshot")
    if isinstance(snapshot, dict):
        snapshot["number"] = new_number


def reorder_manifest(manifest: dict[str, Any], order_tokens: tuple[str, ...]) -> tuple[dict[str, Any], list[str]]:
    if not order_tokens:
        return json.loads(json.dumps(manifest, ensure_ascii=False)), []

    patched = json.loads(json.dumps(manifest, ensure_ascii=False))
    current_order = [str(item) for item in patched.get("order", [])]
    compounds = patched.get("compounds", {}) or {}
    id_by_number = {
        str(compound.get("number")): str(compound_id)
        for compound_id, compound in compounds.items()
        if isinstance(compound, dict) and compound.get("number")
    }

    resolved: list[str] = []
    for token in order_tokens:
        compound_id = token if token in compounds else id_by_number.get(token)
        if not compound_id:
            raise ValueError(f"Reorder token '{token}' does not match a compound id or number.")
        if compound_id in resolved:
            raise ValueError(f"Reorder token '{token}' resolves to duplicate compound id '{compound_id}'.")
        resolved.append(compound_id)

    missing = [compound_id for compound_id in current_order if compound_id not in resolved]
    extra = [compound_id for compound_id in resolved if compound_id not in current_order]
    if missing or extra:
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if extra:
            details.append("extra: " + ", ".join(extra))
        raise ValueError("Reorder must include every manifest compound exactly once (" + "; ".join(details) + ").")

    patched["order"] = resolved
    return patched, resolved


def remove_manifest(manifest: dict[str, Any], remove_tokens: tuple[str, ...]) -> tuple[dict[str, Any], list[str], list[str]]:
    patched = json.loads(json.dumps(manifest, ensure_ascii=False))
    if not remove_tokens:
        return patched, [], []

    compounds = patched.get("compounds", {}) or {}
    id_by_number = {
        str(compound.get("number")): str(compound_id)
        for compound_id, compound in compounds.items()
        if isinstance(compound, dict) and compound.get("number")
    }

    removed_ids: list[str] = []
    removed_bookmarks: list[str] = []
    for token in remove_tokens:
        compound_id = token if token in compounds else id_by_number.get(token)
        if not compound_id:
            raise ValueError(f"Remove token '{token}' does not match a compound id or number.")
        if compound_id in removed_ids:
            raise ValueError(f"Remove token '{token}' resolves to duplicate compound id '{compound_id}'.")
        compound = compounds.get(compound_id, {})
        if isinstance(compound, dict) and compound.get("docx_bookmark"):
            removed_bookmarks.append(str(compound["docx_bookmark"]))
        removed_ids.append(compound_id)

    patched["order"] = [compound_id for compound_id in patched.get("order", []) if str(compound_id) not in set(removed_ids)]
    for compound_id in removed_ids:
        compounds.pop(compound_id, None)
    return patched, removed_ids, removed_bookmarks


def patch_docx_numbers(input_docx: str | Path, output_docx: str | Path, renumber: dict[str, str]) -> Path:
    input_docx = Path(input_docx)
    output_docx = Path(output_docx)
    output_docx.parent.mkdir(parents=True, exist_ok=True)
    if input_docx.resolve() != output_docx.resolve():
        shutil.copy2(input_docx, output_docx)

    with zipfile.ZipFile(output_docx, "r") as source:
        document_xml = source.read("word/document.xml")
        members = {item.filename: source.read(item.filename) for item in source.infolist() if item.filename != "word/document.xml"}

    root = ET.fromstring(document_xml)
    for text_node in root.iter(f"{{{WORD_NS}}}t"):
        if text_node.text:
            text_node.text = _renumber_text(text_node.text, renumber)

    with zipfile.ZipFile(output_docx, "w", zipfile.ZIP_DEFLATED) as target:
        for name, data in members.items():
            target.writestr(name, data)
        target.writestr("word/document.xml", ET.tostring(root, encoding="utf-8", xml_declaration=True))
    return output_docx


def remove_docx_blocks(input_docx: str | Path, output_docx: str | Path, bookmark_names: list[str]) -> Path:
    if not bookmark_names:
        return Path(output_docx)

    input_docx = Path(input_docx)
    output_docx = Path(output_docx)
    output_docx.parent.mkdir(parents=True, exist_ok=True)
    if input_docx.resolve() != output_docx.resolve():
        shutil.copy2(input_docx, output_docx)

    with zipfile.ZipFile(output_docx, "r") as source:
        document_xml = source.read("word/document.xml")
        members = {item.filename: source.read(item.filename) for item in source.infolist() if item.filename != "word/document.xml"}

    root = ET.fromstring(document_xml)
    body = root.find(f"{{{WORD_NS}}}body")
    if body is None:
        raise ValueError("DOCX document body was not found.")

    ranges = _bookmark_body_ranges(body, bookmark_names)
    if len(ranges) != len(bookmark_names):
        missing = [name for name in bookmark_names if name not in ranges]
        raise ValueError("DOCX is missing bookmark ranges: " + ", ".join(missing))

    remove_indexes = {index for name in bookmark_names for index in range(ranges[name][0], ranges[name][1] + 1)}
    for index, child in enumerate(list(body)):
        if index in remove_indexes:
            body.remove(child)

    with zipfile.ZipFile(output_docx, "w", zipfile.ZIP_DEFLATED) as target:
        for name, data in members.items():
            target.writestr(name, data)
        target.writestr("word/document.xml", ET.tostring(root, encoding="utf-8", xml_declaration=True))
    return output_docx


def reorder_docx_blocks(input_docx: str | Path, output_docx: str | Path, bookmark_order: list[str]) -> Path:
    if not bookmark_order:
        return Path(output_docx)

    input_docx = Path(input_docx)
    output_docx = Path(output_docx)
    output_docx.parent.mkdir(parents=True, exist_ok=True)
    if input_docx.resolve() != output_docx.resolve():
        shutil.copy2(input_docx, output_docx)

    with zipfile.ZipFile(output_docx, "r") as source:
        document_xml = source.read("word/document.xml")
        members = {item.filename: source.read(item.filename) for item in source.infolist() if item.filename != "word/document.xml"}

    root = ET.fromstring(document_xml)
    body = root.find(f"{{{WORD_NS}}}body")
    if body is None:
        raise ValueError("DOCX document body was not found.")

    ranges = _bookmark_body_ranges(body, bookmark_order)
    if len(ranges) != len(bookmark_order):
        missing = [name for name in bookmark_order if name not in ranges]
        raise ValueError("DOCX is missing bookmark ranges: " + ", ".join(missing))

    children = list(body)
    first_index = min(start for start, _ in ranges.values())
    moving_indexes = {index for name in bookmark_order for index in range(ranges[name][0], ranges[name][1] + 1)}
    moving_blocks = {name: children[ranges[name][0] : ranges[name][1] + 1] for name in bookmark_order}

    for child in children:
        body.remove(child)

    insert_done = False
    for index, child in enumerate(children):
        if index == first_index and not insert_done:
            for name in bookmark_order:
                for item in moving_blocks[name]:
                    body.append(item)
            insert_done = True
        if index not in moving_indexes:
            body.append(child)

    with zipfile.ZipFile(output_docx, "w", zipfile.ZIP_DEFLATED) as target:
        for name, data in members.items():
            target.writestr(name, data)
        target.writestr("word/document.xml", ET.tostring(root, encoding="utf-8", xml_declaration=True))
    return output_docx


def support_docx_from_manifest(manifest: dict[str, Any], manifest_path: str | Path, override: str | Path | None = None) -> Path:
    if override:
        return Path(override)
    artifacts = manifest.get("artifacts", {}) or {}
    output_paths = manifest.get("output_paths", {}) or {}
    value = artifacts.get("support_docx") or output_paths.get("support_docx")
    if not value:
        raise ValueError("Manifest does not contain a support_docx artifact.")
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(manifest_path).resolve().parent / path


def default_patched_docx_path(source_docx: Path) -> Path:
    return source_docx.with_name(source_docx.stem + "_patched" + source_docx.suffix)


def write_patched_manifest(manifest: dict[str, Any], output_manifest: str | Path) -> Path:
    output_manifest = Path(output_manifest)
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_manifest


def set_manifest_output_paths(manifest: dict[str, Any], *, support_docx: str | Path, manifest_path: str | Path) -> dict[str, Any]:
    manifest.setdefault("artifacts", {})["support_docx"] = str(Path(support_docx))
    manifest.setdefault("artifacts", {})["manifest"] = str(Path(manifest_path))
    manifest.setdefault("output_paths", {})["support_docx"] = str(Path(support_docx))
    manifest.setdefault("output_paths", {})["manifest"] = str(Path(manifest_path))
    return manifest


def bookmark_order_for_compounds(manifest: dict[str, Any], compound_ids: list[str]) -> list[str]:
    compounds = manifest.get("compounds", {}) or {}
    return [
        str(compounds[compound_id]["docx_bookmark"])
        for compound_id in compound_ids
        if isinstance(compounds.get(compound_id), dict) and compounds[compound_id].get("docx_bookmark")
    ]


def _renumber_text(text: str, renumber: dict[str, str]) -> str:
    result = text
    for old, new in renumber.items():
        result = result.replace(f"({old})", f"({new})")
        result = result.replace(f"STRUCTURE:{old}", f"STRUCTURE:{new}")
        result = result.replace(f"SPECTRUM_STRUCTURE:{old}:", f"SPECTRUM_STRUCTURE:{new}:")
        result = result.replace(f"MNOVA:{old}:", f"MNOVA:{new}:")
    return result


def _raise_on_duplicate_numbers(manifest: dict[str, Any]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for compound in (manifest.get("compounds", {}) or {}).values():
        if not isinstance(compound, dict):
            continue
        number = str(compound.get("number") or "")
        if not number:
            continue
        if number in seen:
            duplicates.add(number)
        seen.add(number)
    if duplicates:
        raise ValueError("Renumbering would create duplicate compound numbers: " + ", ".join(sorted(duplicates)))


def _bookmark_body_ranges(body, bookmark_names: list[str]) -> dict[str, tuple[int, int]]:
    wanted = set(bookmark_names)
    starts: dict[str, int] = {}
    ends_by_id: dict[str, int] = {}
    names_by_id: dict[str, str] = {}
    name_attr = f"{{{WORD_NS}}}name"
    id_attr = f"{{{WORD_NS}}}id"

    for index, child in enumerate(list(body)):
        for item in child.iter(f"{{{WORD_NS}}}bookmarkStart"):
            name = str(item.attrib.get(name_attr, ""))
            if name in wanted:
                starts[name] = index
                names_by_id[str(item.attrib.get(id_attr, ""))] = name
        for item in child.iter(f"{{{WORD_NS}}}bookmarkEnd"):
            name = names_by_id.get(str(item.attrib.get(id_attr, "")))
            if name in wanted:
                ends_by_id[name] = index
    return {name: (starts[name], ends_by_id[name]) for name in wanted if name in starts and name in ends_by_id}
