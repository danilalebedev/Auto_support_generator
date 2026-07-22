from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox, ttk


APP_NAME = "Auto Support Generator"
INSTALL_DIR_NAME = "AutoSupportGenerator"
APP_EXE_NAME = "AutoSupportGenerator.exe"
LOG_FILE_NAME = "install.log"

PAYLOAD_FILES = (
    APP_EXE_NAME,
    "README.md",
    "README_RU.md",
    "README_EN.md",
    "INSTALL_RU.md",
    "RELEASE_BETA_1_2.md",
)
PAYLOAD_DIRS = ("examples", "docs")


def main() -> int:
    raw_args = sys.argv[1:]
    args = _normalized_args(raw_args)
    quiet = _has_any(args, {"/q", "/quiet", "--quiet", "-q"})
    no_shortcuts = "--no-shortcuts" in args
    no_launch = quiet or "--no-launch" in args
    app_dir = _install_dir_from_args(raw_args) or _default_install_dir()

    if not quiet:
        return _run_gui_installer(app_dir, create_shortcuts=not no_shortcuts, launch_after_install=not no_launch)

    return _install_noninteractive(app_dir, quiet=True, create_shortcuts=not no_shortcuts, launch_after_install=False)


def _install_noninteractive(
    app_dir: Path,
    *,
    quiet: bool,
    create_shortcuts: bool,
    launch_after_install: bool,
) -> int:
    app_dir = Path(app_dir)

    try:
        _install_payload(app_dir)
        warnings: list[str] = []
        if not create_shortcuts:
            warnings.append("Shortcuts were skipped.")
        else:
            try:
                _create_shortcuts(app_dir)
            except Exception as exc:
                warnings.append(f"Shortcuts were not created: {exc}")

        _validate_install(app_dir)
        _write_install_log(app_dir, "Installation completed.", warnings)

        if quiet:
            return 0

        message = f"{APP_NAME} was installed successfully.\n\nLocation:\n{app_dir}"
        if warnings:
            message += "\n\n" + "\n".join(warnings)
        _show_message("Installation finished", message)
        if launch_after_install:
            _launch_app(app_dir)
        return 0
    except Exception as exc:
        try:
            _write_install_log(app_dir, f"Installation failed: {exc}", [])
        except Exception:
            pass
        if quiet:
            print(f"Installation failed: {exc}", file=sys.stderr)
        else:
            _show_message("Installation failed", str(exc), error=True)
        return 1


