from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

from .domain.compound import Compound


MAX_SPECTRA_ZIP_MEMBERS = 100_000
MAX_SPECTRA_ZIP_UNCOMPRESSED_BYTES = 10 * 1024 * 1024 * 1024
ZIP_UNIX_SYMLINK_MODE = 0o120000
ZIP_UNIX_FILE_TYPE_MASK = 0o170000


def prepare_spectra_source(
    source_path: str | Path,
    work_dir: str | Path,
    *,
    max_members: int = MAX_SPECTRA_ZIP_MEMBERS,
    max_uncompressed_bytes: int = MAX_SPECTRA_ZIP_UNCOMPRESSED_BYTES,
) -> Path:
    source_path = Path(source_path).resolve()
    if source_path.is_dir():
        return source_path
    return prepare_spectra_zip(
        source_path,
        work_dir,
        max_members=max_members,
        max_uncompressed_bytes=max_uncompressed_bytes,
    )


def prepare_spectra_zip(
    zip_path: str | Path,
    work_dir: str | Path,
    *,
    max_members: int = MAX_SPECTRA_ZIP_MEMBERS,
    max_uncompressed_bytes: int = MAX_SPECTRA_ZIP_UNCOMPRESSED_BYTES,
) -> Path:
    zip_path = Path(zip_path).resolve()
    work_dir = Path(work_dir).resolve() / zip_path.stem
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as archive:
        _safe_extract(
            archive,
            work_dir,
            max_members=max_members,
            max_uncompressed_bytes=max_uncompressed_bytes,
        )

    children = [path for path in work_dir.iterdir() if path.is_dir()]
    if len(children) == 1 and not _looks_like_compound_dir(children[0]):
        return children[0]
    return work_dir


def assign_spectra_from_folder(compounds: list[Compound], spectra_root: str | Path) -> None:
    spectra_root = Path(spectra_root).resolve()
    for compound in compounds:
        compound_dir = spectra_root / compound.number
        if not compound_dir.exists():
            continue

        _assign_compound_artifact_folders(compound, compound_dir)
        spectra = _find_bruker_spectra(compound_dir)
        if not compound.h1_spectrum_path and spectra.get("1H"):
            compound.h1_spectrum_path = str(spectra["1H"])
        if not compound.c13_spectrum_path and spectra.get("13C"):
            compound.c13_spectrum_path = str(spectra["13C"])


def spectra_source_compound_numbers(spectra_root: str | Path) -> set[str]:
    spectra_root = Path(spectra_root).resolve()
    if not spectra_root.exists() or not spectra_root.is_dir():
        return set()
    return {
        child.name.strip()
        for child in spectra_root.iterdir()
        if child.is_dir() and child.name.strip() and not _ignored_source_dir(child.name)
    }


def validate_spectra_zip(
    archive: zipfile.ZipFile,
    target: str | Path,
    *,
    max_members: int = MAX_SPECTRA_ZIP_MEMBERS,
    max_uncompressed_bytes: int = MAX_SPECTRA_ZIP_UNCOMPRESSED_BYTES,
) -> None:
    target = Path(target).resolve()
    members = archive.infolist()
    if len(members) > max_members:
        raise ValueError(f"Spectra zip contains too many entries: {len(members)} > {max_members}")

    total_size = 0
    for member in members:
        _validate_zip_member_path(target, member.filename)
        _validate_zip_member_type(member)
        if not member.is_dir():
            total_size += int(member.file_size)
        if total_size > max_uncompressed_bytes:
            limit_mb = max_uncompressed_bytes // (1024 * 1024)
            raise ValueError(f"Spectra zip is too large after extraction: more than {limit_mb} MB")


def _safe_extract(
    archive: zipfile.ZipFile,
    target: Path,
    *,
    max_members: int = MAX_SPECTRA_ZIP_MEMBERS,
    max_uncompressed_bytes: int = MAX_SPECTRA_ZIP_UNCOMPRESSED_BYTES,
) -> None:
    target = target.resolve()
    validate_spectra_zip(
        archive,
        target,
        max_members=max_members,
        max_uncompressed_bytes=max_uncompressed_bytes,
    )
    for member in archive.infolist():
        archive.extract(member, target)


def _validate_zip_member_path(target: Path, filename: str) -> None:
    normalized = filename.replace("\\", "/")
    if "\0" in normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise ValueError(f"Unsafe path in zip: {filename}")
    destination = (target / normalized).resolve()
    if target != destination and target not in destination.parents:
        raise ValueError(f"Unsafe path in zip: {filename}")


def _validate_zip_member_type(member: zipfile.ZipInfo) -> None:
    mode = (member.external_attr >> 16) & ZIP_UNIX_FILE_TYPE_MASK
    if mode == ZIP_UNIX_SYMLINK_MODE:
        raise ValueError(f"Unsafe symlink in zip: {member.filename}")


