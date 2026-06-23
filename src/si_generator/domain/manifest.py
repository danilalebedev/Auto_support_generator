from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .types import Issue


REQUIRED_TOP_LEVEL_KEYS = ("run_id", "order", "compounds")
REQUIRED_COMPOUND_KEYS = ("number", "docx_block_id")
UNRESOLVED_DOCX_PLACEHOLDERS = ("[[STRUCTURE:", "[[SPECTRUM_STRUCTURE:", "[[MNOVA:")


def load_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        raise ValueError(f"{manifest_path}: manifest root must be a JSON object.")
    return manifest


def check_manifest(
    manifest: dict[str, Any],
    *,
    manifest_path: str | Path | None = None,
    support_docx: str | Path | None = None,
    strict_artifacts: bool = True,
) -> list[Issue]:
    issues: list[Issue] = []
    base_dir = Path(manifest_path).resolve().parent if manifest_path else Path.cwd()

    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in manifest:
            issues.append(_issue("MANIFEST_MISSING_KEY", "error", f"manifest is missing '{key}'."))

    order = manifest.get("order", [])
    compounds = manifest.get("compounds", {})
    if not isinstance(order, list):
        issues.append(_issue("MANIFEST_BAD_ORDER", "error", "manifest 'order' must be a list."))
        order = []
    if not isinstance(compounds, dict):
        issues.append(_issue("MANIFEST_BAD_COMPOUNDS", "error", "manifest 'compounds' must be an object."))
        compounds = {}

    issues.extend(_check_compound_entries(order, compounds))
    support_docx_path = _support_docx_path(manifest, base_dir, support_docx)
    issues.extend(_check_support_docx(support_docx_path))
    if support_docx_path and support_docx_path.exists():
        issues.extend(_check_unresolved_docx_placeholders(support_docx_path))
        issues.extend(_check_docx_bookmarks(manifest, support_docx_path))
    if strict_artifacts:
        issues.extend(_check_artifact_paths(manifest, base_dir))

    return issues


def manifest_has_errors(issues: list[Issue]) -> bool:
    return any(issue.get("severity") == "error" for issue in issues)


