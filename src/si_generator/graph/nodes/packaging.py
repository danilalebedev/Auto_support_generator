from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..state import GenerateSIState


def write_manifest_node(state: GenerateSIState) -> dict:
    output_path = Path(state["output_path"])
    manifest_path = output_path.with_suffix(".manifest.json")
    artifacts = {**state.get("artifacts", {}), "manifest": str(manifest_path)}
    manifest = build_manifest({**state, "artifacts": artifacts})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"manifest": manifest, "artifacts": artifacts}


def build_manifest(state: GenerateSIState) -> dict:
    request = state["request"]
    compounds = state.get("compounds", {})
    order = list(state.get("order", []))
    output_path = Path(state["output_path"])

    manifest = {
        "run_id": state.get("run_id", ""),
        "input_hashes": _input_hashes(
            {
                "compound_table": request.input_path,
                "spectra_zip": request.spectra_zip,
                "template_docx": request.template_docx,
                "style_config": request.style_config_path,
                "references": request.references_path,
            }
        ),
        "output_paths": {
            "support_docx": str(output_path),
            "manifest": str(output_path.with_suffix(".manifest.json")),
        },
        "artifacts": {key: str(path) for key, path in state.get("artifacts", {}).items()},
        "order": order,
        "compounds": {},
    }

    for compound_id in order:
        compound = compounds.get(compound_id)
        if not compound:
            continue
        manifest["compounds"][compound_id] = {
            "id": compound_id,
            "number": compound.number,
            "source_row": compound.source_row,
            "structure_placeholder": f"STRUCTURE:{compound.number}",
            "docx_block_id": f"compound:{compound_id}",
            "references": list(compound.references),
            "artifacts": _compound_artifacts(compound),
        }

    return manifest


def _input_hashes(paths: dict[str, Path | None]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, path in paths.items():
        if path and Path(path).exists():
            hashes[key] = _sha256(path)
    return hashes


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _compound_artifacts(compound) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    if compound.h1_image_path:
        artifacts["h1_png"] = compound.h1_image_path
    if compound.c13_image_path:
        artifacts["c13_png"] = compound.c13_image_path
    if compound.mnova_path:
        artifacts["mnova"] = compound.mnova_path
    return artifacts
