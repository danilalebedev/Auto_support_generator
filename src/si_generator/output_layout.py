from __future__ import annotations

import shutil
from pathlib import Path
import re


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
        "reports_dir": root / "reports",
        "mnova_dir": root / "mnova",
        "processed_mnova_dir": root / "mnova" / "processed",
        "spectra_dir": root / "spectra",
        "processed_spectra_dir": root / "spectra" / "processed_spectra",
        "processed_spectra_zip": root / "spectra" / "processed_spectra.zip",
        "mnova_reports_dir": root / "logs" / "mnova_reports",
    }


def create_run_output_root(input_path: str | Path, requested_output: str | Path, run_id: str) -> Path:
    requested = Path(requested_output)
    base = _requested_output_base(requested)
    cleanup_legacy_output_root(base)
    run_parent = base if base.name.lower() == "runs" else base / "runs"
    run_parent.mkdir(parents=True, exist_ok=True)
    stem = _safe_stem(Path(input_path).stem) or "support"
    run_stamp = _safe_stem(str(run_id).replace("T", "_")) or "run"
    candidate = run_parent / f"{run_stamp}_{stem}"
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        indexed = run_parent / f"{candidate.name}_{index}"
        if not indexed.exists():
            return indexed
    raise ValueError(f"Cannot create a unique output run folder under {run_parent}")


def prepare_output_layout(output_path: str | Path, *, input_path: str | Path | None = None, run_id: str = "") -> dict[str, Path]:
    if input_path and run_id:
        run_root = create_run_output_root(input_path, output_path, run_id)
        output_name = Path(output_path).name if Path(output_path).suffix.lower() == ".docx" else "support_information.docx"
        dirs = output_dirs(run_root / "docx" / output_name)
    else:
        dirs = output_dirs(output_path)
    root = dirs["output_root"]
    root.mkdir(parents=True, exist_ok=True)
    cleanup_legacy_output_root(root)
    for key in ("docx_dir", "input_dir", "logs_dir", "reports_dir", "mnova_dir", "spectra_dir"):
        dirs[key].mkdir(parents=True, exist_ok=True)
    dirs["support_docx"] = dirs["docx_dir"] / (Path(output_path).name if Path(output_path).suffix.lower() == ".docx" else "support_information.docx")
    return dirs


def cleanup_legacy_output_root(root: str | Path) -> None:
    root = Path(root)
    for name in LEGACY_GENERATED_FILES:
        path = root / name
        if path.exists() and path.is_file():
            path.unlink()
    for name in LEGACY_GENERATED_DIRS:
        path = root / name
        if path.exists() and path.is_dir():
            shutil.rmtree(path)


def _requested_output_base(path: Path) -> Path:
    if path.suffix.lower() == ".docx":
        if path.parent.name.lower() == "docx" and path.parent.parent.name:
            return path.parent.parent
        return path.parent
    return path


def _safe_stem(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return safe.strip("._-")
