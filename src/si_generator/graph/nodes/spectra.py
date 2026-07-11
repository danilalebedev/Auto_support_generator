from __future__ import annotations

import shutil
from pathlib import Path

from ..compound_store import ordered_compounds
from ..state import GenerateSIState, Issue
from ...domain.spectra_config import build_spectrum_render_spec
from ...domain.types import SpectrumRenderSpec
from ...nmr_fill import fill_nmr_from_mnova
from ...output_layout import output_root_for, prepare_output_layout
from ...spectra_zip import assign_spectra_from_folder, prepare_spectra_source, spectra_source_compound_numbers


def prepare_spectra_source_node(state: GenerateSIState) -> dict:
    request = state["request"]
    compounds = ordered_compounds(state)
    dirs = prepare_output_layout(request.output_path, input_path=request.input_path, run_id=state.get("run_id", ""))
    output_path = dirs["support_docx"]
    artifacts = {
        **state.get("artifacts", {}),
        "output_root": str(dirs["output_root"]),
        "docx_dir": str(dirs["docx_dir"]),
        "input_dir": str(dirs["input_dir"]),
        "logs_dir": str(dirs["logs_dir"]),
        "reports_dir": str(dirs["reports_dir"]),
        "spectra_dir": str(dirs["spectra_dir"]),
    }
    input_artifacts = _copy_input_artifacts(request, dirs["input_dir"])
    artifacts.update(input_artifacts)
    spectra_source = request.resolved_spectra_source
    if not spectra_source:
        return {"output_path": output_path, "artifacts": artifacts}

    spectra_root = prepare_spectra_source(spectra_source, dirs["input_dir"] / "spectra")
    mismatch = _spectra_source_input_number_mismatch(compounds, spectra_root)
    if mismatch:
        issues = [*state.get("issues", []), mismatch]
        return {
            "output_path": output_path,
            "artifacts": {**artifacts, "spectra_root": str(spectra_root)},
            "issues": issues,
            "status": "fail",
        }

    assign_spectra_from_folder(compounds, spectra_root)
    return {
        "output_path": output_path,
        "compounds": state.get("compounds", {}),
        "artifacts": {**artifacts, "spectra_root": str(spectra_root)},
    }


def _spectra_source_input_number_mismatch(compounds, spectra_root: Path) -> Issue | None:
    input_numbers = {str(compound.number or "").strip() for compound in compounds if str(compound.number or "").strip()}
    spectra_numbers = spectra_source_compound_numbers(spectra_root)
    if input_numbers == spectra_numbers:
        return None
    missing_in_spectra = sorted(input_numbers - spectra_numbers)
    extra_in_spectra = sorted(spectra_numbers - input_numbers)
    message_parts = [
        "Spectra source and compound table contain different compound numbers.",
        f"Input compounds: {', '.join(sorted(input_numbers)) or '<none>'}.",
        f"Spectra folders: {', '.join(sorted(spectra_numbers)) or '<none>'}.",
    ]
    if missing_in_spectra:
        message_parts.append(f"Missing in spectra source: {', '.join(missing_in_spectra)}.")
    if extra_in_spectra:
        message_parts.append(f"Extra in spectra source: {', '.join(extra_in_spectra)}.")
    return {
        "code": "SPECTRA_SOURCE_INPUT_MISMATCH",
        "severity": "error",
        "message": " ".join(message_parts),
        "path": str(spectra_root),
    }

def _copy_input_artifacts(request, input_dir: Path) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for key, source in {
        "compound_table_copy": request.input_path,
        "template_docx_copy": request.template_docx,
        "references_copy": request.references_path,
        "loadings_schema_copy": request.loadings_schema_docx,
        "loadings_scope_copy": request.loadings_scope_docx,
        "mnova_graphics_profile_copy": request.mnova_graphics_profile,
        "mnova_graphics_profile_1h_copy": request.mnova_graphics_profile_1h,
        "mnova_graphics_profile_13c_copy": request.mnova_graphics_profile_13c,
    }.items():
        if not source:
            continue
        path = Path(source)
        if not path.exists() or not path.is_file():
            continue
        target = input_dir / path.name
        if path.resolve() == target.resolve():
            artifacts[key] = str(target)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        artifacts[key] = str(target)
    return artifacts


def plan_nmr_processing_node(state: GenerateSIState) -> dict:
    spectra_plan: dict[str, dict[str, SpectrumRenderSpec]] = {}
    spectra_config = state.get("spectra_config", {})

    for compound in ordered_compounds(state):
        compound_plan: dict[str, SpectrumRenderSpec] = {}
        if compound.h1_spectrum_path:
            compound_plan["1H"] = build_spectrum_render_spec("1H", spectra_config)
        if compound.c13_spectrum_path:
            compound_plan["13C"] = build_spectrum_render_spec("13C", spectra_config)
        if compound_plan:
            compound_id = compound.id or compound.number
            spectra_plan[compound_id] = compound_plan

    return {"spectra_plan": spectra_plan}


def route_nmr_processing(state: GenerateSIState) -> str:
    request = state["request"]
    spectra_config = state.get("spectra_config", {})
    extract_nmr = bool(spectra_config.get("extract_nmr", not request.no_extract_nmr))
    if not extract_nmr:
        return "skip_mnova"
    for compound in ordered_compounds(state):
        if compound.h1_spectrum_path or compound.c13_spectrum_path:
            return "run_mnova"
    return "skip_mnova"


def mnova_batch_node(state: GenerateSIState) -> dict:
    request = state["request"]
    compounds = ordered_compounds(state)
    spectra_config = state.get("spectra_config", {})
    mnova_exe = request.mnova_exe
    if not mnova_exe and spectra_config.get("mnova_executable_path"):
        mnova_exe = Path(str(spectra_config["mnova_executable_path"]))
    fill_nmr_from_mnova(
        compounds,
        request.input_base_dir,
        output_root_for(state.get("output_path", request.output_path)) / "logs" / "mnova_batch",
        output_root=output_root_for(state.get("output_path", request.output_path)),
        mnova_exe=mnova_exe,
        mnova_graphics_profile_path=spectra_config.get("mnova_graphics_profile_path"),
        mnova_graphics_profile_1h_path=spectra_config.get("mnova_graphics_profile_1h_path"),
        mnova_graphics_profile_13c_path=spectra_config.get("mnova_graphics_profile_13c_path"),
        render_specs_by_compound=state.get("spectra_plan"),
    )
    return {"compounds": state.get("compounds", {})}

