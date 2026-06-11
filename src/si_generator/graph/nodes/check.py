from __future__ import annotations

from pathlib import Path

from ...domain.manifest import check_manifest, load_manifest, manifest_has_errors
from ..state import CheckSIState


def load_manifest_node(state: CheckSIState) -> dict:
    request = state["request"]
    manifest_path = Path(request.manifest_path)
    manifest = load_manifest(manifest_path)
    artifacts = {**state.get("artifacts", {}), "manifest": str(manifest_path)}
    return {"manifest": manifest, "artifacts": artifacts}


def check_manifest_node(state: CheckSIState) -> dict:
    request = state["request"]
    manifest_path = Path(request.manifest_path)
    issues = list(state.get("issues", []))
    issues.extend(
        check_manifest(
            state.get("manifest", {}),
            manifest_path=manifest_path,
            support_docx=request.support_docx,
            strict_artifacts=request.strict_artifacts,
        )
    )
    status = "fail" if manifest_has_errors(issues) else "pass"
    return {"issues": issues, "status": status}