def _run_gui_installer(
    initial_install_dir: Path,
    *,
    create_shortcuts: bool,
    launch_after_install: bool,
) -> int:
    root = Tk()
    root.title(f"{APP_NAME} Setup")
    root.resizable(False, False)

    install_dir = StringVar(value=str(initial_install_dir))
    shortcuts = BooleanVar(value=create_shortcuts)
    launch = BooleanVar(value=launch_after_install)
    status = StringVar(value="Ready to install.")
    result_code = {"value": 1}

    frame = ttk.Frame(root, padding=18)
    frame.grid(row=0, column=0, sticky="nsew")
    frame.columnconfigure(0, weight=1)

    title = ttk.Label(frame, text=APP_NAME, font=("Segoe UI", 16, "bold"))
    title.grid(row=0, column=0, columnspan=3, sticky="w")
    subtitle = ttk.Label(frame, text="Choose where to install the application.")
    subtitle.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 16))

    ttk.Label(frame, text="Install folder").grid(row=2, column=0, columnspan=3, sticky="w")
    path_entry = ttk.Entry(frame, textvariable=install_dir, width=62)
    path_entry.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 8))

    def browse() -> None:
        selected = filedialog.askdirectory(initialdir=str(Path(install_dir.get()).parent), title="Choose install folder")
        if selected:
            install_dir.set(str(Path(selected)))

    ttk.Button(frame, text="Browse...", command=browse).grid(row=3, column=2, sticky="ew", padx=(8, 0), pady=(4, 8))
    ttk.Checkbutton(frame, text="Create desktop and Start menu shortcuts", variable=shortcuts).grid(
        row=4, column=0, columnspan=3, sticky="w"
    )
    ttk.Checkbutton(frame, text=f"Launch {APP_NAME} after installation", variable=launch).grid(
        row=5, column=0, columnspan=3, sticky="w", pady=(2, 14)
    )

    progress = ttk.Progressbar(frame, mode="indeterminate", length=420)
    progress.grid(row=6, column=0, columnspan=3, sticky="ew")
    ttk.Label(frame, textvariable=status).grid(row=7, column=0, columnspan=3, sticky="w", pady=(8, 16))

    button_row = ttk.Frame(frame)
    button_row.grid(row=8, column=0, columnspan=3, sticky="e")
    install_button = ttk.Button(button_row, text="Install")
    cancel_button = ttk.Button(button_row, text="Cancel", command=root.destroy)
    install_button.grid(row=0, column=0, padx=(0, 8))
    cancel_button.grid(row=0, column=1)

    def set_controls_enabled(enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for widget in (path_entry, install_button, cancel_button):
            widget.configure(state=state)

    def install() -> None:
        raw_destination = install_dir.get().strip().strip('"')
        if not raw_destination:
            messagebox.showerror("Installation failed", "Choose an install folder.")
            return
        destination = Path(raw_destination)
        set_controls_enabled(False)
        progress.start(12)
        status.set("Installing...")
        root.update_idletasks()
        code = _install_noninteractive(
            destination,
            quiet=False,
            create_shortcuts=shortcuts.get(),
            launch_after_install=launch.get(),
        )
        progress.stop()
        result_code["value"] = code
        if code == 0:
            status.set("Installation completed.")
            root.destroy()
        else:
            status.set("Installation failed.")
            set_controls_enabled(True)

    install_button.configure(command=install)
    path_entry.focus_set()
    _center_window(root)
    root.mainloop()
    return result_code["value"]


def _center_window(root: Tk) -> None:
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = max((root.winfo_screenwidth() - width) // 2, 0)
    y = max((root.winfo_screenheight() - height) // 2, 0)
    root.geometry(f"{width}x{height}+{x}+{y}")


def _install_dir_from_args(raw_args: list[str]) -> Path | None:
    for index, arg in enumerate(raw_args):
        lowered = arg.lower()
        if lowered in {"--install-dir", "/install-dir"} and index + 1 < len(raw_args):
            return Path(raw_args[index + 1].strip('"'))
        for prefix in ("--install-dir=", "/install-dir="):
            if lowered.startswith(prefix):
                return Path(arg[len(prefix) :].strip('"'))
    return None


def _normalized_args(raw_args: list[str]) -> set[str]:
    return {arg.lower() for arg in raw_args}


def _has_any(args: set[str], choices: set[str]) -> bool:
    return bool(args.intersection(choices))


def _default_install_dir(*, environ: dict[str, str] | None = None) -> Path:
    env = environ if environ is not None else os.environ
    root = env.get("LOCALAPPDATA") or str(Path.home())
    return Path(root) / INSTALL_DIR_NAME


def _payload_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "payload"
    return Path(__file__).resolve().parents[1] / "dist" / "installer_payload"


def _install_payload(app_dir: Path) -> None:
    payload = _payload_root()
    _validate_payload(payload)

    app_dir = app_dir.resolve()
    app_dir.parent.mkdir(parents=True, exist_ok=True)
    app_dir.mkdir(parents=True, exist_ok=True)

    for filename in PAYLOAD_FILES:
        _copy_file(payload / filename, app_dir / filename)

    for dirname in PAYLOAD_DIRS:
        source = payload / dirname
        if source.exists():
            _replace_directory(source, app_dir / dirname, app_dir)


def _validate_payload(payload: Path) -> None:
    if not payload.exists():
        raise RuntimeError(f"Installer payload was not found: {payload}")
    if not payload.is_dir():
        raise RuntimeError(f"Installer payload is not a folder: {payload}")

    missing_files = [filename for filename in PAYLOAD_FILES if not (payload / filename).is_file()]
    if missing_files:
        raise RuntimeError("Installer payload is missing files: " + ", ".join(missing_files))

    examples = payload / "examples"
    if not examples.is_dir():
        raise RuntimeError("Installer payload examples folder is missing.")
    if not any(examples.iterdir()):
        raise RuntimeError("Installer payload examples folder is empty.")


def _validate_install(app_dir: Path) -> None:
    exe_path = app_dir / APP_EXE_NAME
    if not exe_path.is_file():
        raise RuntimeError(f"{APP_EXE_NAME} was not installed: {exe_path}")
    if not (app_dir / "examples").is_dir():
        raise RuntimeError("Examples were not installed.")


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_destination = destination.with_name(destination.name + ".installing")
    try:
        if temp_destination.exists():
            _remove_path(temp_destination)
        shutil.copy2(source, temp_destination)
        temp_destination.replace(destination)
    except PermissionError as exc:
        raise RuntimeError(
            f"Cannot replace {destination.name}. Close {APP_NAME} if it is running and start the installer again."
        ) from exc
    finally:
        if temp_destination.exists():
            _remove_path(temp_destination)


def _replace_directory(source: Path, destination: Path, install_root: Path) -> None:
    _assert_managed_path(destination, install_root)
    staging = destination.with_name("." + destination.name + ".installing")
    backup = destination.with_name("." + destination.name + ".previous")
    _assert_managed_path(staging, install_root)
    _assert_managed_path(backup, install_root)

    for path in (staging, backup):
        if path.exists():
            _remove_path(path)

    shutil.copytree(source, staging)
    try:
        if destination.exists():
            destination.replace(backup)
        staging.replace(destination)
    except Exception:
        if destination.exists():
            _remove_path(destination)
        if backup.exists():
            backup.replace(destination)
        raise
    finally:
        for path in (staging, backup):
            if path.exists():
                _remove_path(path)


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def _assert_managed_path(path: Path, install_root: Path) -> None:
    resolved_root = install_root.resolve()
    resolved_path = path.resolve()
    if resolved_path == resolved_root or resolved_root not in resolved_path.parents:
        raise RuntimeError(f"Refusing to modify a path outside the install folder: {resolved_path}")


def _create_shortcuts(app_dir: Path) -> None:
    exe_path = app_dir / APP_EXE_NAME
    with tempfile.TemporaryDirectory(prefix="auto_si_shortcut_") as tmp:
        script_path = Path(tmp) / "create_shortcuts.ps1"
        script_path.write_text(_shortcut_script(), encoding="utf-8")
        result = subprocess.run(
            _shortcut_command(script_path, app_dir, exe_path),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or f"PowerShell exited with code {result.returncode}")


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
if (-not [string]::IsNullOrWhiteSpace($desktop)) {
    New-AutoSupportShortcut -ShortcutPath (Join-Path $desktop 'Auto Support Generator.lnk')
}

$programs = [Environment]::GetFolderPath('Programs')
if (-not [string]::IsNullOrWhiteSpace($programs)) {
    $menuDir = Join-Path $programs 'Auto Support Generator'
    New-Item -ItemType Directory -Force -Path $menuDir | Out-Null
    New-AutoSupportShortcut -ShortcutPath (Join-Path $menuDir 'Auto Support Generator.lnk')
}
"""


def _launch_app(app_dir: Path) -> None:
    exe_path = app_dir / APP_EXE_NAME
    subprocess.Popen([str(exe_path)], cwd=str(app_dir))


def _write_install_log(app_dir: Path, status: str, warnings: list[str]) -> None:
    app_dir.mkdir(parents=True, exist_ok=True)
    lines = [status, f"Install directory: {app_dir}"]
    lines.extend(warnings)
    (app_dir / LOG_FILE_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _show_message(title: str, message: str, error: bool = False) -> None:
    try:
        import ctypes

        icon = 0x10 if error else 0x40
        ctypes.windll.user32.MessageBoxW(0, message, title, icon)
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
