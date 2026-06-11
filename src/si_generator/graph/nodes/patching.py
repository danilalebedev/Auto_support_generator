from __future__ import annotations

from pathlib import Path

from ...domain.manifest import check_manifest, load_manifest, manifest_has_errors
from ...domain.patching import (
    default_patched_docx_path,
    patch_docx_numbers,
    renumber_manifest,
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

    patched_manifest, applied = renumber_manifest(source_manifest, request.renumber)
    patch_docx_numbers(source_docx, output_docx, applied)
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
    return {"issues": issues, "status": "fail" if manifest_has_errors(issues) else "pass"}
