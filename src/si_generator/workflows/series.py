from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import shutil

from ..graph.state import make_run_id
from ..output_layout import prepare_output_layout
from ..word_input import read_word_compounds


def series_requests(request):
    root = Path(request.series_folder)
    if not root.is_dir():
        raise ValueError(f"Series folder does not exist: {root}")
    folders = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not folders:
        raise ValueError("Series folder contains no series subfolders")
    result, seen = [], {}
    for folder in folders:
        table = folder / "Compound_table.docx"
        if not table.is_file():
            raise ValueError(f"{folder.name}: Compound_table.docx is required")
        for compound in read_word_compounds(table, extract_structure_metadata=False):
            key = compound.number.casefold()
            if key in seen:
                raise ValueError(f"Duplicate compound number '{compound.number}' in {table} and {seen[key]}")
            seen[key] = table
        def optional(name):
            path = folder / name
            return path if path.exists() else None
        schema, scope = optional("Reaction_schema.docx"), optional("Scope.docx")
        if bool(schema) != bool(scope):
            raise ValueError(f"{folder.name}: Reaction_schema.docx and Scope.docx must be supplied together")
        result.append(replace(request, series_folder=None, input_path=table, unified_input_docx=None,
                              resolved_compound_table_docx=None, template_docx=optional("SI_template.docx"),
                              spectra_source=optional("Spectra_source") or optional("Spectra_source.zip"), spectra_zip=None,
                              cif_source=optional("CIF_source") or optional("CIF_source.zip"),
                              crystallography_template_docx=optional("Crystallography_template.docx") or request.crystallography_template_docx,
                              loadings_schema_docx=schema, loadings_scope_docx=scope, generate_loadings=bool(schema and scope)))
    return result


def run_series(request):
    from .generate_si import run_generate_si
    from ..graph.nodes.add_compounds import _append_generated_docx_blocks, _merge_manifest, _new_compound_id_map
    from ..graph.nodes.packaging import build_run_summary

    requests = series_requests(request)
    stamp = make_run_id()
    dirs = prepare_output_layout(request.output_path, input_path=request.series_folder, run_id=stamp)
    output = dirs["support_docx"]
    manifest_path = output.with_suffix(".manifest.json")
    merged, all_issues, compound_store, configurations = None, [], {}, []
    for index, child in enumerate(requests, 1):
        child.output_path = dirs["output_root"] / "series" / f"series_{index}" / "support_information.docx"
        result = run_generate_si(child)
        if result.get("status") in {"fail", "failed"} or not result.get("artifacts", {}).get("support_docx"):
            all_issues.extend(result.get("issues", []))
            return {**result, "issues": all_issues, "status": "fail"}
        generated = result["manifest"]
        path = Path(result["artifacts"]["support_docx"])
        name = child.input_path.parent.name
        for entry in generated["compounds"].values():
            entry["series"] = name
        configurations.append({"name": name, "run_config": generated.get("run_config", {}), "source": str(child.input_path)})
        if merged is None:
            mapping = {key: key for key in generated["compounds"]}
            shutil.copy2(path, output)
            merged = deepcopy(generated)
            compound_store.update(result.get("compounds", {}))
        else:
            mapping = _new_compound_id_map(merged, generated)
            _append_generated_docx_blocks(output, path, output, old_manifest=merged, new_manifest=generated, id_map=mapping)
            merged, _ = _merge_manifest(merged, generated, id_map=mapping, run_id=stamp, source_manifest=manifest_path,
                                         output_docx=output, output_manifest=manifest_path, method_mode="new_method",
                                         method_config=generated.get("run_config", {}))
            for old, compound in result.get("compounds", {}).items():
                compound.id = mapping[old]
                compound_store[mapping[old]] = compound
        for issue in result.get("issues", []):
            copied = deepcopy(issue)
            if copied.get("compound_id") in mapping:
                copied["compound_id"] = mapping[copied["compound_id"]]
            all_issues.append(copied)
        # All source runs live inside this output; relative paths survive moving the folder.
        for entry in merged["compounds"].values():
            entry["relative_artifacts"] = {}
            for key, value in entry.get("artifacts", {}).items():
                try:
                    entry["relative_artifacts"][key] = str(Path(value).resolve().relative_to(dirs["output_root"].resolve()))
                except ValueError:
                    entry["relative_artifacts"][key] = value
    merged["series"] = configurations
    artifacts = {k: str(v) for k, v in dirs.items() if v.exists()}
    summary_path = output.with_suffix(".run_summary.json")
    artifacts.update(manifest=str(manifest_path), support_docx=str(output), run_summary=str(summary_path))
    merged.update(run_id=stamp, artifacts=artifacts, output_paths=artifacts.copy())
    merged["relative_paths"] = {k: str(Path(v).relative_to(dirs["output_root"])) for k, v in artifacts.items()}
    manifest_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = build_run_summary({"run_id": stamp, "compounds": compound_store, "order": merged["order"],
                                 "issues": all_issues}, merged)
    summary["series"] = configurations
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"request": request, "run_id": stamp, "output_path": output, "artifacts": artifacts, "manifest": merged,
            "compounds": compound_store, "order": merged["order"], "issues": all_issues, "status": summary["status"]}
