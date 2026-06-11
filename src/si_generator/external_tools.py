from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path


def find_mnova_executable(explicit_path: str | Path | None = None) -> Path:
    """Find MestReNova on the current Windows machine.

    Search order is deterministic: explicit path, environment variables, PATH,
    Windows registry, then common installation folders.
    """
    if explicit_path:
        explicit = _clean_path(explicit_path)
        if explicit.is_file():
            return explicit.resolve()
        raise FileNotFoundError(f"Selected MestReNova executable does not exist: {explicit}")

    candidates: list[Path] = []

    for name in ["AUTO_SUPPORT_MNOVA_EXE", "AUTO_SI_MNOVA_EXE", "MNOVA_EXE", "MESTRENOVA_EXE"]:
        value = os.environ.get(name)
        if value:
            candidates.append(Path(value))

    for executable in ["MestReNova.exe", "Mnova.exe"]:
        found = shutil.which(executable)
        if found:
            candidates.append(Path(found))

    candidates.extend(_mnova_registry_candidates())
    candidates.extend(_mnova_common_path_candidates())

    for candidate in _unique_paths(candidates):
        if candidate.is_file():
            return candidate.resolve()

    searched = "\n".join(f"  - {path}" for path in _unique_paths(candidates)) or "  - no candidate paths"
    raise FileNotFoundError(
        "MestReNova executable was not found. Install MestReNova, add it to PATH, "
        "set AUTO_SUPPORT_MNOVA_EXE, or choose MestReNova.exe in the GUI.\n"
        f"Searched:\n{searched}"
    )


def _mnova_registry_candidates() -> list[Path]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []

    roots = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
    candidates: list[Path] = []

    for root in roots:
        candidates.extend(_registry_app_paths(winreg, root, "MestReNova.exe"))
        candidates.extend(_registry_app_paths(winreg, root, "Mnova.exe"))

    uninstall_subkeys = [
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
        r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]
    for root in roots:
        for subkey in uninstall_subkeys:
            candidates.extend(_registry_uninstall_candidates(winreg, root, subkey))

    return candidates


def _registry_app_paths(winreg, root, executable: str) -> list[Path]:
    key_path = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{executable}"
    try:
        with winreg.OpenKey(root, key_path) as key:
            value, _ = winreg.QueryValueEx(key, "")
    except OSError:
        return []
    return [Path(value)] if value else []


def _registry_uninstall_candidates(winreg, root, subkey: str) -> list[Path]:
    candidates: list[Path] = []
    try:
        with winreg.OpenKey(root, subkey) as parent:
            count = winreg.QueryInfoKey(parent)[0]
            for index in range(count):
                try:
                    child_name = winreg.EnumKey(parent, index)
                    with winreg.OpenKey(parent, child_name) as child:
                        display_name = _registry_value(winreg, child, "DisplayName")
                        if "mestrenova" not in display_name.lower() and "mnova" not in display_name.lower():
                            continue
                        install_location = _registry_value(winreg, child, "InstallLocation")
                        display_icon = _registry_value(winreg, child, "DisplayIcon")
                        if install_location:
                            candidates.extend(_mnova_exes_in_folder(Path(install_location)))
                        if display_icon:
                            candidates.append(Path(display_icon.split(",", 1)[0].strip('"')))
                except OSError:
                    continue
    except OSError:
        return []
    return candidates


def _registry_value(winreg, key, name: str) -> str:
    try:
        value, _ = winreg.QueryValueEx(key, name)
    except OSError:
        return ""
    return str(value or "")


def _mnova_common_path_candidates() -> list[Path]:
    roots = [
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("LOCALAPPDATA"),
    ]
    candidates: list[Path] = []
    for raw_root in roots:
        if not raw_root:
            continue
        root = Path(raw_root)
        candidates.extend(_mnova_exes_in_folder(root / "Mestrelab Research S.L" / "MestReNova"))
        candidates.extend(_mnova_exes_in_folder(root / "MestReNova"))
        candidates.extend(root.glob("Mestrelab Research*/*/MestReNova.exe"))
        candidates.extend(root.glob("Mestrelab Research*/*/Mnova.exe"))
    return candidates


def _mnova_exes_in_folder(folder: Path) -> list[Path]:
    return [folder / "MestReNova.exe", folder / "Mnova.exe"]


def _unique_paths(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        cleaned = _clean_path(path)
        key = str(cleaned).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _clean_path(path: str | Path) -> Path:
    return Path(str(path).strip().strip('"'))


def make_ascii_work_dir(prefix: str) -> Path:
    """Create a writable ASCII-only temporary directory.

    Some external chemistry tools still mis-handle Unicode paths passed through
    script files or command-line bridges. Prefer C:\\Users\\Public because it is
    normally writable for non-admin users and stays ASCII on Windows.
    """
    roots = [
        os.environ.get("AUTO_SUPPORT_TEMP_DIR"),
        str(Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "AutoSupportGenerator" / "temp"),
        r"C:\AutoSupportGeneratorTemp",
        os.environ.get("TEMP"),
    ]
    errors: list[str] = []
    for raw_root in roots:
        if not raw_root:
            continue
        root = Path(raw_root)
        if not str(root).isascii():
            continue
        try:
            root.mkdir(parents=True, exist_ok=True)
            work_dir = root / f"{prefix}_{uuid.uuid4().hex}"
            work_dir.mkdir(parents=True, exist_ok=False)
            return work_dir
        except OSError as exc:
            errors.append(f"{root}: {exc}")
    details = "\n".join(f"  - {item}" for item in errors) or "  - no ASCII writable temp root found"
    raise RuntimeError("Could not create an ASCII-only temporary folder for external tools.\n" + details)
