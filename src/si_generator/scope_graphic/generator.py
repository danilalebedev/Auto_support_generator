from __future__ import annotations

import json
import re
from pathlib import Path

from ..domain.loadings_workflow import read_scope, read_reaction_schema, _limiting_mmol
from ..chemdraw_names import _extract_cdx_by_cell
from .layout import make_page
from .native import chemdraw, cdx_to_xml, render_png


def yield_label(compound, row, schema):
    matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*%", compound.yield_text or "")
    if len(matches) == 1:
        return matches[0].replace(",", ".") + "%"
    reagent = schema.get("Reagent_1")
    if reagent:
        scale = _limiting_mmol(row.reagent_1_mass_mg,
                              row.reagent_1.molecular_weight or reagent.mw,
                              reagent.equivalents)
        if scale and row.product.molecular_weight and row.product_mass_mg is not None:
            percent = row.product_mass_mg / row.product.molecular_weight / scale * 100
            return f"{percent:.0f}%"
    raise ValueError(f"Scope: yield is missing for compound {compound.number}. Fill a percentage yield "
                     "in Compound table or measured Reagent_1/product masses in Scope.docx.")


def generate(compounds, scope_path, schema_path, output_dir, conditions="", title="Reaction and compound scope"):
    rows = read_scope(scope_path, structure_names_by_cell={})
    schema = read_reaction_schema(schema_path)
    row_map = {r.product_number: r for r in rows}
    numbers = [c.number for c in compounds]
    if len(row_map) != len(rows) or set(row_map) != set(numbers):
        raise ValueError(f"Scope graphic: compound numbers differ. Compound table: {', '.join(numbers)}; "
                         f"Scope.docx: {', '.join(row_map)}. Use one row per product.")
    if not compounds:
        raise ValueError("Scope graphic requires at least one compound.")
    cdx = _extract_cdx_by_cell(Path(scope_path), set())
    first = row_map[numbers[0]]
    keys = sorted(first.reagent_cells, key=lambda k: int(k.split("_")[-1]))
    if not keys:
        raise ValueError("Scope.docx must contain at least one Reagent_i structure for the reaction.")
    missing = [k for k in keys if first.reagent_cells[k] not in cdx]
    if missing:
        raise ValueError("Scope reaction: missing ChemDraw OLE structure for " + ", ".join(missing))
    named = [entry.label for key, entry in schema.items()
             if not re.fullmatch(r"Reagent_\d+", key) and not key.startswith("Solvent_")]
    solvents = [entry.label.removeprefix("Solvent_") for key, entry in schema.items() if key.startswith("Solvent_")]
    missing_solvents = [s for s in solvents if s.lower() not in conditions.lower()]
    conditions = ", ".join([*missing_solvents, conditions.strip()]).strip(", ")
    reagents = [", ".join(named)] if named else []
    if len(reagents[0] if reagents else "") > 55:
        reagents = named
    model = {"version": 1, "title": title, "conditions": conditions, "products": [], "reaction": {}}
    with chemdraw() as app:
        for compound in compounds:
            row = row_map[compound.number]
            if row.product_cell not in cdx:
                raise ValueError(f"Scope: compound {compound.number} has no editable product structure.")
            # A scope with the same numbers but different products must not silently
            # introduce an inconsistent chemistry overview.
            if compound.formula and row.product.formula and compound.formula != row.product.formula:
                raise ValueError(f"Scope: formula for {compound.number} differs from Compound table "
                                 f"({row.product.formula} versus {compound.formula}).")
            model["products"].append({"id": compound.id, "number": compound.number,
                                      "yield": yield_label(compound, row, schema),
                                      "reactants": [cdx_to_xml(app, cdx[row.reagent_cells[k]]) for k in keys
                                                    if row.reagent_cells.get(k) in cdx],
                                      "cdxml": cdx_to_xml(app, cdx[row.product_cell])})
            if len(model["products"][-1]["reactants"]) != len(keys):
                raise ValueError(f"Scope reaction: missing Reagent_i structure for {compound.number}.")
        model["reaction"] = {"reactants": [cdx_to_xml(app, cdx[first.reagent_cells[k]]) for k in keys],
                             "product": model["products"][0]["cdxml"], "number": numbers[0], "reagents": reagents}
        return write_model(model, Path(output_dir), app)


def write_model(model, output_dir, app=None):
    if app is None:
        with chemdraw() as application:
            return write_model(model, output_dir, application)
    output_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    # Twelve products per page keeps the labels readable in a portrait SI.
    for series in model.get("series", [model]):
        for index in range(0, len(series["products"]), 12):
            products = series["products"][index:index + 12]
            xml, metrics = make_page(products, series["reaction"], series["conditions"], series["title"])
            stem = f"reaction_scope_{len(pages) + 1}"
            cdxml, png = output_dir / f"{stem}.cdxml", output_dir / f"{stem}.png"
            cdxml.write_text(xml, encoding="utf-8")
            render_png(app, cdxml, png)
            pages.append({"cdxml": cdxml.name, "png": png.name, **metrics})
    model["pages"] = pages
    model_path = output_dir / "scope_graphic.json"
    model_path.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
    return model_path
