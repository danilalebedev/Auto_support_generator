from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ...domain.bookmarks import bookmark_name_for_block_id
from ...domain.compound import compound_to_domain_dict
from ...domain.issues import compound_issue_counts, count_issues, generation_status, issue_code_counts, issues_by_compound
from ...output_layout import output_dirs, output_root_for
from ..state import GenerateSIState


def write_manifest_node(state: GenerateSIState) -> dict:
    output_path = Path(state["output_path"])
    manifest_path = output_path.with_suffix(".manifest.json")
    run_summary_path = output_path.with_suffix(".run_summary.json")
    state_with_manifest = {
        **state,
        "artifacts": {
            **state.get("artifacts", {}),
            "manifest": str(manifest_path),
            "run_summary": str(run_summary_path),
        },
    }
    manifest = build_manifest(state_with_manifest)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    run_summary = build_run_summary(state_with_manifest, manifest)
    run_summary_path.write_text(json.dumps(run_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"manifest": manifest, "artifacts": manifest["artifacts"]}


def build_manifest(state: GenerateSIState) -> dict:
    request = state["request"]
    compounds = state.get("compounds", {})
    order = list(state.get("order", []))
    output_path = Path(state["output_path"])
    artifacts = collect_output_artifacts(state)
    output_paths = _output_paths(output_path, artifacts)
    output_root = output_root_for(output_path)

    manifest = {
        "run_id": state.get("run_id", ""),
        "input_hashes": _input_hashes(
            {
                "compound_table": request.input_path,
                "spectra_source": request.resolved_spectra_source,
                "template_docx": request.template_docx,
                "references": request.references_path,
            }
        ),
        "output_paths": output_paths,
        "relative_paths": _relative_paths(output_root, artifacts),
        "configs": {
            "spectra": state.get("spectra_config", {}),
            "generation": state.get("generation_config", {}),
            "runtime": state.get("runtime_config", {}),
        },
        "artifacts": artifacts,
        "order": order,
        "compounds": {},
    }

    for compound_id in order:
        compound = compounds.get(compound_id)
        if not compound:
            continue
        compound_artifacts = _compound_artifacts(compound)
        manifest["compounds"][compound_id] = {
            "id": compound_id,
            "number": compound.number,
            "name": compound.name,
            "formula": compound.formula,
            "source_row": compound.source_row,
            "domain_snapshot": compound_to_domain_dict(compound),
            "structure": {
                "has_word_structure": compound.has_word_structure,
                "path": compound.structure_path,
            },
            "analytical_blocks": _analytical_blocks(compound),
            "structure_placeholder": f"STRUCTURE:{compound.number}",
            "docx_block_id": f"compound:{compound_id}",
            "docx_bookmark": bookmark_name_for_block_id(f"compound:{compound_id}"),
            "references": list(compound.references),
            "artifacts": compound_artifacts,
            "relative_artifacts": _relative_paths(output_root, compound_artifacts),
        }

    return manifest


def build_run_summary(state: GenerateSIState, manifest: dict | None = None) -> dict:
    manifest = manifest or build_manifest(state)
    issues = list(state.get("issues", []))
    issue_counts = count_issues(issues)
    grouped_issues = issues_by_compound(issues)
    compounds = state.get("compounds", {})
    order = list(state.get("order", []))

    return {
        "run_id": state.get("run_id", ""),
        "status": generation_status(issue_counts),
        "compound_count": len(order),
        "issue_counts": issue_counts,
        "issue_code_counts": issue_code_counts(issues),
        "compound_issue_counts": compound_issue_counts(issues),
        "issues": issues,
        "output_paths": manifest.get("output_paths", {}),
        "artifacts": manifest.get("artifacts", {}),
        "relative_paths": manifest.get("relative_paths", {}),
        "configs": manifest.get("configs", {}),
        "compounds": [
            {
                "id": compound_id,
                "number": compounds[compound_id].number,
                "name": compounds[compound_id].name,
                "formula": compounds[compound_id].formula,
                "domain_snapshot": compound_to_domain_dict(compounds[compound_id]),
                "issue_count": len(grouped_issues.get(compound_id, [])),
                "issues": _compact_issues(grouped_issues.get(compound_id, [])),
            }
            for compound_id in order
            if compound_id in compounds
        ],
    }


def collect_output_artifacts(state: GenerateSIState) -> dict[str, str]:
    output_path = Path(state["output_path"])
    artifacts = {key: str(path) for key, path in state.get("artifacts", {}).items()}
    artifacts.setdefault("support_docx", str(output_path))
    artifacts.setdefault("manifest", str(output_path.with_suffix(".manifest.json")))
    dirs = output_dirs(output_path)
    artifacts.setdefault("output_root", str(dirs["output_root"]))

    for key, path in {
        "docx_dir": dirs["docx_dir"],
        "input_dir": dirs["input_dir"],
        "logs_dir": dirs["logs_dir"],
        "reports_dir": dirs["reports_dir"],
        "spectra_dir": dirs["spectra_dir"],
        "processed_spectra_zip": dirs["processed_spectra_zip"],
        "processed_spectra_dir": dirs["processed_spectra_dir"],
        "processed_mnova_dir": dirs["processed_mnova_dir"],
        "mnova_reports_dir": dirs["mnova_reports_dir"],
    }.items():
        if Path(path).exists():
            artifacts[key] = str(path)
    return artifacts


def _output_paths(output_path: Path, artifacts: dict[str, str]) -> dict[str, str]:
    output_paths = {
        "support_docx": str(output_path),
        "manifest": str(output_path.with_suffix(".manifest.json")),
        "run_summary": artifacts.get("run_summary", str(output_path.with_suffix(".run_summary.json"))),
    }
    for key in [
        "output_root",
        "docx_dir",
        "input_dir",
        "spectra_dir",
        "processed_spectra_zip",
        "processed_spectra_dir",
        "processed_mnova_dir",
        "mnova_reports_dir",
        "logs_dir",
        "reports_dir",
    ]:
        if key in artifacts:
            output_paths[key] = artifacts[key]
    return output_paths


def _input_hashes(paths: dict[str, Path | None]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, path in paths.items():
        if path and Path(path).exists():
            hashes[key] = _sha256_path(path)
    return hashes


def _sha256_path(path: Path) -> str:
    path = Path(path)
    if path.is_dir():
        return _sha256_dir(path)
    return _sha256_file(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_dir(path: Path) -> str:
    digest = hashlib.sha256()
    root = Path(path)
    for child in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = child.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with child.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _compound_artifacts(compound) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    if compound.h1_image_path:
        artifacts["h1_png"] = compound.h1_image_path
    if compound.c13_image_path:
        artifacts["c13_png"] = compound.c13_image_path
    if getattr(compound, "h1_mnova_path", ""):
        artifacts["h1_mnova"] = compound.h1_mnova_path
    if getattr(compound, "c13_mnova_path", ""):
        artifacts["c13_mnova"] = compound.c13_mnova_path
    if compound.mnova_path:
        artifacts["mnova"] = compound.mnova_path
    return artifacts


def _analytical_blocks(compound) -> dict[str, bool]:
    return {
        "preparation": bool(compound.preparation or compound.reaction),
        "yield": bool(compound.yield_text),
        "physical_properties": bool(compound.color or compound.state or compound.melting_point or compound.rf),
        "h1_nmr": bool(compound.h1_nmr or compound.nmr_spectra.get("1H")),
        "c13_nmr": bool(compound.c13_nmr or compound.nmr_spectra.get("13C")),
        "extra_nmr": bool(compound.extra_nmr),
        "ir": bool(compound.ir),
        "hrms": bool(compound.hrms or compound.hrms_found),
        "elemental_analysis": bool(compound.elemental_analysis),
    }


def _compact_issues(issues: list[dict]) -> list[dict[str, str]]:
    return [
        {
            "code": str(issue.get("code", "")),
            "severity": str(issue.get("severity", "warning")),
            "message": str(issue.get("message", "")),
        }
        for issue in issues
    ]


def _relative_paths(base_dir: Path, paths: dict[str, str]) -> dict[str, str]:
    base_dir = base_dir.resolve()
    result: dict[str, str] = {}
    for key, value in paths.items():
        result[key] = _relative_path(base_dir, value)
    return result


def _relative_path(base_dir: Path, value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        return str(path)
    try:
        return str(path.resolve().relative_to(base_dir))
    except ValueError:
        return str(path)