def _check_compound_entries(order: list[Any], compounds: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    seen_numbers: set[str] = set()
    seen_ids: set[str] = set()

    for item in order:
        compound_id = str(item)
        if compound_id in seen_ids:
            issues.append(_issue("MANIFEST_DUPLICATE_ID", "error", f"compound id '{compound_id}' appears more than once."))
        seen_ids.add(compound_id)

        compound = compounds.get(compound_id)
        if not isinstance(compound, dict):
            issues.append(
                _issue(
                    "MANIFEST_MISSING_COMPOUND",
                    "error",
                    f"compound id '{compound_id}' is listed in order but missing from compounds.",
                    compound_id=compound_id,
                )
            )
            continue

        stored_id = str(compound.get("id") or compound_id)
        if stored_id != compound_id:
            issues.append(
                _issue(
                    "MANIFEST_ID_MISMATCH",
                    "warning",
                    f"compound id '{compound_id}' has stored id '{stored_id}'.",
                    compound_id=compound_id,
                )
            )

        for key in REQUIRED_COMPOUND_KEYS:
            if not compound.get(key):
                issues.append(
                    _issue(
                        "MANIFEST_MISSING_COMPOUND_FIELD",
                        "error",
                        f"compound '{compound_id}' is missing '{key}'.",
                        compound_id=compound_id,
                    )
                )

        number = str(compound.get("number") or "").strip()
        if number:
            if number in seen_numbers:
                issues.append(
                    _issue(
                        "MANIFEST_DUPLICATE_NUMBER",
                        "error",
                        f"compound number '{number}' appears more than once.",
                        compound_id=compound_id,
                    )
                )
            seen_numbers.add(number)

    extra_ids = sorted(set(compounds) - {str(item) for item in order})
    for compound_id in extra_ids:
        issues.append(
            _issue(
                "MANIFEST_UNUSED_COMPOUND",
                "warning",
                f"compound id '{compound_id}' is present but not listed in order.",
                compound_id=compound_id,
            )
        )
    return issues


def _support_docx_path(manifest: dict[str, Any], base_dir: Path, support_docx: str | Path | None) -> Path | None:
    path = Path(support_docx) if support_docx else _manifest_path(manifest, "support_docx", base_dir)
    if not path:
        return None
    return _resolve_manifest_path(path, base_dir)


def _check_support_docx(path: Path | None) -> list[Issue]:
    if not path:
        return [_issue("MANIFEST_MISSING_SUPPORT_DOCX", "error", "support DOCX path is missing from manifest artifacts.")]
    if path.exists():
        return []
    return [
        _issue(
            "MANIFEST_MISSING_SUPPORT_DOCX",
            "error",
            f"support DOCX does not exist: {path}",
            path=str(path),
        )
    ]


def _check_docx_bookmarks(manifest: dict[str, Any], support_docx: Path) -> list[Issue]:
    expected = _expected_docx_bookmarks(manifest)
    if not expected:
        return []
    try:
        actual = _read_docx_bookmarks(support_docx)
    except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        return [
            _issue(
                "DOCX_BOOKMARK_READ_ERROR",
                "error",
                f"could not read DOCX bookmarks from {support_docx}: {exc}",
                path=str(support_docx),
            )
        ]

    issues: list[Issue] = []
    for compound_id, bookmark in expected.items():
        if bookmark not in actual:
            issues.append(
                _issue(
                    "DOCX_MISSING_BOOKMARK",
                    "error",
                    f"bookmark '{bookmark}' for compound '{compound_id}' was not found in support DOCX.",
                    compound_id=compound_id,
                    path=str(support_docx),
                )
            )
    for bookmark in sorted(_unexpected_compound_bookmarks(actual, expected)):
        issues.append(
            _issue(
                "DOCX_UNEXPECTED_COMPOUND_BOOKMARK",
                "warning",
                f"compound bookmark '{bookmark}' was found in support DOCX but is not listed in manifest.",
                path=str(support_docx),
            )
        )
    return issues


def _check_unresolved_docx_placeholders(support_docx: Path) -> list[Issue]:
    try:
        xml = _read_docx_document_xml(support_docx).decode("utf-8", errors="ignore")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        return [
            _issue(
                "DOCX_READ_ERROR",
                "error",
                f"could not read support DOCX {support_docx}: {exc}",
                path=str(support_docx),
            )
        ]
    placeholders = [token for token in UNRESOLVED_DOCX_PLACEHOLDERS if token in xml]
    if not placeholders:
        return []
    return [
        _issue(
            "DOCX_UNRESOLVED_PLACEHOLDER",
            "error",
            "support DOCX still contains unresolved placeholders: " + ", ".join(placeholders),
            path=str(support_docx),
        )
    ]


def _expected_docx_bookmarks(manifest: dict[str, Any]) -> dict[str, str]:
    expected: dict[str, str] = {}
    for compound_id, compound in (manifest.get("compounds", {}) or {}).items():
        if isinstance(compound, dict) and compound.get("docx_bookmark"):
            expected[str(compound_id)] = str(compound["docx_bookmark"])
    return expected


def _read_docx_bookmarks(path: Path) -> set[str]:
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    xml = _read_docx_document_xml(path)
    root = ElementTree.fromstring(xml)
    return {
        str(element.attrib.get(namespace + "name"))
        for element in root.iter(namespace + "bookmarkStart")
        if element.attrib.get(namespace + "name")
    }


def _read_docx_document_xml(path: Path) -> bytes:
    with zipfile.ZipFile(path) as archive:
        return archive.read("word/document.xml")


def _unexpected_compound_bookmarks(actual: set[str], expected: dict[str, str]) -> set[str]:
    expected_bookmarks = set(expected.values())
    return {bookmark for bookmark in actual if bookmark.startswith("asig_compound_") and bookmark not in expected_bookmarks}


def _check_artifact_paths(manifest: dict[str, Any], base_dir: Path) -> list[Issue]:
    issues: list[Issue] = []
    artifact_paths = _combined_artifact_paths(manifest)
    for compound_id, compound in (manifest.get("compounds", {}) or {}).items():
        if isinstance(compound, dict):
            compound_artifacts = dict(compound.get("artifacts", {}) or {})
            compound_artifacts.update(compound.get("relative_artifacts", {}) or {})
            for key, path in compound_artifacts.items():
                artifact_paths[f"{compound_id}.{key}"] = path

    for key, path in artifact_paths.items():
        if not path:
            continue
        resolved = _resolve_manifest_path(path, base_dir)
        if not resolved.exists():
            severity = "error" if key == "support_docx" else "warning"
            issues.append(
                _issue(
                    "MANIFEST_MISSING_ARTIFACT",
                    severity,
                    f"artifact '{key}' does not exist: {resolved}",
                    path=str(resolved),
                )
            )
    return issues


def _manifest_path(manifest: dict[str, Any], key: str, base_dir: Path) -> Path | None:
    candidates = _path_candidates(
        manifest.get("relative_paths", {}),
        manifest.get("artifacts", {}),
        manifest.get("output_paths", {}),
        key=key,
    )
    return _first_existing_or_first(candidates, base_dir)


def _combined_artifact_paths(manifest: dict[str, Any]) -> dict[str, Any]:
    artifact_paths = dict(manifest.get("artifacts", {}) or {})
    artifact_paths.update(manifest.get("output_paths", {}) or {})
    artifact_paths.update(manifest.get("relative_paths", {}) or {})
    return artifact_paths


def _path_candidates(*sources: Any, key: str) -> list[Path]:
    candidates: list[Path] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        value = source.get(key)
        if value:
            candidates.append(Path(value))
    return candidates


def _first_existing_or_first(candidates: list[Path], base_dir: Path) -> Path | None:
    if not candidates:
        return None
    for candidate in candidates:
        resolved = _resolve_manifest_path(candidate, base_dir)
        if resolved.exists():
            return candidate
    return candidates[0]


def _resolve_manifest_path(path: str | Path, base_dir: Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = base_dir / resolved
    return resolved.resolve()


def _issue(code: str, severity: str, message: str, *, compound_id: str = "", path: str = "") -> Issue:
    issue: Issue = {"code": code, "severity": severity, "message": message}
    if compound_id:
        issue["compound_id"] = compound_id
    if path:
        issue["path"] = path
    return issue
