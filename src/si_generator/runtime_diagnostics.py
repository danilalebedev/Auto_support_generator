from __future__ import annotations

import uuid
import zipfile
from collections.abc import Callable
from pathlib import Path

from .domain.requests import GenerateSIRequest
from .domain.types import Issue
from .external_tools import find_mnova_executable
from .mnova import SCRIPT_PATH
from .spectra_zip import validate_spectra_zip


MnovaFinder = Callable[[str | Path | None], Path]


def preflight_generate_request(
    request: GenerateSIRequest,
    *,
    mnova_finder: MnovaFinder = find_mnova_executable,
    mnova_script_path: str | Path = SCRIPT_PATH,
) -> list[Issue]:
    """Run cheap checks that catch common setup failures before a long run."""
    issues: list[Issue] = []
    issues.extend(_check_input_path(request))
    issues.extend(_check_output_path(request.output_path))
    issues.extend(_check_loadings_files(request))
    issues.extend(_check_mnova_graphics_profile(request))
    spectra_source = request.resolved_spectra_source
    if spectra_source:
        issues.extend(_check_spectra_source(spectra_source))
    else:
        issues.extend(_check_missing_spectra_source(request))
    if _mnova_required(request):
        issues.extend(_check_mnova_script(Path(mnova_script_path)))
        issues.extend(_check_mnova(request, mnova_finder))
    return issues


def issue_has_errors(issues: list[Issue]) -> bool:
    return any(issue.get("severity") == "error" for issue in issues)


def format_preflight_issues(issues: list[Issue]) -> str:
    lines = []
    for issue in issues:
        severity = str(issue.get("severity", "warning")).upper()
        code = issue.get("code", "PREFLIGHT")
        message = issue.get("message", "")
        path = issue.get("path", "")
        suffix = f" ({path})" if path else ""
        lines.append(f"[{severity}] {code}: {message}{suffix}")
        detail = str(issue.get("detail", "")).strip()
        if detail:
            lines.append(f"  Details: {detail}")
    return "\n".join(lines)


def _check_input_path(request: GenerateSIRequest) -> list[Issue]:
    path = request.input_path
    if not path.exists():
        return [_issue("PREFLIGHT_INPUT_MISSING", "error", "Input table does not exist.", path)]
    if request.input_kind == "word" and path.suffix.lower() != ".docx":
        return [_issue("PREFLIGHT_INPUT_EXTENSION", "warning", "Word input is expected to be a .docx file.", path)]
    if request.input_kind == "csv" and path.suffix.lower() != ".csv":
        return [_issue("PREFLIGHT_INPUT_EXTENSION", "warning", "CSV input is expected to be a .csv file.", path)]
    return []


def _check_output_path(output_path: Path) -> list[Issue]:
    issues: list[Issue] = []
    if output_path.suffix.lower() != ".docx":
        issues.append(_issue("PREFLIGHT_OUTPUT_EXTENSION", "error", "Output file must be a .docx file.", output_path))
        return issues

    output_dir = output_path.parent
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        probe = output_dir / f".autosi_write_test_{uuid.uuid4().hex}.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        issues.append(_issue("PREFLIGHT_OUTPUT_NOT_WRITABLE", "error", f"Output folder is not writable: {exc}", output_dir))
        return issues

    if output_path.exists():
        try:
            with output_path.open("r+b"):
                pass
        except OSError as exc:
            issues.append(_issue("PREFLIGHT_OUTPUT_LOCKED", "error", f"Output DOCX cannot be opened for writing: {exc}", output_path))
    return issues


def _check_spectra_source(spectra_source: Path) -> list[Issue]:
    if not spectra_source.exists():
        return [_issue("PREFLIGHT_SPECTRA_SOURCE_MISSING", "error", "Spectra source does not exist.", spectra_source)]
    if spectra_source.is_dir():
        return []
    if spectra_source.suffix.lower() != ".zip":
        return [_issue("PREFLIGHT_SPECTRA_SOURCE_INVALID", "error", "Spectra source must be a folder or a readable zip archive.", spectra_source)]
    if not zipfile.is_zipfile(spectra_source):
        return [_issue("PREFLIGHT_SPECTRA_ZIP_INVALID", "error", "Spectra file is not a readable zip archive.", spectra_source)]
    try:
        with zipfile.ZipFile(spectra_source) as archive:
            if not archive.namelist():
                return [_issue("PREFLIGHT_SPECTRA_ZIP_EMPTY", "warning", "Spectra zip archive is empty.", spectra_source)]
            try:
                validate_spectra_zip(archive, spectra_source.parent / spectra_source.stem)
            except ValueError as exc:
                return [_issue("PREFLIGHT_SPECTRA_ZIP_UNSAFE", "error", str(exc), spectra_source)]
    except OSError as exc:
        return [_issue("PREFLIGHT_SPECTRA_ZIP_INVALID", "error", f"Spectra zip cannot be read: {exc}", spectra_source)]
    return []


