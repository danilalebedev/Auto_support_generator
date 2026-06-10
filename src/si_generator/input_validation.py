from __future__ import annotations

from .models import Compound


def validate_compound_inputs(compounds: list[Compound], *, require_structure: bool = False) -> list[str]:
    """Validate input rows and return non-fatal warnings.

    Fatal problems raise ValueError. Optional chemistry fields are reported as
    warnings because users often add spectra, HRMS, mp, or Rf gradually.
    """
    if not compounds:
        raise ValueError("No compounds were found in the input table.")

    errors: list[str] = []
    warnings: list[str] = []
    seen_numbers: set[str] = set()

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

        if not compound.hrms_found.strip():
            warnings.append(f"{label}: HRMS found value is missing; HRMS line/check will be skipped.")

        if not compound.color.strip() and not compound.state.strip():
            warnings.append(f"{label}: color/state is missing; appearance line will be incomplete.")

        if compound.state.strip().lower() in {"solid", "powder", "crystal", "crystals", "твердое", "порошок"}:
            if not compound.melting_point.strip():
                warnings.append(f"{label}: state looks solid, but melting point is missing.")

        if not compound.h1_nmr.strip() and not compound.h1_spectrum_path.strip():
            warnings.append(f"{label}: 1H NMR text/spectrum is missing.")
        if not compound.c13_nmr.strip() and not compound.c13_spectrum_path.strip():
            warnings.append(f"{label}: 13C NMR text/spectrum is missing.")

    if errors:
        raise ValueError("Input table has blocking errors:\n" + "\n".join(f"- {item}" for item in errors))
    return warnings
