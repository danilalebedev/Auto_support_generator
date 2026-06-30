from __future__ import annotations

import shutil
from pathlib import Path


LEGACY_GENERATED_FILES = (
    "support_information.docx",
    "support_information.manifest.json",
    "support_information.run_summary.json",
    "processed_spectra.zip",
)
LEGACY_GENERATED_DIRS = (
    "processed_spectra",
    "processed_mnova",
    "mnova_reports",
)


def output_root_for(output_path: str | Path) -> Path:
    path = Path(output_path)
    if path.parent.name.lower() == "docx":
        return path.parent.parent
    return path.parent


def support_docx_path(output_path: str | Path) -> Path:
    path = Path(output_path)
    if path.parent.name.lower() == "docx":
        return path
    return output_root_for(path) / "docx" / path.name


def output_dirs(output_path: str | Path) -> dict[str, Path]:
    root = output_root_for(output_path)
    return {
        "output_root": root,
        "docx_dir": root / "docx",
        "input_dir": root / "input",
        "logs_dir": root / "logs",
        "mnova_dir": root / "mnova",
        "processed_mnova_dir": root / "mnova" / "processed",
        "spectra_dir": root / "spectra",
        "processed_spectra_dir": root / "spectra" / "processed_spectra",
        "processed_spectra_zip": root / "spectra" / "processed_spectra.zip",
        "mnova_reports_dir": root / "logs" / "mnova_reports",
    }


def prepare_output_layout(output_path: str | Path) -> dict[str, Path]:
    dirs = output_dirs(output_path)
    root = dirs["output_root"]
    root.mkdir(parents=True, exist_ok=True)
    _remove_legacy_generated_paths(root)
    for key in ("docx_dir", "input_dir", "logs_dir", "mnova_dir", "spectra_dir"):
        dirs[key].mkdir(parents=True, exist_ok=True)
    return dirs


def _remove_legacy_generated_paths(root: Path) -> None:
    for name in LEGACY_GENERATED_FILES:
        path = root / name
        if path.exists() and path.is_file():
            path.unlink()
    for name in LEGACY_GENERATED_DIRS:
        path = root / name
        if path.exists() and path.is_dir():
            shutil.rmtree(path)