def _looks_like_compound_dir(path: Path) -> bool:
    return any((child / "fid").exists() for child in path.iterdir() if child.is_dir())


def _ignored_source_dir(name: str) -> bool:
    lowered = name.lower()
    return name.startswith(".") or lowered in {"__macosx", "thumbs.db"}


def _find_bruker_spectra(compound_dir: Path) -> dict[str, Path]:
    candidates: dict[str, list[Path]] = {"1H": [], "13C": []}
    for fid in compound_dir.rglob("fid"):
        experiment = fid.parent
        nucleus = _read_nucleus(experiment)
        if nucleus in candidates:
            candidates[nucleus].append(experiment)

    result: dict[str, Path] = {}
    if candidates["1H"]:
        result["1H"] = _prefer_by_name(candidates["1H"], ["1h", "proton"])
    if candidates["13C"]:
        result["13C"] = _prefer_by_name(candidates["13C"], ["13c"], ["apt", "dept"])
    return result


def _assign_compound_artifact_folders(compound: Compound, compound_dir: Path) -> None:
    cif_folder = _optional_child_folder(compound_dir, "cif")
    cif_files = _files_with_suffix(cif_folder, ".cif")
    if cif_folder and not compound.cif_folder:
        compound.cif_folder = str(cif_folder)
    if cif_files and not compound.cif_files:
        compound.cif_files = [str(path) for path in cif_files]

    spectra_root = _optional_child_folder(compound_dir, "spectra")
    one_d_folder = _first_existing_folder(spectra_root, ("1d", "1D")) if spectra_root else _first_existing_folder(compound_dir, ("1d", "1D"))
    if one_d_folder is None and _find_bruker_spectra(compound_dir):
        one_d_folder = compound_dir
    if one_d_folder and not compound.spectra_1d_folder:
        compound.spectra_1d_folder = str(one_d_folder)
    if one_d_folder and not compound.spectra_1d_files:
        compound.spectra_1d_files = [str(path) for path in _data_files(one_d_folder)]

    two_d_folder = _first_existing_folder(spectra_root, ("2d", "2D")) if spectra_root else _first_existing_folder(compound_dir, ("2d", "2D"))
    two_d_experiments = _find_bruker_2d_spectra(two_d_folder or compound_dir)
    if two_d_folder is None and two_d_experiments:
        two_d_folder = _common_parent(two_d_experiments)
    if two_d_folder and not compound.spectra_2d_folder:
        compound.spectra_2d_folder = str(two_d_folder)
    if two_d_folder and not compound.spectra_2d_files:
        compound.spectra_2d_files = [str(path) for path in _data_files(two_d_folder)]


def _optional_child_folder(root: Path, name: str) -> Path | None:
    path = root / name
    return path if path.is_dir() else None


def _first_existing_folder(root: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        path = root / name
        if path.is_dir():
            return path
    return None


def _files_with_suffix(folder: Path | None, suffix: str) -> list[Path]:
    if folder is None:
        return []
    return sorted((path for path in folder.rglob(f"*{suffix}") if path.is_file()), key=lambda path: str(path).casefold())


def _data_files(folder: Path) -> list[Path]:
    ignored_names = {"readme.txt", ".ds_store", "thumbs.db"}
    return sorted(
        (path for path in folder.rglob("*") if path.is_file() and path.name.casefold() not in ignored_names),
        key=lambda path: str(path).casefold(),
    )


def _find_bruker_2d_spectra(compound_dir: Path) -> list[Path]:
    if not compound_dir.exists():
        return []
    experiments: list[Path] = []
    for ser in compound_dir.rglob("ser"):
        experiment = ser.parent
        if (experiment / "acqu2").exists() or (experiment / "acqu2s").exists():
            experiments.append(experiment)
    return sorted(experiments, key=lambda path: str(path).casefold())


def _common_parent(paths: list[Path]) -> Path:
    if not paths:
        raise ValueError("Cannot compute a common parent for an empty path list.")
    common = Path(paths[0])
    for path in paths[1:]:
        while common != path and common not in path.parents:
            common = common.parent
    return common


def _read_nucleus(experiment: Path) -> str:
    for filename in ["acqus", "acqu"]:
        path = experiment / filename
        if not path.exists():
            continue
        text = path.read_text(encoding="latin1", errors="ignore")
        if "##$NUC1= <1H>" in text:
            return "1H"
        if "##$NUC1= <13C>" in text:
            return "13C"
    return ""


def _prefer_by_name(paths: list[Path], include: list[str], exclude: list[str] | None = None) -> Path:
    exclude = exclude or []

    def score(path: Path) -> tuple[int, str]:
        name = path.name.lower()
        value = 0
        if any(token in name for token in include):
            value -= 10
        if any(token in name for token in exclude):
            value += 10
        return value, str(path)

    return sorted(paths, key=score)[0]
