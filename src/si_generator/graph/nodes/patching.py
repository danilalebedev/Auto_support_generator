from __future__ import annotations

import json
from pathlib import Path

from ...domain.issues import count_issues
from ...domain.manifest import check_manifest, load_manifest, manifest_has_errors
from ...domain.patching import (
    bookmark_order_for_compounds,
    default_patched_docx_path,
    patch_docx_numbers,
    renumber_manifest,
    remove_docx_blocks,
    remove_manifest,
    reorder_docx_blocks,
    reorder_manifest,
    set_manifest_output_paths,
    support_docx_from_manifest,
    write_patched_manifest,
)
from ..state import PatchSIState


def load_patch_manifest_node(state: PatchSIState) -> dict:
    request = state["request"]
    manifest = load_manifest(request.manifest_path)
    return {"manifest": manifest, "artifacts": {**state.get("artifacts", {}), "manifest": str(request.manifest_path)}}


def apply_renumber_patch_node(state: PatchSIState) -> dict:
    request = state["request"]
    source_manifest = state.get("manifest", {})
    source_docx = support_docx_from_manifest(source_manifest, request.manifest_path, request.support_docx)
    output_docx = request.output_docx or default_patched_docx_path(source_docx)
    output_manifest = request.output_manifest or output_docx.with_suffix(".manifest.json")

    patched_manifest = source_manifest
    applied_numbers: dict[str, str] = {}
    removed_bookmarks: list[str] = []
    if request.remove:
        patched_manifest, _removed_ids, removed_bookmarks = remove_manifest(patched_manifest, request.remove)
    if request.renumber:
        patched_manifest, applied_numbers = renumber_manifest(patched_manifest, request.renumber)
    if request.reorder:
        patched_manifest, reordered_ids = reorder_manifest(patched_manifest, request.reorder)
    else:
        reordered_ids = []

    if applied_numbers:
        patch_docx_numbers(source_docx, output_docx, applied_numbers)
    else:
        patch_docx_numbers(source_docx, output_docx, {})
    if removed_bookmarks:
        remove_docx_blocks(output_docx, output_docx, removed_bookmarks)
    if reordered_ids:
        reorder_docx_blocks(output_docx, output_docx, bookmark_order_for_compounds(patched_manifest, reordered_ids))
    set_manifest_output_paths(patched_manifest, support_docx=output_docx, manifest_path=output_manifest)
    write_patched_manifest(patched_manifest, output_manifest)

    artifacts = {
        **state.get("artifacts", {}),
        "support_docx": str(Path(output_docx)),
        "manifest": str(Path(output_manifest)),
    }
    return {"manifest": patched_manifest, "artifacts": artifacts}


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
    report_base = support_docx or manifest_path
    report_path = _patch_report_path(report_base)
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
        "operations": {
            "renumber": dict(request.renumber),
            "remove": list(request.remove),
            "reorder": list(request.reorder),
        },
        "strict_artifacts": request.strict_artifacts,
        "issue_counts": count_issues(issues),
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
