from __future__ import annotations

import json
import uuid
from pathlib import Path

from ...domain.issues import compound_issue_counts, count_issues
from ...domain.manifest import check_manifest, load_manifest, manifest_has_errors
from ...domain.patching import (
    bookmark_order_for_compounds,
    existing_docx_bookmarks,
    patch_docx_numbers,
    renumber_manifest,
    remove_docx_blocks,
    remove_manifest,
    reorder_docx_blocks,
    reorder_manifest,
    selected_patch_operation,
    set_manifest_output_paths,
    spectrum_bookmark_order_for_compounds,
    support_docx_from_manifest,
    swap_manifest,
    write_patched_manifest,
)
from ...output_layout import prepare_output_layout
from ..state import PatchSIState


def prepare_patch_output_layout_node(state: PatchSIState) -> dict:
    request = state["request"]
    try:
        operation = selected_patch_operation(request)
    except ValueError:
        operation = "invalid"
    output_base = _patch_output_base(request)
    dirs = prepare_output_layout(
        output_base,
        input_path=Path(f"patch_{operation}.json"),
        run_id=state.get("run_id", "patch"),
    )
    output_docx = dirs["docx_dir"] / "support_information.docx"
    output_manifest = dirs["docx_dir"] / "support_information.manifest.json"
    artifacts = {
        **state.get("artifacts", {}),
        **{key: str(value) for key, value in dirs.items()},
        "support_docx": str(output_docx),
        "manifest": str(output_manifest),
        "source_manifest": str(request.manifest_path),
    }
    return {"artifacts": artifacts}


