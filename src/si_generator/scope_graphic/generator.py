from __future__ import annotations

import json
import re
from pathlib import Path

from ..domain.loadings_workflow import read_scope, read_reaction_schemas, _limiting_mmol
from ..method_selectors import select_for_compound
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
    schemas = read_reaction_schemas(schema_path)
    row_map = {r.product_number: r for r in rows}
    numbers = [c.number for c in compounds]
    if len(row_map) != len(rows) or set(row_map) != set(numbers):
        raise ValueError(f"Scope graphic: compound numbers differ. Compound table: {', '.join(numbers)}; "
                         f"Scope.docx: {', '.join(row_map)}. Use one row per product.")
    if not compounds:
        raise ValueError("Scope graphic requires at least one compound.")
    cdx = _extract_cdx_by_cell(Path(scope_path), set())
    schema_indexes = [(selector, index) for index, (selector, _schema) in enumerate(schemas)]
    grouped: list[tuple[int, list]] = []
    group_by_schema: dict[int, list] = {}
    for compound in compounds:
        schema_index = select_for_compound(schema_indexes, compound.number)
        if schema_index is None:
            raise ValueError(f"Scope reaction: no reaction schema includes compound {compound.number}.")
        group = group_by_schema.get(schema_index)
        if group is None:
            group = []
            group_by_schema[schema_index] = group
            grouped.append((schema_index, group))
        group.append(compound)

    series_models = []
    with chemdraw() as app:
        for schema_index, series_compounds in grouped:
            schema = schemas[schema_index][1]
            keys = sorted(
                (key for key in schema if re.fullmatch(r"Reagent_\d+", key)),
                key=lambda key: int(key.split("_")[-1]),
            )
            if not keys:
                raise ValueError("Reaction schema must contain at least one Reagent_i entry for the scope.")
            first = row_map[series_compounds[0].number]
            missing = [key for key in keys if first.reagent_cells.get(key) not in cdx]
            if missing:
                raise ValueError("Scope reaction: missing ChemDraw OLE structure for " + ", ".join(missing))

            named = [
                entry.label for key, entry in schema.items()
                if not re.fullmatch(r"Reagent_\d+", key) and not key.startswith("Solvent_")
            ]
            solvents = [
                entry.label.removeprefix("Solvent_")
                for key, entry in schema.items() if key.startswith("Solvent_")
            ]
            missing_solvents = [value for value in solvents if value.lower() not in conditions.lower()]
            series_conditions = ", ".join([*missing_solvents, conditions.strip()]).strip(", ")
            reagents = [", ".join(named)] if named else []
            if len(reagents[0] if reagents else "") > 55:
                reagents = named
            series = {
                "version": 1,
                "title": title,
                "conditions": series_conditions,
                "products": [],
                "reaction": {},
            }
            for compound in series_compounds:
                row = row_map[compound.number]
                if row.product_cell not in cdx:
                    raise ValueError(f"Scope: compound {compound.number} has no editable product structure.")
                if compound.formula and row.product.formula and compound.formula != row.product.formula:
                    raise ValueError(f"Scope: formula for {compound.number} differs from Compound table "
                                     f"({row.product.formula} versus {compound.formula}).")
                reactants = [
                    cdx_to_xml(app, cdx[row.reagent_cells[key]])
                    for key in keys if row.reagent_cells.get(key) in cdx
                ]
                if len(reactants) != len(keys):
                    raise ValueError(f"Scope reaction: missing Reagent_i structure for {compound.number}.")
                series["products"].append({
                    "id": compound.id,
                    "number": compound.number,
                    "yield": yield_label(compound, row, schema),
                    "reactants": reactants,
                    "cdxml": cdx_to_xml(app, cdx[row.product_cell]),
                })
            series["reaction"] = {
                "reactants": [cdx_to_xml(app, cdx[first.reagent_cells[key]]) for key in keys],
                "product": series["products"][0]["cdxml"],
                "number": series_compounds[0].number,
                "reagents": reagents,
            }
            series_models.append(series)

        model = series_models[0] if len(series_models) == 1 else {
            "version": 1,
            "title": title,
            "conditions": conditions,
            "products": [product for series in series_models for product in series["products"]],
            "reaction": series_models[0]["reaction"],
            "series": series_models,
        }
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
