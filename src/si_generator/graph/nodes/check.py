from __future__ import annotations

import json
from pathlib import Path

from ...domain.issues import compound_issue_counts, count_issues
from ...domain.manifest import check_manifest, load_manifest, manifest_has_errors
from ..state import CheckSIState


def load_manifest_node(state: CheckSIState) -> dict:
    request = state["request"]
    manifest_path = Path(request.manifest_path)
    artifacts = {**state.get("artifacts", {}), "manifest": str(manifest_path)}
    try:
        manifest = load_manifest(manifest_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        issues = [
            *state.get("issues", []),
            {
                "code": "MANIFEST_LOAD_FAILED",
                "severity": "error",
                "message": f"could not load manifest: {exc}",
                "path": str(manifest_path),
            },
        ]
        return {"manifest": {}, "artifacts": artifacts, "issues": issues}
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
    report_path = _check_report_path(manifest_path)
    report = build_check_report(state, status, issues, report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts = {**state.get("artifacts", {}), "check_report": str(report_path)}
    return {"issues": issues, "status": status, "artifacts": artifacts}


def build_check_report(state: CheckSIState, status: str, issues: list[dict], report_path: Path) -> dict:
    request = state["request"]
    return {
        "run_id": state.get("run_id", ""),
        "status": status,
        "manifest_path": str(Path(request.manifest_path)),
        "support_docx": str(Path(request.support_docx)) if request.support_docx else "",
        "strict_artifacts": request.strict_artifacts,
        "issue_counts": count_issues(issues),
        "compound_issue_counts": compound_issue_counts(issues),
        "issues": issues,
        "artifacts": {
            **state.get("artifacts", {}),
            "check_report": str(report_path),
        },
    }


def _check_report_path(manifest_path: Path) -> Path:
    name = manifest_path.name
    if name.endswith(".manifest.json"):
        return manifest_path.with_name(f"{name[:-len('.manifest.json')]}.check_report.json")
    return manifest_path.with_suffix(".check_report.json")