def load_patch_manifest_node(state: PatchSIState) -> dict:
    request = state["request"]
    artifacts = {**state.get("artifacts", {}), "source_manifest": str(request.manifest_path)}
    try:
        manifest = load_manifest(request.manifest_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        issues = [
            *state.get("issues", []),
            {
                "code": "MANIFEST_LOAD_FAILED",
                "severity": "error",
                "message": f"could not load manifest: {exc}",
                "path": str(request.manifest_path),
            },
        ]
        return {"manifest": {}, "artifacts": artifacts, "issues": issues}
    return {"manifest": manifest, "artifacts": artifacts}


def apply_patch_node(state: PatchSIState) -> dict:
    try:
        return _apply_patch_node(state)
    except Exception as exc:
        request = state["request"]
        artifacts = dict(state.get("artifacts", {}))
        issue_code = "PATCH_OPERATION_COUNT_INVALID" if "PATCH_OPERATION_COUNT_INVALID" in str(exc) else "PATCH_APPLY_FAILED"
        issues = [
            *state.get("issues", []),
            {
                "code": issue_code,
                "severity": "error",
                "message": f"could not apply patch: {exc}",
                "path": str(request.manifest_path),
            },
        ]
        return {
            "manifest": state.get("manifest", {}),
            "artifacts": artifacts,
            "issues": issues,
            "patch_result": _empty_patch_result(),
        }


def _apply_patch_node(state: PatchSIState) -> dict:
    request = state["request"]
    source_manifest = state.get("manifest", {})
    if manifest_has_errors(state.get("issues", [])):
        return {"manifest": source_manifest, "artifacts": state.get("artifacts", {}), "patch_result": _empty_patch_result()}
    operation = selected_patch_operation(request)
    source_docx = support_docx_from_manifest(source_manifest, request.manifest_path, request.support_docx)
    artifacts = state.get("artifacts", {})
    output_docx = Path(artifacts["support_docx"])
    output_manifest = Path(artifacts["manifest"])
    temp_docx = _temporary_sibling(output_docx)
    temp_manifest = _temporary_sibling(output_manifest)

    try:
        patched_manifest = source_manifest
        applied_numbers: dict[str, str] = {}
        removed_ids: list[str] = []
        removed_bookmarks: list[str] = []
        reordered_ids: list[str] = []
        swapped_pairs: list[dict[str, str]] = []
        text_number_map: dict[str, str] = {}
        if operation == "remove":
            patched_manifest, removed_ids, removed_bookmarks = remove_manifest(patched_manifest, request.remove)
        elif operation == "renumber":
            patched_manifest, applied_numbers = renumber_manifest(patched_manifest, request.renumber)
            text_number_map = applied_numbers
        elif operation == "reorder":
            patched_manifest, reordered_ids = reorder_manifest(patched_manifest, request.reorder)
        elif operation == "swap":
            patched_manifest, swapped_pairs, text_number_map = swap_manifest(patched_manifest, request.swap)
            reordered_ids = [str(item) for item in patched_manifest.get("order", [])]

        patch_docx_numbers(source_docx, temp_docx, text_number_map)
        available_bookmarks = existing_docx_bookmarks(temp_docx)
        if removed_ids:
            spectrum_bookmarks = spectrum_bookmark_order_for_compounds(source_manifest, removed_ids)
            compound_bookmarks = _required_compound_bookmarks(source_manifest, removed_ids, available_bookmarks)
            existing_spectrum_bookmarks = [
                bookmark for bookmark in spectrum_bookmarks if bookmark in available_bookmarks
            ]
            remove_docx_blocks(temp_docx, temp_docx, compound_bookmarks)
            remove_docx_blocks(
                temp_docx,
                temp_docx,
                existing_spectrum_bookmarks,
                include_previous_page_break=True,
            )
            removed_bookmarks = compound_bookmarks + existing_spectrum_bookmarks
        if reordered_ids:
            compound_bookmarks = _required_compound_bookmarks(patched_manifest, reordered_ids, available_bookmarks)
            reorder_docx_blocks(temp_docx, temp_docx, compound_bookmarks)
            spectrum_bookmarks = [
                bookmark
                for bookmark in spectrum_bookmark_order_for_compounds(patched_manifest, reordered_ids)
                if bookmark in available_bookmarks
            ]
            if spectrum_bookmarks:
                reorder_docx_blocks(
                    temp_docx,
                    temp_docx,
                    spectrum_bookmarks,
                    include_previous_page_break=True,
                )
        patch_result = {
            "operation": operation,
            "renumbered": applied_numbers,
            "removed_ids": removed_ids,
            "removed_bookmarks": removed_bookmarks,
            "reordered_ids": reordered_ids,
            "swapped_pairs": swapped_pairs,
        }
        set_manifest_output_paths(patched_manifest, support_docx=output_docx, manifest_path=output_manifest)
        _append_patch_history(
            patched_manifest,
            run_id=state.get("run_id", ""),
            source_manifest=request.manifest_path,
            output_manifest=output_manifest,
            output_docx=output_docx,
            operations=_patch_operations(request),
            patch_result=patch_result,
        )
        write_patched_manifest(patched_manifest, temp_manifest)
        temp_docx.replace(output_docx)
        temp_manifest.replace(output_manifest)
    except Exception:
        temp_docx.unlink(missing_ok=True)
        temp_manifest.unlink(missing_ok=True)
        raise

    artifacts = {
        **state.get("artifacts", {}),
        "support_docx": str(Path(output_docx)),
        "manifest": str(Path(output_manifest)),
    }
    return {"manifest": patched_manifest, "artifacts": artifacts, "patch_result": patch_result}


def check_patched_manifest_node(state: PatchSIState) -> dict:
    request = state["request"]
    manifest_path = Path(state.get("artifacts", {}).get("manifest") or request.manifest_path)
    support_docx = Path(state.get("artifacts", {}).get("support_docx", "")) if state.get("artifacts", {}).get("support_docx") else None
    issues = list(state.get("issues", []))
    issues.extend(
        check_manifest(
            state.get("manifest", {}),
            manifest_path=manifest_path,
            support_docx=support_docx,
            strict_artifacts=request.strict_artifacts,
        )
    )
    status = "fail" if manifest_has_errors(issues) else "pass"
    reports_dir = state.get("artifacts", {}).get("reports_dir")
    report_base = support_docx or manifest_path
    report_path = Path(reports_dir) / "patch_report.json" if reports_dir else _patch_report_path(report_base)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = build_patch_report(state, status, issues, report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts = {**state.get("artifacts", {}), "patch_report": str(report_path)}
    return {"issues": issues, "status": status, "artifacts": artifacts}


def build_patch_report(state: PatchSIState, status: str, issues: list[dict], report_path: Path) -> dict:
    request = state["request"]
    return {
        "run_id": state.get("run_id", ""),
        "status": status,
        "source_manifest": str(Path(request.manifest_path)),
        "operations": _patch_operations(request),
        "patch_result": state.get(
            "patch_result",
            _empty_patch_result(),
        ),
        "strict_artifacts": request.strict_artifacts,
        "issue_counts": count_issues(issues),
        "compound_issue_counts": compound_issue_counts(issues),
        "issues": issues,
        "artifacts": {
            **state.get("artifacts", {}),
            "patch_report": str(report_path),
        },
    }


def _patch_report_path(base_path: Path) -> Path:
    if base_path.name.endswith(".manifest.json"):
        return base_path.with_name(f"{base_path.name[:-len('.manifest.json')]}.patch_report.json")
    return base_path.with_suffix(".patch_report.json")


def _temporary_sibling(path: Path) -> Path:
    return path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")


def _patch_operations(request) -> dict[str, object]:
    return {
        "renumber": dict(request.renumber),
        "remove": list(request.remove),
        "reorder": list(request.reorder),
        "swap": [list(pair) for pair in request.swap],
    }


def _empty_patch_result() -> dict[str, object]:
    return {
        "operation": "",
        "renumbered": {},
        "removed_ids": [],
        "removed_bookmarks": [],
        "reordered_ids": [],
        "swapped_pairs": [],
    }


def _patch_output_base(request) -> Path:
    if request.output_folder:
        return Path(request.output_folder)
    manifest_parent = Path(request.manifest_path).resolve().parent
    if manifest_parent.name.lower() == "docx" and manifest_parent.parent.parent.name.lower() == "runs":
        return manifest_parent.parent.parent
    return manifest_parent


def _required_compound_bookmarks(manifest: dict, compound_ids: list[str], available: set[str]) -> list[str]:
    bookmarks = bookmark_order_for_compounds(manifest, compound_ids)
    missing = [bookmark for bookmark in bookmarks if bookmark not in available]
    if missing:
        raise ValueError("DOCX is missing bookmark ranges: " + ", ".join(missing))
    return bookmarks


def _append_patch_history(
    manifest: dict,
    *,
    run_id: str,
    source_manifest: Path,
    output_manifest: Path,
    output_docx: Path,
    operations: dict[str, object],
    patch_result: dict[str, object],
) -> None:
    history = manifest.setdefault("patch_history", [])
    if not isinstance(history, list):
        manifest["patch_history"] = history = []
    history.append(
        {
            "run_id": run_id,
            "source_manifest": str(Path(source_manifest)),
            "output_manifest": str(Path(output_manifest)),
            "output_docx": str(Path(output_docx)),
            "operations": operations,
            "result": patch_result,
        }
    )
