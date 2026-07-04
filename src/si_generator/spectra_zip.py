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

        spectra = _find_bruker_spectra(compound_dir)
        if not compound.h1_spectrum_path and spectra.get("1H"):
            compound.h1_spectrum_path = str(spectra["1H"])
        if not compound.c13_spectrum_path and spectra.get("13C"):
            compound.c13_spectrum_path = str(spectra["13C"])


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
