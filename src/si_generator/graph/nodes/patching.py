from __future__ import annotations

import json
import hashlib
import uuid
import shutil
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
from ...domain.compound import Compound, compound_from_domain_dict
from ...docx_builder import build_document_from_model
from ...journal_profiles import get_journal_profile, journal_profile_manifest_block
from ...output_layout import prepare_output_layout
from ...render.document_model import build_si_document_model
from ...word_input import paste_support_structures
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

        if operation == "reformat":
            return _reformat_for_journal(
                state,
                source_manifest=source_manifest,
                source_docx=source_docx,
                output_docx=output_docx,
                output_manifest=output_manifest,
                temp_docx=temp_docx,
                temp_manifest=temp_manifest,
            )

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
        "reformat_journal": request.journal_profile_id or "",
    }


def _empty_patch_result() -> dict[str, object]:
    return {
        "operation": "",
        "renumbered": {},
        "removed_ids": [],
        "removed_bookmarks": [],
        "reordered_ids": [],
        "swapped_pairs": [],
        "journal_profile_id": "",
    }


def _reformat_for_journal(
    state: PatchSIState,
    *,
    source_manifest: dict,
    source_docx: Path,
    output_docx: Path,
    output_manifest: Path,
    temp_docx: Path,
    temp_manifest: Path,
) -> dict:
    request = state["request"]
    profile = get_journal_profile(request.journal_profile_id)
    _copy_reformat_source_artifacts(source_manifest, request.manifest_path, state.get("artifacts", {}))
    compounds = _compounds_from_manifest(source_manifest, request.manifest_path)
    embed_mode = str(source_manifest.get("run_config", {}).get("insert_spectra_as") or "png")
    if embed_mode not in {"png", "mnova", "none"}:
        embed_mode = "png"
    model = build_si_document_model(compounds, spectra_embed_mode=embed_mode)
    build_document_from_model(
        model,
        temp_docx,
        template_path=profile.template_path,
        render_options=profile.data,
    )
    copied_structures = paste_support_structures(source_docx, temp_docx, compounds)

    patched_manifest = json.loads(json.dumps(source_manifest, ensure_ascii=False))
    patched_manifest["journal_profile"] = journal_profile_manifest_block(profile.id)
    run_config = patched_manifest.setdefault("run_config", {})
    if isinstance(run_config, dict):
        run_config["journal_profile_id"] = profile.id
        run_config["template_docx"] = str(profile.template_path.name)
    _set_reformat_layout_paths(patched_manifest, state.get("artifacts", {}), output_docx, output_manifest)
    set_manifest_output_paths(patched_manifest, support_docx=output_docx, manifest_path=output_manifest)

    input_dir = Path(state.get("artifacts", {}).get("input_dir") or output_docx.parent.parent / "input")
    input_dir.mkdir(parents=True, exist_ok=True)
    profile_template_copy = input_dir / profile.template_path.name
    shutil.copy2(profile.template_path, profile_template_copy)
    profile_catalog_copy = input_dir / "journal_profiles.json"
    shutil.copy2(profile.resource_dir / "profiles.json", profile_catalog_copy)
    _register_reformat_input(patched_manifest, state.get("artifacts", {}), "template_docx", profile_template_copy)
    for nucleus, config_key in (("1H", "mnova_graphics_profile_1h"), ("13C", "mnova_graphics_profile_13c")):
        mngp_source = profile.mngp_path(nucleus)
        if mngp_source and mngp_source.exists():
            mngp_copy = input_dir / mngp_source.name
            shutil.copy2(mngp_source, mngp_copy)
            _register_reformat_input(patched_manifest, state.get("artifacts", {}), config_key, mngp_copy)

    patch_result = {
        **_empty_patch_result(),
        "operation": "reformat",
        "journal_profile_id": profile.id,
        "copied_structure_count": copied_structures,
    }
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
    artifacts = {
        **state.get("artifacts", {}),
        "support_docx": str(output_docx),
        "manifest": str(output_manifest),
        "journal_template": str(profile_template_copy),
        "journal_profile_catalog": str(profile_catalog_copy),
    }
    return {"manifest": patched_manifest, "artifacts": artifacts, "patch_result": patch_result}


