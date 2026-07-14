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
    no_shortcuts = "--no-shortcuts" in {arg.lower() for arg in sys.argv[1:]}
    try:
        app_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / INSTALL_DIR_NAME
        _install_payload(app_dir)
        if not no_shortcuts:
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
    if examples_dir.exists():
        shutil.rmtree(examples_dir)

    copies = {
        "AutoSupportGenerator.exe": app_dir / "AutoSupportGenerator.exe",
        "README.md": app_dir / "README.md",
        "README_RU.md": app_dir / "README_RU.md",
        "README_EN.md": app_dir / "README_EN.md",
        "INSTALL_RU.md": app_dir / "INSTALL_RU.md",
        "RELEASE_BETA_1_2.md": app_dir / "RELEASE_BETA_1_2.md",
    }
    for source_name, destination in copies.items():
        source = payload / source_name
        if not source.exists():
            raise RuntimeError(f"Installer payload file is missing: {source_name}")
        shutil.copy2(source, destination)
    examples_source = payload / "examples"
    if not examples_source.exists():
        raise RuntimeError("Installer payload examples folder is missing.")
    shutil.copytree(examples_source, examples_dir)
    docs_source = payload / "docs"
    if docs_source.exists():
        docs_dir = app_dir / "docs"
        if docs_dir.exists():
            shutil.rmtree(docs_dir)
        shutil.copytree(docs_source, docs_dir)


def _create_shortcuts(app_dir: Path) -> None:
    exe_path = app_dir / "AutoSupportGenerator.exe"
    with tempfile.TemporaryDirectory(prefix="auto_si_shortcut_") as tmp:
        script_path = Path(tmp) / "create_shortcuts.ps1"
        script_path.write_text(_shortcut_script(), encoding="utf-8")
        subprocess.run(
            _shortcut_command(script_path, app_dir, exe_path),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _shortcut_command(script_path: Path, app_dir: Path, exe_path: Path) -> list[str]:
    return [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-AppDir",
        str(app_dir),
        "-ExePath",
        str(exe_path),
    ]


def _shortcut_script() -> str:
    return r"""
param(
    [Parameter(Mandatory=$true)][string]$AppDir,
    [Parameter(Mandatory=$true)][string]$ExePath
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $ExePath -PathType Leaf)) {
    throw "AutoSupportGenerator.exe was not found: $ExePath"
}

$shell = New-Object -ComObject WScript.Shell

function New-AutoSupportShortcut {
    param([string]$ShortcutPath)
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $ExePath
    $shortcut.Arguments = ''
    $shortcut.WorkingDirectory = $AppDir
    $shortcut.IconLocation = "$ExePath,0"
    $shortcut.Description = 'Auto Support Generator'
    $shortcut.Save()

    $saved = $shell.CreateShortcut($ShortcutPath)
    if ($saved.TargetPath -ne $ExePath) {
        throw "Shortcut target was not saved correctly: $ShortcutPath"
    }
}

$desktop = [Environment]::GetFolderPath('Desktop')
New-AutoSupportShortcut -ShortcutPath (Join-Path $desktop 'Auto Support Generator.lnk')

$programs = [Environment]::GetFolderPath('Programs')
$menuDir = Join-Path $programs 'Auto Support Generator'
New-Item -ItemType Directory -Force -Path $menuDir | Out-Null
New-AutoSupportShortcut -ShortcutPath (Join-Path $menuDir 'Auto Support Generator.lnk')
"""


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
