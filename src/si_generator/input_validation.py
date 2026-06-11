from __future__ import annotations

from pathlib import Path

from .chemistry import parse_formula
from .models import Compound


SOLID_STATE_MARKERS = (
    "solid",
    "powder",
    "crystal",
    "тверд",
    "твёрд",
    "порош",
    "кристалл",
)


def validate_compound_inputs(
    compounds: list[Compound],
    *,
    require_structure: bool = False,
    base_dir: str | Path | None = None,
) -> list[str]:
    """Validate input rows and return non-fatal warnings.

    Fatal problems raise ValueError. Optional chemistry fields are reported as
    warnings because users often add spectra, HRMS, mp, or Rf gradually.
    """
    if not compounds:
        raise ValueError("No compounds were found in the input table.")

    errors: list[str] = []
    warnings: list[str] = []
    seen_numbers: set[str] = set()
    resolved_base_dir = Path(base_dir).resolve() if base_dir else None

    for index, compound in enumerate(compounds, start=1):
        label = compound.number.strip() or f"row {index + 1}"
        if not compound.number.strip():
            errors.append(f"{label}: missing compound number.")
        elif compound.number in seen_numbers:
            errors.append(f"{label}: duplicate compound number.")
        seen_numbers.add(compound.number)

        if not compound.name.strip() or compound.name.strip().lower().startswith("compound "):
            warnings.append(f"{label}: missing generated/name field; fallback name will be used.")

        if require_structure and not compound.has_word_structure and not compound.structure_path.strip():
            warnings.append(f"{label}: no structure object/path was found.")

        if not compound.formula.strip():
            warnings.append(f"{label}: formula is missing; HRMS and NMR count checks will be limited.")
        else:
            try:
                parse_formula(compound.formula)
            except ValueError as exc:
                warnings.append(f"{label}: formula could not be parsed ({exc}); HRMS and formula-based checks will be limited.")

        if not compound.hrms_found.strip():
            warnings.append(f"{label}: HRMS found value is missing; HRMS line/check will be skipped.")

        if not compound.color.strip() and not compound.state.strip():
            warnings.append(f"{label}: color/state is missing; appearance line will be incomplete.")

        if _looks_solid(compound.state) or _looks_solid(compound.color):
            if not compound.melting_point.strip():
                warnings.append(f"{label}: state looks solid, but melting point is missing.")

        if not compound.h1_nmr.strip() and not compound.h1_spectrum_path.strip():
            warnings.append(f"{label}: 1H NMR text/spectrum is missing.")
        warnings.extend(_spectrum_path_warnings(label, "1H", compound.h1_spectrum_path, resolved_base_dir))
        if not compound.c13_nmr.strip() and not compound.c13_spectrum_path.strip():
            warnings.append(f"{label}: 13C NMR text/spectrum is missing.")
        warnings.extend(_spectrum_path_warnings(label, "13C", compound.c13_spectrum_path, resolved_base_dir))

    if errors:
        raise ValueError("Input table has blocking errors:\n" + "\n".join(f"- {item}" for item in errors))
    return warnings


def _looks_solid(value: str) -> bool:
    normalized = value.strip().lower().replace("ё", "е")
    return any(marker.replace("ё", "е") in normalized for marker in SOLID_STATE_MARKERS)


def _spectrum_path_warnings(label: str, nucleus: str, raw_path: str, base_dir: Path | None) -> list[str]:
    raw_path = raw_path.strip().strip('"')
    if not raw_path:
        return []
    path = _resolve_input_path(raw_path, base_dir)
    if not path.exists():
        return [f"{label}: {nucleus} spectrum path does not exist: {path}."]
    if path.is_dir() and not _contains_bruker_fid(path):
        return [f"{label}: {nucleus} spectrum folder does not contain a Bruker fid file: {path}."]
    return []


def _resolve_input_path(raw_path: str, base_dir: Path | None) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute() and base_dir:
        path = base_dir / path
    return path.resolve()


def _contains_bruker_fid(path: Path) -> bool:
    if (path / "fid").exists():
        return True
    return any(child.is_file() and child.name.lower() == "fid" for child in path.rglob("fid"))