def _check_loadings_files(request: GenerateSIRequest) -> list[Issue]:
    paths = {
        "Reaction schema": request.loadings_schema_docx,
        "Scope": request.loadings_scope_docx,
    }
    selected = {label: path for label, path in paths.items() if path}
    if not selected:
        return []
    if len(selected) != len(paths):
        return [
            _issue(
                "PREFLIGHT_LOADINGS_FILES_INCOMPLETE",
                "error",
                "Choose both reagent loadings files or leave both fields empty for auto-detect.",
            )
        ]

    issues: list[Issue] = []
    for label, path in selected.items():
        if not path.exists():
            issues.append(_issue("PREFLIGHT_LOADINGS_FILE_MISSING", "error", f"{label} file does not exist.", path))
        elif not path.is_file():
            issues.append(_issue("PREFLIGHT_LOADINGS_FILE_NOT_FILE", "error", f"{label} path must be a file.", path))
        elif path.suffix.lower() != ".docx":
            issues.append(_issue("PREFLIGHT_LOADINGS_FILE_EXTENSION", "error", f"{label} file must be a .docx file.", path))
    return issues


def _check_mnova_graphics_profile(request: GenerateSIRequest) -> list[Issue]:
    issues: list[Issue] = []
    for label, path in {
        "Mnova graphics profile": request.mnova_graphics_profile,
        "1H Mnova graphics profile": request.mnova_graphics_profile_1h,
        "13C Mnova graphics profile": request.mnova_graphics_profile_13c,
    }.items():
        if not path:
            continue
        if not path.exists():
            issues.append(_issue("PREFLIGHT_MNOVA_GRAPHICS_PROFILE_MISSING", "error", f"{label} does not exist.", path))
        elif not path.is_file():
            issues.append(_issue("PREFLIGHT_MNOVA_GRAPHICS_PROFILE_NOT_FILE", "error", f"{label} must be a file.", path))
        elif path.suffix.lower() != ".mngp":
            issues.append(_issue("PREFLIGHT_MNOVA_GRAPHICS_PROFILE_EXTENSION", "error", f"{label} must be a .mngp file.", path))
    return issues


def _check_missing_spectra_source(request: GenerateSIRequest) -> list[Issue]:
    if request.insert_spectra_as == "none":
        return []
    return [
        _issue(
            "PREFLIGHT_SPECTRA_SOURCE_NOT_SELECTED",
            "warning",
            "Spectra appendix is enabled, but no spectra source was selected. Generated spectrum images and Mnova files will be skipped unless input rows already point to processed spectrum assets.",
        )
    ]


def _check_mnova(request: GenerateSIRequest, mnova_finder: MnovaFinder) -> list[Issue]:
    try:
        mnova_finder(request.mnova_exe)
    except (FileNotFoundError, OSError) as exc:
        return [
            _issue(
                "PREFLIGHT_MNOVA_NOT_FOUND",
                "error",
                "MestReNova is required for spectra extraction but was not found. Choose MestReNova.exe in the GUI or set AUTO_SUPPORT_MNOVA_EXE.",
                request.mnova_exe,
                detail=str(exc),
            )
        ]
    return []


def _check_mnova_script(script_path: Path) -> list[Issue]:
    if script_path.exists():
        return []
    return [
        _issue(
            "PREFLIGHT_MNOVA_SCRIPT_MISSING",
            "error",
            "MestReNova automation script was not found. Reinstall Auto Support Generator or use a complete application bundle.",
            script_path,
        )
    ]


def _mnova_required(request: GenerateSIRequest) -> bool:
    return bool(request.resolved_spectra_source and not request.no_extract_nmr)


def _issue(code: str, severity: str, message: str, path: str | Path | None = None, *, detail: str = "") -> Issue:
    issue: Issue = {"code": code, "severity": severity, "message": message}
    if path:
        issue["path"] = str(path)
    if detail:
        issue["detail"] = detail
    return issue
