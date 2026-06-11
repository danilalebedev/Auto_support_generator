from __future__ import annotations

import uuid
import zipfile
from collections.abc import Callable
from pathlib import Path

from .external_tools import find_mnova_executable
from .graph.state import GenerateSIRequest, Issue
from .mnova import SCRIPT_PATH


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
    if request.spectra_zip:
        issues.extend(_check_spectra_zip(request.spectra_zip))
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


def _check_spectra_zip(spectra_zip: Path) -> list[Issue]:
    if not spectra_zip.exists():
        return [_issue("PREFLIGHT_SPECTRA_ZIP_MISSING", "error", "Spectra zip does not exist.", spectra_zip)]
    if not zipfile.is_zipfile(spectra_zip):
        return [_issue("PREFLIGHT_SPECTRA_ZIP_INVALID", "error", "Spectra file is not a readable zip archive.", spectra_zip)]
    try:
        with zipfile.ZipFile(spectra_zip) as archive:
            if not archive.namelist():
                return [_issue("PREFLIGHT_SPECTRA_ZIP_EMPTY", "warning", "Spectra zip archive is empty.", spectra_zip)]
    except OSError as exc:
        return [_issue("PREFLIGHT_SPECTRA_ZIP_INVALID", "error", f"Spectra zip cannot be read: {exc}", spectra_zip)]
    return []


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
    return bool(request.spectra_zip and not request.no_extract_nmr)


def _issue(code: str, severity: str, message: str, path: str | Path | None = None, *, detail: str = "") -> Issue:
    issue: Issue = {"code": code, "severity": severity, "message": message}
    if path:
        issue["path"] = str(path)
    if detail:
        issue["detail"] = detail
    return issue
