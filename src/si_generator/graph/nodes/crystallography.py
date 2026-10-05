from __future__ import annotations

from pathlib import Path

from ..compound_store import ordered_compounds
from ..state import GenerateSIState
from ...output_layout import output_dirs


def process_crystallography_node(state: GenerateSIState) -> dict:
    request = state["request"]
    compounds = ordered_compounds(state)
    if not request.cif_source and not any(c.cif_files for c in compounds):
        return {}
    from ...crystallography.service import discover_source, process_compound

    dirs = output_dirs(Path(state.get("output_path", request.output_path)).resolve())
    root = dirs["reports_dir"] / "crystallography"
    issues = list(state.get("issues", []))
    try:
        if request.cif_source:
            found = discover_source(Path(request.cif_source), root / "source_archive", {c.number for c in compounds})
            for compound in compounds:
                # A dedicated source takes precedence over legacy spectra/cif folders.
                compound.cif_files = [str(p) for p in found.get(compound.number, [])]
        for index, compound in enumerate(compounds, 1):
            if not compound.cif_files:
                continue
            alerts = process_compound(compound, root / f"compound_{index}", request.crystallography_template_docx)
            for alert in alerts:
                issues.append({"code": "CIF_" + alert["code"], "severity": "info" if alert["severity"] == "info" else "warning",
                               "message": f"{compound.number}: {alert['message']}", "compound_id": compound.id,
                               "path": compound.crystallography_data_path})
    except Exception as exc:
        issues.append({"code": "CRYSTALLOGRAPHY_INPUT_FAILED", "severity": "error", "message": str(exc)})
        return {"issues": issues, "status": "fail"}
    return {"compounds": state.get("compounds", {}), "issues": issues,
            "artifacts": {**state.get("artifacts", {}), "crystallography_input_dir": str(root)}}