def _compounds_from_manifest(manifest: dict, manifest_path: Path) -> list[Compound]:
    compounds_by_id = manifest.get("compounds", {}) or {}
    result: list[Compound] = []
    for compound_id in manifest.get("order", []):
        entry = compounds_by_id.get(str(compound_id))
        if not isinstance(entry, dict):
            raise ValueError(f"PATCH_REFORMAT_SNAPSHOT_MISSING: compound '{compound_id}' is missing from manifest")
        snapshot = entry.get("domain_snapshot")
        if not isinstance(snapshot, dict):
            raise ValueError(f"PATCH_REFORMAT_SNAPSHOT_MISSING: compound '{compound_id}' has no domain snapshot")
        compound = compound_from_domain_dict(snapshot)
        compound.id = str(compound_id)
        compound.number = str(entry.get("number") or compound.number)
        compound.name = str(entry.get("name") or compound.name)
        _hydrate_compound_artifacts(compound, entry, manifest, manifest_path)
        result.append(compound)
    return result


def _hydrate_compound_artifacts(compound: Compound, entry: dict, manifest: dict, manifest_path: Path) -> None:
    artifacts = dict(entry.get("artifacts", {}) or {})
    relative = dict(entry.get("relative_artifacts", {}) or {})
    mappings = {
        "h1_png": "h1_image_path",
        "c13_png": "c13_image_path",
        "h1_mnova": "h1_mnova_path",
        "c13_mnova": "c13_mnova_path",
        "mnova": "mnova_path",
    }
    base_dir = _manifest_output_root(manifest, manifest_path)
    for key, attribute in mappings.items():
        candidates = [relative.get(key), artifacts.get(key), getattr(compound, attribute, "")]
        resolved = _first_existing_manifest_path(candidates, base_dir)
        if resolved:
            setattr(compound, attribute, str(resolved))


def _manifest_output_root(manifest: dict, manifest_path: Path) -> Path:
    for source_name in ("artifacts", "output_paths"):
        source = manifest.get(source_name, {})
        if isinstance(source, dict) and source.get("output_root"):
            candidate = Path(source["output_root"])
            if candidate.is_absolute() and candidate.exists():
                return candidate.resolve()
    parent = Path(manifest_path).resolve().parent
    return parent.parent if parent.name.lower() == "docx" else parent


def _first_existing_manifest_path(candidates, base_dir: Path) -> Path | None:
    first: Path | None = None
    for raw in candidates:
        if not raw:
            continue
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = base_dir / candidate
        candidate = candidate.resolve()
        first = first or candidate
        if candidate.exists():
            return candidate
    return first


def _copy_reformat_source_artifacts(source_manifest: dict, manifest_path: Path, target_artifacts: dict) -> None:
    source_root = _manifest_output_root(source_manifest, manifest_path)
    target_root_text = target_artifacts.get("output_root")
    if not target_root_text:
        return
    target_root = Path(target_root_text).resolve()
    for folder_name in ("input", "spectra", "mnova", "logs", "reports"):
        source = source_root / folder_name
        target = target_root / folder_name
        if source.exists() and source.resolve() != target.resolve():
            shutil.copytree(source, target, dirs_exist_ok=True)


def _set_reformat_layout_paths(
    manifest: dict,
    target_artifacts: dict,
    output_docx: Path,
    output_manifest: Path,
) -> None:
    path_keys = (
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
    )
    artifacts = manifest.setdefault("artifacts", {})
    output_paths = manifest.setdefault("output_paths", {})
    for key in path_keys:
        value = target_artifacts.get(key)
        if value:
            artifacts[key] = str(value)
            output_paths[key] = str(value)
    output_root = Path(target_artifacts.get("output_root") or output_docx.parent.parent)
    relative = manifest.setdefault("relative_paths", {})
    for key in path_keys:
        value = target_artifacts.get(key)
        if not value:
            continue
        try:
            relative[key] = str(Path(value).resolve().relative_to(output_root.resolve())) or "."
        except ValueError:
            relative[key] = str(value)
    relative["support_docx"] = str(output_docx.resolve().relative_to(output_root.resolve()))
    relative["manifest"] = str(output_manifest.resolve().relative_to(output_root.resolve()))


def _register_reformat_input(manifest: dict, target_artifacts: dict, config_key: str, path: Path) -> None:
    output_root = Path(target_artifacts.get("output_root") or path.parent.parent).resolve()
    try:
        relative_path = str(path.resolve().relative_to(output_root))
    except ValueError:
        relative_path = str(path.resolve())
    run_config = manifest.setdefault("run_config", {})
    if isinstance(run_config, dict):
        run_config[config_key] = relative_path
    artifact_key = f"{config_key}_copy"
    manifest.setdefault("artifacts", {})[artifact_key] = str(path)
    manifest.setdefault("relative_paths", {})[artifact_key] = relative_path
    manifest.setdefault("input_hashes", {})[config_key] = _sha256_file(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
