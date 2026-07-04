from __future__ import annotations

import json
import posixpath
import re
import shutil
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from ...domain.bookmarks import bookmark_name_for_block_id
from ...domain.issues import compound_issue_counts, count_issues
from ...domain.manifest import load_manifest, manifest_has_errors
from ...domain.patching import set_manifest_output_paths, support_docx_from_manifest
from ...domain.requests import GenerateSIRequest
from ...input_table import read_compounds
from ...word_input import read_word_compounds
from ..state import AddCompoundsState


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_ATTRS = (
    f"{{{OFFICE_REL_NS}}}id",
    f"{{{OFFICE_REL_NS}}}embed",
    f"{{{OFFICE_REL_NS}}}link",
)

ET.register_namespace("w", WORD_NS)
ET.register_namespace("r", OFFICE_REL_NS)
ET.register_namespace("rel", REL_NS)
ET.register_namespace("ct", CONTENT_TYPES_NS)


def load_add_manifest_node(state: AddCompoundsState) -> dict:
    request = state["request"]
    artifacts = {**state.get("artifacts", {}), "source_manifest": str(request.manifest_path)}
    try:
        manifest = load_manifest(request.manifest_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        issues = [
            *state.get("issues", []),
            _issue(
                "MANIFEST_LOAD_FAILED",
                "error",
                f"could not load manifest: {exc}",
                path=str(request.manifest_path),
            ),
        ]
        return {"manifest": {}, "artifacts": artifacts, "issues": issues, "status": "fail"}
    return {"manifest": manifest, "artifacts": artifacts}


def read_new_compounds_node(state: AddCompoundsState) -> dict:
    request = state["request"]
    try:
        if request.input_kind == "word":
            compounds = read_word_compounds(request.input_path, extract_structure_metadata=False)
        else:
            compounds = read_compounds(request.input_path)
    except Exception as exc:
        issues = [
            *state.get("issues", []),
            _issue("ADD_COMPOUNDS_INPUT_READ_FAILED", "error", f"could not read new compound table: {exc}", path=str(request.input_path)),
        ]
        return {"new_compounds": [], "issues": issues, "status": "fail"}
    return {"new_compounds": compounds, "artifacts": {**state.get("artifacts", {}), "new_compound_table": str(request.input_path)}}


def check_duplicate_compound_numbers_node(state: AddCompoundsState) -> dict:
    issues = list(state.get("issues", []))
    if manifest_has_errors(issues):
        return {"issues": issues, "status": "fail"}

    existing_numbers = _manifest_numbers(state.get("manifest", {}))
    duplicate_numbers = sorted(
        {
            compound.number.strip()
            for compound in state.get("new_compounds", [])
            if compound.number.strip() and compound.number.strip() in existing_numbers
        }
    )
    if not duplicate_numbers:
        return {"issues": issues}

    issues.extend(
        _issue(
            "DUPLICATE_COMPOUND_NUMBER",
            "error",
            f"new compound number '{number}' already exists in the manifest.",
            compound_id=existing_numbers[number],
        )
        for number in duplicate_numbers
    )
    return {
        "issues": issues,
        "status": "fail",
        "add_result": {
            "duplicate_numbers": duplicate_numbers,
            "added_ids": [],
            "generated_support_docx": "",
        },
    }


def generate_new_support_node(state: AddCompoundsState) -> dict:
    issues = list(state.get("issues", []))
    if manifest_has_errors(issues):
        return {"issues": issues, "status": "fail"}

    request = state["request"]
    temp_dir = request.output_docx.parent / "_add_compounds_work" / (state.get("run_id") or "run")
    temp_output = temp_dir / "new_compounds.docx"
    temp_dir.mkdir(parents=True, exist_ok=True)

    generate_request = GenerateSIRequest(
        input_path=request.input_path,
        input_kind=request.input_kind,
        output_path=temp_output,
        template_docx=request.template_docx,
        references_path=request.references_path,
        spectra_source=request.resolved_spectra_source,
        mnova_exe=request.mnova_exe,
        mnova_graphics_profile=request.mnova_graphics_profile,
        no_extract_nmr=request.no_extract_nmr,
        insert_spectra_as=request.insert_spectra_as,
        target_signal_height_fraction=request.target_signal_height_fraction,
        peak_threshold_fraction=request.peak_threshold_fraction,
        peak_threshold_fraction_1h=request.peak_threshold_fraction_1h,
        peak_threshold_fraction_13c=request.peak_threshold_fraction_13c,
        baseline_mode=request.baseline_mode,
        baseline_apply_1h=request.baseline_apply_1h,
        baseline_apply_13c=request.baseline_apply_13c,
        baseline_poly_order=request.baseline_poly_order,
        whittaker_lambda=request.whittaker_lambda,
        whittaker_asymmetry=request.whittaker_asymmetry,
        generate_loadings=request.generate_loadings,
        calculate_elemental_analysis=request.calculate_elemental_analysis,
        no_check_support=request.no_check_support,
    )

    from ...workflows.generate_si import output_path_from_state, run_generate_si

    generated_state = run_generate_si(generate_request)
    generated_output = output_path_from_state(generated_state)
    artifacts = {
        **state.get("artifacts", {}),
        "generated_support_docx": str(generated_output),
    }
    if generated_state.get("artifacts", {}).get("manifest"):
        artifacts["generated_manifest"] = generated_state["artifacts"]["manifest"]
    issues.extend(generated_state.get("issues", []))
    if manifest_has_errors(generated_state.get("issues", [])):
        issues.append(
            _issue(
                "ADD_COMPOUNDS_GENERATION_FAILED",
                "error",
                "new compound generation reported errors; existing support was not patched.",
                path=str(generated_output),
            )
        )
        return {"new_generate_state": generated_state, "artifacts": artifacts, "issues": issues, "status": "fail"}
    return {"new_generate_state": generated_state, "artifacts": artifacts, "issues": issues}


def append_new_blocks_node(state: AddCompoundsState) -> dict:
    issues = list(state.get("issues", []))
    if manifest_has_errors(issues):
        return {"issues": issues, "status": "fail"}

    request = state["request"]
    output_docx = Path(request.output_docx)
    output_docx.parent.mkdir(parents=True, exist_ok=True)
    try:
        source_docx = support_docx_from_manifest(state.get("manifest", {}), request.manifest_path, request.support_docx)
        generated_docx = Path(state.get("artifacts", {}).get("generated_support_docx", ""))
        if not source_docx.exists():
            raise FileNotFoundError(source_docx)
        if not generated_docx.exists():
            raise FileNotFoundError(generated_docx)
        if source_docx.resolve() == output_docx.resolve():
            issues.append(
                _issue(
                    "ADD_COMPOUNDS_IN_PLACE_OUTPUT",
                    "error",
                    "output DOCX must be different from the existing support DOCX.",
                    path=str(output_docx),
                )
            )
            return {"issues": issues, "status": "fail"}
        generated_manifest = _generated_manifest(state)
        id_map = _new_compound_id_map(state.get("manifest", {}), generated_manifest)
        _append_generated_docx_blocks(
            source_docx,
            generated_docx,
            output_docx,
            old_manifest=state.get("manifest", {}),
            new_manifest=generated_manifest,
            id_map=id_map,
        )
    except Exception as exc:
        issues.append(
            _issue(
                "ADD_COMPOUNDS_DOCX_APPEND_FAILED",
                "error",
                f"could not append new compound blocks: {exc}",
                path=str(output_docx),
            )
        )
        return {"issues": issues, "status": "fail"}

    return {"artifacts": {**state.get("artifacts", {}), "support_docx": str(output_docx)}, "issues": issues, "add_id_map": id_map}


def write_add_manifest_node(state: AddCompoundsState) -> dict:
    issues = list(state.get("issues", []))
    if manifest_has_errors(issues):
        return {"issues": issues, "status": "fail"}

    request = state["request"]
    output_docx = Path(request.output_docx)
    output_manifest = output_docx.with_suffix(".manifest.json")
    generated_manifest = _generated_manifest(state)
    id_map = state.get("add_id_map") or _new_compound_id_map(state.get("manifest", {}), generated_manifest)
    merged_manifest, add_result = _merge_manifest(
        state.get("manifest", {}),
        generated_manifest,
        id_map=id_map,
        run_id=state.get("run_id", ""),
        source_manifest=request.manifest_path,
        output_docx=output_docx,
        output_manifest=output_manifest,
    )
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(json.dumps(merged_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts = {
        **state.get("artifacts", {}),
        "manifest": str(output_manifest),
    }
    return {"manifest": merged_manifest, "add_result": add_result, "artifacts": artifacts}


def write_add_compounds_report_node(state: AddCompoundsState) -> dict:
    request = state["request"]
    output_docx = Path(request.output_docx)
    report_path = output_docx.with_suffix(".add_report.json")
    issues = list(state.get("issues", []))
    status = "fail" if manifest_has_errors(issues) or state.get("status") == "fail" else "pass"
    report = {
        "run_id": state.get("run_id", ""),
        "status": status,
        "source_manifest": str(request.manifest_path),
        "source_support_docx": str(request.support_docx) if request.support_docx else "",
        "new_compound_table": str(request.input_path),
        "output_docx": str(output_docx),
        "strict_artifacts": request.strict_artifacts,
        "add_result": state.get("add_result", _empty_add_result()),
        "issue_counts": count_issues(issues),
        "compound_issue_counts": compound_issue_counts(issues),
        "issues": issues,
        "artifacts": {**state.get("artifacts", {}), "add_report": str(report_path)},
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": status, "issues": issues, "artifacts": report["artifacts"]}


def route_add_compounds_after_load(state: AddCompoundsState) -> str:
    return "fail" if manifest_has_errors(state.get("issues", [])) or state.get("status") == "fail" else "continue"


def route_add_compounds_after_duplicate_check(state: AddCompoundsState) -> str:
    return "fail" if manifest_has_errors(state.get("issues", [])) or state.get("status") == "fail" else "continue"


def route_add_compounds_after_generation(state: AddCompoundsState) -> str:
    return "fail" if manifest_has_errors(state.get("issues", [])) or state.get("status") == "fail" else "continue"


def _append_generated_docx_blocks(
    source_docx: Path,
    generated_docx: Path,
    output_docx: Path,
    *,
    old_manifest: dict[str, Any],
    new_manifest: dict[str, Any],
    id_map: dict[str, str] | None = None,
) -> None:
    if source_docx.resolve() != output_docx.resolve():
        shutil.copy2(source_docx, output_docx)

    id_map = id_map or _new_compound_id_map(old_manifest, new_manifest)
    bookmark_name_map = _bookmark_name_map(id_map)
    temp_docx = output_docx.with_name(f".{output_docx.name}.add_compounds.tmp")
    temp_docx.unlink(missing_ok=True)

    try:
        with zipfile.ZipFile(output_docx, "r") as target_zip, zipfile.ZipFile(generated_docx, "r") as source_zip:
            target_document = ET.fromstring(target_zip.read("word/document.xml"))
            target_rels = _read_xml_or_empty(target_zip, "word/_rels/document.xml.rels", f"{{{REL_NS}}}Relationships")
            target_content_types = ET.fromstring(target_zip.read("[Content_Types].xml"))
            source_document = ET.fromstring(source_zip.read("word/document.xml"))
            source_rels = _read_xml_or_empty(source_zip, "word/_rels/document.xml.rels", f"{{{REL_NS}}}Relationships")
            source_content_types = ET.fromstring(source_zip.read("[Content_Types].xml"))
            target_body = _document_body(target_document)
            source_body = _document_body(source_document)
            existing_names = set(target_zip.namelist())

            source_ranges = _bookmark_body_ranges(source_body)
            source_children = list(source_body)
            compound_elements = _compound_range_elements(source_children, source_ranges, new_manifest)
            spectrum_elements = _spectrum_range_elements(source_children, source_ranges, new_manifest)

            extra_files: dict[str, bytes] = {}
            rel_counter = _next_rel_counter(target_rels)
            bookmark_counter = _next_bookmark_id(target_body)
            compound_elements, rel_counter, bookmark_counter = _prepare_inserted_elements(
                compound_elements,
                source_zip=source_zip,
                source_rels=source_rels,
                source_content_types=source_content_types,
                target_rels=target_rels,
                target_content_types=target_content_types,
                existing_names=existing_names,
                extra_files=extra_files,
                rel_counter=rel_counter,
                bookmark_counter=bookmark_counter,
                bookmark_name_map=bookmark_name_map,
            )
            spectrum_elements, rel_counter, bookmark_counter = _prepare_inserted_elements(
                spectrum_elements,
                source_zip=source_zip,
                source_rels=source_rels,
                source_content_types=source_content_types,
                target_rels=target_rels,
                target_content_types=target_content_types,
                existing_names=existing_names,
                extra_files=extra_files,
                rel_counter=rel_counter,
                bookmark_counter=bookmark_counter,
                bookmark_name_map=bookmark_name_map,
            )

            if compound_elements:
                _insert_body_elements(target_body, _compound_insert_index(target_body, old_manifest), compound_elements)
            if spectrum_elements:
                _insert_body_elements(target_body, _spectra_insert_index(target_body), spectrum_elements)

            with zipfile.ZipFile(temp_docx, "w", zipfile.ZIP_DEFLATED) as target_out:
                replaced = {"word/document.xml", "word/_rels/document.xml.rels", "[Content_Types].xml"}
                for item in target_zip.infolist():
                    if item.filename in replaced:
                        continue
                    target_out.writestr(item, target_zip.read(item.filename))
                target_out.writestr("word/document.xml", ET.tostring(target_document, encoding="utf-8", xml_declaration=True))
                target_out.writestr("word/_rels/document.xml.rels", ET.tostring(target_rels, encoding="utf-8", xml_declaration=True))
                target_out.writestr("[Content_Types].xml", ET.tostring(target_content_types, encoding="utf-8", xml_declaration=True))
                for name, data in extra_files.items():
                    target_out.writestr(name, data)
        temp_docx.replace(output_docx)
    finally:
        temp_docx.unlink(missing_ok=True)


def _generated_manifest(state: AddCompoundsState) -> dict[str, Any]:
    generated_state = state.get("new_generate_state", {})
    if isinstance(generated_state, dict) and isinstance(generated_state.get("manifest"), dict):
        return generated_state["manifest"]
    manifest_path = state.get("artifacts", {}).get("generated_manifest")
    if manifest_path:
        return load_manifest(manifest_path)
    return {}


def _merge_manifest(
    old_manifest: dict[str, Any],
    new_manifest: dict[str, Any],
    *,
    id_map: dict[str, str],
    run_id: str,
    source_manifest: Path,
    output_docx: Path,
    output_manifest: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    merged = deepcopy(old_manifest)
    merged.setdefault("order", [])
    merged.setdefault("compounds", {})
    added_ids: list[str] = []

    for new_id in new_manifest.get("order", []):
        raw_entry = (new_manifest.get("compounds", {}) or {}).get(new_id)
        if not isinstance(raw_entry, dict):
            continue
        merged_id = id_map.get(str(new_id), str(new_id))
        entry = deepcopy(raw_entry)
        entry["id"] = merged_id
        entry["docx_block_id"] = f"compound:{merged_id}"
        entry["docx_bookmark"] = bookmark_name_for_block_id(f"compound:{merged_id}")
        entry.pop("relative_artifacts", None)
        snapshot = entry.get("domain_snapshot")
        if isinstance(snapshot, dict):
            snapshot["id"] = merged_id
        merged["compounds"][merged_id] = entry
        merged["order"].append(merged_id)
        added_ids.append(merged_id)

    set_manifest_output_paths(merged, support_docx=output_docx, manifest_path=output_manifest)
    history = merged.setdefault("add_compounds_history", [])
    if not isinstance(history, list):
        merged["add_compounds_history"] = history = []
    add_result = {
        "added_ids": added_ids,
        "duplicate_numbers": [],
        "generated_support_docx": new_manifest.get("output_paths", {}).get("support_docx")
        or new_manifest.get("artifacts", {}).get("support_docx", ""),
    }
    history.append(
        {
            "run_id": run_id,
            "source_manifest": str(source_manifest),
            "output_manifest": str(output_manifest),
            "output_docx": str(output_docx),
            "result": add_result,
        }
    )
    return merged, add_result


def _new_compound_id_map(old_manifest: dict[str, Any], new_manifest: dict[str, Any]) -> dict[str, str]:
    existing_ids = {str(item) for item in (old_manifest.get("compounds", {}) or {})}
    id_map: dict[str, str] = {}
    for new_id in new_manifest.get("order", []):
        new_id = str(new_id)
        merged_id = _unique_compound_id(new_id, existing_ids)
        existing_ids.add(merged_id)
        id_map[new_id] = merged_id
    return id_map


def _bookmark_name_map(id_map: dict[str, str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for source_id, target_id in id_map.items():
        mapping[bookmark_name_for_block_id(f"compound:{source_id}")] = bookmark_name_for_block_id(f"compound:{target_id}")
        for nucleus in ("1H", "13C"):
            mapping[bookmark_name_for_block_id(f"spectrum:{source_id}:{nucleus}")] = bookmark_name_for_block_id(
                f"spectrum:{target_id}:{nucleus}"
            )
    return mapping


def _manifest_numbers(manifest: dict[str, Any]) -> dict[str, str]:
    numbers: dict[str, str] = {}
    for compound_id, compound in (manifest.get("compounds", {}) or {}).items():
        if not isinstance(compound, dict):
            continue
        number = str(compound.get("number") or "").strip()
        if number:
            numbers[number] = str(compound_id)
    return numbers


def _unique_compound_id(base_id: str, existing_ids: set[str]) -> str:
    candidate = base_id or "compound"
    if candidate not in existing_ids:
        return candidate
    counter = 1
    while f"added_{candidate}_{counter}" in existing_ids:
        counter += 1
    return f"added_{candidate}_{counter}"


def _read_xml_or_empty(archive: zipfile.ZipFile, name: str, tag: str) -> ET.Element:
    try:
        return ET.fromstring(archive.read(name))
    except KeyError:
        return ET.Element(tag)


def _document_body(document: ET.Element) -> ET.Element:
    body = document.find(f"{{{WORD_NS}}}body")
    if body is None:
        raise ValueError("DOCX document body was not found.")
    return body


def _bookmark_body_ranges(body: ET.Element) -> dict[str, tuple[int, int]]:
    starts: dict[str, int] = {}
    ends_by_id: dict[str, int] = {}
    names_by_id: dict[str, str] = {}
    name_attr = f"{{{WORD_NS}}}name"
    id_attr = f"{{{WORD_NS}}}id"

    for index, child in enumerate(list(body)):
        for item in child.iter(f"{{{WORD_NS}}}bookmarkStart"):
            name = str(item.attrib.get(name_attr, ""))
            if name:
                starts[name] = index
                names_by_id[str(item.attrib.get(id_attr, ""))] = name
        for item in child.iter(f"{{{WORD_NS}}}bookmarkEnd"):
            name = names_by_id.get(str(item.attrib.get(id_attr, "")))
            if name:
                ends_by_id[name] = index
    return {name: (starts[name], ends_by_id[name]) for name in starts if name in ends_by_id}


def _compound_range_elements(
    source_children: list[ET.Element],
    source_ranges: dict[str, tuple[int, int]],
    new_manifest: dict[str, Any],
) -> list[ET.Element]:
    elements: list[ET.Element] = []
    for compound_id in new_manifest.get("order", []):
        compound = (new_manifest.get("compounds", {}) or {}).get(str(compound_id), {})
        bookmark = str(compound.get("docx_bookmark") or bookmark_name_for_block_id(f"compound:{compound_id}"))
        if bookmark in source_ranges:
            elements.extend(_range_elements(source_children, source_ranges[bookmark]))
    return elements


def _spectrum_range_elements(
    source_children: list[ET.Element],
    source_ranges: dict[str, tuple[int, int]],
    new_manifest: dict[str, Any],
) -> list[ET.Element]:
    elements: list[ET.Element] = []
    for compound_id in new_manifest.get("order", []):
        for nucleus in ("1H", "13C"):
            bookmark = bookmark_name_for_block_id(f"spectrum:{compound_id}:{nucleus}")
            if bookmark in source_ranges:
                elements.extend(_range_elements(source_children, source_ranges[bookmark], include_previous_page_break=True))
    return elements


def _range_elements(
    children: list[ET.Element],
    body_range: tuple[int, int],
    *,
    include_previous_page_break: bool = False,
) -> list[ET.Element]:
    start, end = body_range
    if include_previous_page_break and start > 0 and _has_page_break(children[start - 1]):
        start -= 1
    return [deepcopy(child) for child in children[start : end + 1]]


def _has_page_break(element: ET.Element) -> bool:
    return any(item.attrib.get(f"{{{WORD_NS}}}type") == "page" for item in element.iter(f"{{{WORD_NS}}}br"))


def _prepare_inserted_elements(
    elements: list[ET.Element],
    *,
    source_zip: zipfile.ZipFile,
    source_rels: ET.Element,
    source_content_types: ET.Element,
    target_rels: ET.Element,
    target_content_types: ET.Element,
    existing_names: set[str],
    extra_files: dict[str, bytes],
    rel_counter: int,
    bookmark_counter: int,
    bookmark_name_map: dict[str, str],
) -> tuple[list[ET.Element], int, int]:
    rels_by_id = {rel.attrib.get("Id", ""): rel for rel in source_rels}
    rel_id_map: dict[str, str] = {}
    bookmark_counter = _remap_bookmarks(elements, bookmark_name_map, bookmark_counter)
    for element in elements:
        for child in element.iter():
            for attr in REL_ATTRS:
                source_rel_id = child.attrib.get(attr)
                if not source_rel_id or source_rel_id not in rels_by_id:
                    continue
                if source_rel_id not in rel_id_map:
                    new_rel_id, rel_counter = _copy_relationship(
                        rels_by_id[source_rel_id],
                        source_zip=source_zip,
                        source_content_types=source_content_types,
                        target_rels=target_rels,
                        target_content_types=target_content_types,
                        existing_names=existing_names,
                        extra_files=extra_files,
                        rel_counter=rel_counter,
                    )
                    rel_id_map[source_rel_id] = new_rel_id
                child.set(attr, rel_id_map[source_rel_id])
    return elements, rel_counter, bookmark_counter


def _remap_bookmarks(elements: list[ET.Element], bookmark_name_map: dict[str, str], bookmark_counter: int) -> int:
    id_attr = f"{{{WORD_NS}}}id"
    name_attr = f"{{{WORD_NS}}}name"
    id_map: dict[str, str] = {}
    for element in elements:
        for item in element.iter():
            if item.tag == f"{{{WORD_NS}}}bookmarkStart":
                old_id = str(item.attrib.get(id_attr, ""))
                new_id = str(bookmark_counter)
                bookmark_counter += 1
                id_map[old_id] = new_id
                item.set(id_attr, new_id)
                name = str(item.attrib.get(name_attr, ""))
                if name in bookmark_name_map:
                    item.set(name_attr, bookmark_name_map[name])
    for element in elements:
        for item in element.iter():
            if item.tag == f"{{{WORD_NS}}}bookmarkEnd":
                old_id = str(item.attrib.get(id_attr, ""))
                if old_id in id_map:
                    item.set(id_attr, id_map[old_id])
    return bookmark_counter


def _copy_relationship(
    source_rel: ET.Element,
    *,
    source_zip: zipfile.ZipFile,
    source_content_types: ET.Element,
    target_rels: ET.Element,
    target_content_types: ET.Element,
    existing_names: set[str],
    extra_files: dict[str, bytes],
    rel_counter: int,
) -> tuple[str, int]:
    rel_type = str(source_rel.attrib.get("Type", ""))
    source_target = str(source_rel.attrib.get("Target", ""))
    target_mode = source_rel.attrib.get("TargetMode")
    rel_id = f"rIdAdd{rel_counter}"
    rel_counter += 1

    if target_mode == "External":
        _add_relationship(target_rels, rel_id, rel_type, source_target, target_mode=target_mode)
        return rel_id, rel_counter

    source_part = _relationship_target_part(source_target)
    if source_part not in source_zip.namelist():
        _add_relationship(target_rels, rel_id, rel_type, source_target)
        return rel_id, rel_counter

    target_part = _unique_target_part(source_part, existing_names)
    existing_names.add(target_part)
    extra_files[target_part] = source_zip.read(source_part)
    _copy_content_type(source_content_types, target_content_types, source_part, target_part)
    _add_relationship(target_rels, rel_id, rel_type, target_part.removeprefix("word/"))
    return rel_id, rel_counter


def _relationship_target_part(target: str) -> str:
    normalized = posixpath.normpath(posixpath.join("word", target))
    if normalized.startswith("../"):
        return normalized.removeprefix("../")
    return normalized


def _unique_target_part(source_part: str, existing_names: set[str]) -> str:
    folder, name = posixpath.split(source_part)
    stem, ext = posixpath.splitext(name)
    prefix = "add_compounds"
    counter = 1
    while True:
        candidate = posixpath.join(folder or "word", f"{prefix}_{counter}{ext or '.bin'}")
        if candidate not in existing_names:
            return candidate
        counter += 1


def _copy_content_type(source_content_types: ET.Element, target_content_types: ET.Element, source_part: str, target_part: str) -> None:
    source_part_name = "/" + source_part
    target_part_name = "/" + target_part
    for override in source_content_types.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
        if override.attrib.get("PartName") == source_part_name:
            _ensure_override_content_type(target_content_types, target_part_name, str(override.attrib.get("ContentType", "")))
            return

    extension = Path(source_part).suffix.lower().lstrip(".")
    for default in source_content_types.findall(f"{{{CONTENT_TYPES_NS}}}Default"):
        if default.attrib.get("Extension", "").lower() == extension:
            _ensure_default_content_type(target_content_types, extension, str(default.attrib.get("ContentType", "")))
            return
    if extension:
        _ensure_default_content_type(target_content_types, extension, _fallback_content_type(extension))


def _ensure_override_content_type(content_types: ET.Element, part_name: str, content_type: str) -> None:
    if not content_type:
        return
    for override in content_types.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
        if override.attrib.get("PartName") == part_name:
            return
    override = ET.SubElement(content_types, f"{{{CONTENT_TYPES_NS}}}Override")
    override.set("PartName", part_name)
    override.set("ContentType", content_type)


def _ensure_default_content_type(content_types: ET.Element, extension: str, content_type: str) -> None:
    if not extension or not content_type:
        return
    for default in content_types.findall(f"{{{CONTENT_TYPES_NS}}}Default"):
        if default.attrib.get("Extension", "").lower() == extension.lower():
            return
    default = ET.SubElement(content_types, f"{{{CONTENT_TYPES_NS}}}Default")
    default.set("Extension", extension)
    default.set("ContentType", content_type)


def _fallback_content_type(extension: str) -> str:
    if extension == "png":
        return "image/png"
    if extension in {"jpg", "jpeg"}:
        return "image/jpeg"
    if extension == "emf":
        return "image/x-emf"
    if extension == "bin":
        return "application/vnd.openxmlformats-officedocument.oleObject"
    return "application/octet-stream"


def _add_relationship(rels: ET.Element, rel_id: str, rel_type: str, target: str, *, target_mode: str | None = None) -> None:
    rel = ET.SubElement(rels, f"{{{REL_NS}}}Relationship")
    rel.set("Id", rel_id)
    rel.set("Type", rel_type)
    rel.set("Target", target)
    if target_mode:
        rel.set("TargetMode", target_mode)


def _next_rel_counter(rels: ET.Element) -> int:
    max_id = 0
    for rel in rels:
        match = re.fullmatch(r"rId(?:Add|Mnova|SI)?(\d+)", str(rel.attrib.get("Id", "")))
        if match:
            max_id = max(max_id, int(match.group(1)))
    return max_id + 1


def _next_bookmark_id(body: ET.Element) -> int:
    max_id = 0
    id_attr = f"{{{WORD_NS}}}id"
    for item in body.iter():
        if item.tag in {f"{{{WORD_NS}}}bookmarkStart", f"{{{WORD_NS}}}bookmarkEnd"}:
            try:
                max_id = max(max_id, int(item.attrib.get(id_attr, "0")))
            except ValueError:
                continue
    return max_id + 1


def _compound_insert_index(body: ET.Element, manifest: dict[str, Any]) -> int:
    ranges = _bookmark_body_ranges(body)
    bookmarks = []
    for compound_id in manifest.get("order", []):
        compound = (manifest.get("compounds", {}) or {}).get(str(compound_id), {})
        bookmark = str(compound.get("docx_bookmark") or "")
        if bookmark in ranges:
            bookmarks.append(bookmark)
    if bookmarks:
        return ranges[bookmarks[-1]][1] + 1
    for index, child in enumerate(list(body)):
        for item in child.iter(f"{{{WORD_NS}}}bookmarkStart"):
            if str(item.attrib.get(f"{{{WORD_NS}}}name", "")).startswith("asig_spectrum_"):
                return index
    return _before_section_properties_index(body)


def _spectra_insert_index(body: ET.Element) -> int:
    children = list(body)
    for index, child in enumerate(children):
        for item in child.iter(f"{{{WORD_NS}}}bookmarkStart"):
            if str(item.attrib.get(f"{{{WORD_NS}}}name", "")).startswith("asig_reference_"):
                return index
    return _before_section_properties_index(body)


def _before_section_properties_index(body: ET.Element) -> int:
    children = list(body)
    if children and children[-1].tag == f"{{{WORD_NS}}}sectPr":
        return len(children) - 1
    return len(children)


def _insert_body_elements(body: ET.Element, index: int, elements: list[ET.Element]) -> None:
    for offset, element in enumerate(elements):
        body.insert(index + offset, element)


def _empty_add_result() -> dict[str, Any]:
    return {
        "added_ids": [],
        "duplicate_numbers": [],
        "generated_support_docx": "",
    }


def _issue(
    code: str,
    severity: str,
    message: str,
    *,
    compound_id: str = "",
    path: str = "",
) -> dict[str, str]:
    issue = {"code": code, "severity": severity, "message": message}
    if compound_id:
        issue["compound_id"] = compound_id
    if path:
        issue["path"] = path
    return issue
