from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


APP_NAME = "Auto Support Generator"
INSTALL_DIR_NAME = "AutoSupportGenerator"


def main() -> int:
    quiet = any(arg.lower() in {"/q", "/quiet", "--quiet", "-q"} for arg in sys.argv[1:])
    try:
        app_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / INSTALL_DIR_NAME
        _install_payload(app_dir)
        _create_shortcuts(app_dir)
        if not quiet:
            _show_message("Installation finished.", f"{APP_NAME} was installed successfully.")
            _launch_app(app_dir)
        return 0
    except Exception as exc:
        _show_message("Installation failed", str(exc), error=True)
        return 1


def _payload_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "payload"
    return Path(__file__).resolve().parents[1] / "dist" / "installer_payload"


def _install_payload(app_dir: Path) -> None:
    payload = _payload_root()
    if not payload.exists():
        raise RuntimeError(f"Installer payload was not found: {payload}")

    examples_dir = app_dir / "examples"
    app_dir.mkdir(parents=True, exist_ok=True)
    examples_dir.mkdir(parents=True, exist_ok=True)

    copies = {
        "AutoSupportGenerator.exe": app_dir / "AutoSupportGenerator.exe",
        "style_config.example.yml": app_dir / "style_config.example.yml",
        "README.md": app_dir / "README.md",
        "INSTALL_RU.md": app_dir / "INSTALL_RU.md",
        "sample_compounds.csv": examples_dir / "sample_compounds.csv",
        "generated_support_example.docx": examples_dir / "generated_support_example.docx",
    }
    for source_name, destination in copies.items():
        source = payload / source_name
        if not source.exists():
            raise RuntimeError(f"Installer payload file is missing: {source_name}")
        shutil.copy2(source, destination)


def _create_shortcuts(app_dir: Path) -> None:
    exe_path = app_dir / "AutoSupportGenerator.exe"
    script = r"""
param([string]$AppDir, [string]$ExePath)
$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$desktopShortcut = $shell.CreateShortcut((Join-Path $desktop 'Auto Support Generator.lnk'))
$desktopShortcut.TargetPath = $ExePath
$desktopShortcut.WorkingDirectory = $AppDir
$desktopShortcut.Save()

$programs = [Environment]::GetFolderPath('Programs')
$menuDir = Join-Path $programs 'Auto Support Generator'
New-Item -ItemType Directory -Force -Path $menuDir | Out-Null
$menuShortcut = $shell.CreateShortcut((Join-Path $menuDir 'Auto Support Generator.lnk'))
$menuShortcut.TargetPath = $ExePath
$menuShortcut.WorkingDirectory = $AppDir
$menuShortcut.Save()
"""
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
            str(app_dir),
            str(exe_path),
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _launch_app(app_dir: Path) -> None:
    exe_path = app_dir / "AutoSupportGenerator.exe"
    subprocess.Popen([str(exe_path)], cwd=str(app_dir))


def _show_message(title: str, message: str, error: bool = False) -> None:
    try:
        import ctypes

        icon = 0x10 if error else 0x40
        ctypes.windll.user32.MessageBoxW(0, message, title, icon)
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
