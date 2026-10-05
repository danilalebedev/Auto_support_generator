from __future__ import annotations

import copy
import json
from pathlib import Path

from .document import insert_overview, remove_overview
from .generator import write_model


def read_model(manifest, root):
    relative = manifest.get("relative_paths", {}).get("scope_graphic")
    absolute = manifest.get("artifacts", {}).get("scope_graphic")
    path = Path(root) / relative if relative else Path(absolute) if absolute else None
    if path is None:
        return None
    if not path.is_file():
        raise FileNotFoundError(f"Scope source is missing: {path}. Keep the complete output folder.")
    return json.loads(path.read_text(encoding="utf-8"))


def update_model(model, manifest):
    model = copy.deepcopy(model)
    series_list = model.get("series", [model])
    kept_series = []
    for series in series_list:
        products = {p["id"]: p for p in series["products"]}
        updated = []
        for cid in manifest["order"]:
            if cid not in products:
                continue
            product = products[cid]
            product["number"] = manifest["compounds"][cid]["number"]
            updated.append(product)
        if updated:
            series["products"] = updated
            representative = updated[0]
            series["reaction"].update(number=representative["number"], product=representative["cdxml"],
                                       reactants=representative["reactants"])
            kept_series.append(series)
    return {"version": 1, "series": kept_series}


def save_overview(model, manifest, docx, output_root):
    if not model.get("series", [model]):
        from docx import Document
        document = Document(str(docx))
        remove_overview(document._element.body)
        document.save(str(docx))
        for key in ("artifacts", "relative_paths", "output_paths"):
            manifest.get(key, {}).pop("scope_graphic", None)
        return
    path = write_model(model, Path(output_root) / "scope")
    insert_overview(docx, path)
    for key in ("artifacts", "output_paths"):
        manifest.setdefault(key, {})["scope_graphic"] = str(path)
    manifest.setdefault("relative_paths", {})["scope_graphic"] = str(path.relative_to(output_root))


def refresh_patch(source_manifest, manifest, source_root, docx, output_root):
    model = read_model(source_manifest, source_root)
    if model is not None:
        save_overview(update_model(model, manifest), manifest, docx, output_root)


def refresh_add(old_manifest, new_manifest, merged, old_root, new_root, docx, output_root, id_map, method):
    old = read_model(old_manifest, old_root)
    new = read_model(new_manifest, new_root)
    if old is None and new is None:
        return
    if old is not None and new is None:
        raise ValueError("The existing SI has a scope overview, but the new compounds have no scope data.")
    old_series = old.get("series", [old]) if old else []
    new_series = new.get("series", [new]) if new else []
    for series in new_series:
        for product in series["products"]:
            product["id"] = id_map.get(product["id"], product["id"])
    if method == "same_series" and old_series and new_series:
        old_series[-1]["products"].extend(new_series[0]["products"])
        new_series = new_series[1:]
    model = update_model({"series": old_series + new_series}, merged)
    save_overview(model, merged, docx, output_root)
