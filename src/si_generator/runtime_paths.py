from __future__ import annotations

import os
import sys
from pathlib import Path


APP_DIR_NAME = "AutoSupportGenerator"


def local_app_data_dir(*, environ: dict[str, str] | None = None) -> Path:
    env = environ if environ is not None else os.environ
    return Path(env.get("LOCALAPPDATA", str(Path.home()))) / APP_DIR_NAME


def app_base_dir(
    *,
    package_file: str | Path | None = None,
    frozen: bool | None = None,
    executable: str | Path | None = None,
) -> Path:
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if is_frozen:
        return Path(executable or sys.executable).resolve().parent
    return Path(package_file or __file__).resolve().parents[2]


def bundled_resource_path(
    relative_path: str | Path,
    *,
    package_file: str | Path | None = None,
    bundle_root: str | Path | None = None,
) -> Path:
    relative_path = Path(relative_path)
    root = bundle_root if bundle_root is not None else getattr(sys, "_MEIPASS", None)
    if root:
        return Path(root) / relative_path
    source_layout_path = app_base_dir(package_file=package_file) / relative_path
    if source_layout_path.exists():
        return source_layout_path
    package_resource_path = Path(package_file or __file__).resolve().parent / "resources" / relative_path
    if package_resource_path.exists():
        return package_resource_path
    return source_layout_path


def examples_dir() -> Path:
    return app_base_dir() / "examples"


def default_output_path(*, frozen: bool | None = None, environ: dict[str, str] | None = None) -> Path:
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if is_frozen:
        return local_app_data_dir(environ=environ) / "output" / "docx" / "support_information.docx"
    return Path.cwd() / "output" / "docx" / "support_information.docx"


def gui_settings_path(*, environ: dict[str, str] | None = None) -> Path:
    return local_app_data_dir(environ=environ) / "gui_settings.json"
