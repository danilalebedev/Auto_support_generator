from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from docx import Document

from ..structure_metadata import StructureMetadata, extract_structure_metadata_by_cell
from .compound import Compound
from .types import Issue, ReagentAmount


@dataclass(frozen=True)
class LoadingsWorkflowPaths:
    schema_docx: Path
    scope_docx: Path
    template_docx: Path | None = None


@dataclass(frozen=True)
class SchemaEntry:
    key: str
    label: str
    equivalents: float | None = None
    mw: float | None = None
    density_g_mL: float | None = None
    concentration_M: float | None = None


@dataclass(frozen=True)
class ScopeRow:
    product_number: str
    reagent_1_mass_mg: float | None
    product_mass_mg: float | None
    reagent_1: StructureMetadata
    reagent_2: StructureMetadata
    product: StructureMetadata
    reagent_1_cell: tuple[int, int, int] = (0, 0, 0)
    reagent_2_cell: tuple[int, int, int] = (0, 0, 0)
    product_cell: tuple[int, int, int] = (0, 0, 0)


def discover_loadings_workflow(base_dir: str | Path) -> LoadingsWorkflowPaths | None:
    base_dir = Path(base_dir)
    directories = [base_dir / "loadings", base_dir]
    for directory in directories:
        if not directory.exists():
            continue
        schema = _find_docx(directory, "Reaction_schema.docx")
        scope = _find_docx(directory, "Scope.docx")
        if schema and scope:
            return LoadingsWorkflowPaths(schema, scope)
    return None


def apply_loadings_workflow(
    compounds: list[Compound],
    base_dir: str | Path,
    paths: LoadingsWorkflowPaths | None = None,
    template_docx: str | Path | None = None,
    structure_names_by_cell: dict[tuple[int, int, int], str] | None = None,
) -> list[Issue]:
    paths = paths or discover_loadings_workflow(base_dir)
    if paths is None:
        return []

    issues: list[Issue] = []
    schema = read_reaction_schema(paths.schema_docx)
    template_path = Path(template_docx) if template_docx else paths.template_docx or _default_si_template_path()
    template = read_characterization_template(template_path)
    if structure_names_by_cell is None:
        structure_names_by_cell, name_issues = _structure_names_for_template(paths.scope_docx, template)
        issues.extend(name_issues)
    scope_rows = read_scope(paths.scope_docx, structure_names_by_cell=structure_names_by_cell)
    compounds_by_number = {compound.number.strip(): compound for compound in compounds if compound.number.strip()}

    for row in scope_rows:
        compound = compounds_by_number.get(row.product_number)
        if compound is None:
            issues.append(
                {
                    "code": "LOADINGS_COMPOUND_NOT_FOUND",
                    "severity": "warning",
                    "message": f"Scope row for {row.product_number} has no matching input compound.",
                    "compound_id": row.product_number,
                    "path": str(paths.scope_docx),
                }
            )
            continue
        row_issues = _apply_scope_row(compound, row, schema, template)
        issues.extend(row_issues)

    return issues


def read_reaction_schema(path: str | Path) -> dict[str, SchemaEntry]:
    document = Document(str(path))
    if not document.tables:
        return {}

    table = document.tables[0]
    headers = [_normalize_header(cell.text) for cell in table.rows[0].cells]
    name_col = _header_index(headers, "reagents", "reagent")
    equiv_col = _header_index(headers, "equiv", "equivalents")
    mw_col = _header_index(headers, "mwgmol", "mw")
    density_col = _header_index(headers, "densitygml", "density")
    concentration_col = _header_index(headers, "concentrationm", "concentration")

    entries: dict[str, SchemaEntry] = {}
    for row in table.rows[1:]:
        cells = row.cells
        label = _cell_text(cells, name_col)
        if not label:
            continue
        key = _schema_key(label)
        entries[key] = SchemaEntry(
            key=key,
            label=label,
            equivalents=_float_or_none(_cell_text(cells, equiv_col)),
            mw=_float_or_none(_cell_text(cells, mw_col)),
            density_g_mL=_float_or_none(_cell_text(cells, density_col)),
            concentration_M=_float_or_none(_cell_text(cells, concentration_col)),
        )
    return entries


def read_scope(
    path: str | Path,
    structure_names_by_cell: dict[tuple[int, int, int], str] | None = None,
) -> list[ScopeRow]:
    document = Document(str(path))
    if not document.tables:
        return []

    table = document.tables[0]
    headers = [_normalize_header(cell.text) for cell in table.rows[0].cells]
    reagent_1_col = _header_index(headers, "reagent1")
    reagent_1_mass_col = _header_index(headers, "massofreagent1mg", "reagent1massmg")
    reagent_2_col = _header_index(headers, "reagent2")
    product_col = _header_index(headers, "product")
    product_number_col = _header_index(headers, "productnumber", "number")
    product_mass_col = _header_index(headers, "massofproductmg", "productmassmg")
    metadata_by_cell = extract_structure_metadata_by_cell(path)

    rows: list[ScopeRow] = []
    for row_index, row in enumerate(table.rows[1:], start=2):
        cells = row.cells
        product_number = _cell_text(cells, product_number_col)
        if not product_number:
            continue
        rows.append(
            ScopeRow(
                product_number=product_number,
                reagent_1_mass_mg=_float_or_none(_cell_text(cells, reagent_1_mass_col)),
                product_mass_mg=_float_or_none(_cell_text(cells, product_mass_col)),
                reagent_1=_metadata_with_name(
                    metadata_by_cell.get((1, row_index, reagent_1_col + 1), StructureMetadata()),
                    structure_names_by_cell,
                    (1, row_index, reagent_1_col + 1),
                ),
                reagent_2=_metadata_with_name(
                    metadata_by_cell.get((1, row_index, reagent_2_col + 1), StructureMetadata()),
                    structure_names_by_cell,
                    (1, row_index, reagent_2_col + 1),
                ),
                product=_metadata_with_name(
                    metadata_by_cell.get((1, row_index, product_col + 1), StructureMetadata()),
                    structure_names_by_cell,
                    (1, row_index, product_col + 1),
                ),
                reagent_1_cell=(1, row_index, reagent_1_col + 1),
                reagent_2_cell=(1, row_index, reagent_2_col + 1),
                product_cell=(1, row_index, product_col + 1),
            )
        )
    return rows


def read_characterization_template(path: str | Path) -> str:
    document = Document(str(path))
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    loadings_paragraph = next((text for text in paragraphs if _paragraph_has_loadings_placeholders(text)), "")
    text = loadings_paragraph or "\n".join(paragraphs)
    return _repair_known_template_placeholders(text)


def _apply_scope_row(
    compound: Compound,
    row: ScopeRow,
    schema: dict[str, SchemaEntry],
    template: str,
) -> list[Issue]:
    issues: list[Issue] = []
    reagent_1_schema = schema.get("Reagent_1")
    reagent_2_schema = schema.get("Reagent_2")
    if reagent_1_schema is None or reagent_2_schema is None:
        return [
            {
                "code": "LOADINGS_SCHEMA_INCOMPLETE",
                "severity": "warning",
                "message": "Reaction_schema.docx must contain Reagent 1 and Reagent 2 rows.",
                "compound_id": compound.id or compound.number,
            }
        ]

    reagent_1_mw = _metadata_mw(row.reagent_1) or reagent_1_schema.mw
    reagent_2_mw = _metadata_mw(row.reagent_2) or reagent_2_schema.mw
    product_mw = _metadata_mw(row.product)
    target_mmol = _limiting_mmol(row.reagent_1_mass_mg, reagent_1_mw, reagent_1_schema.equivalents)
    if target_mmol is None:
        issues.append(_compound_issue(compound, "LOADINGS_LIMITING_MISSING", "Cannot calculate limiting reagent mmol."))
        return issues

    reagent_amounts: dict[str, dict[str, Any]] = {}
    reagent_amounts["Reagent_1"] = _amount_from_mass(
        schema_entry=reagent_1_schema,
        metadata=row.reagent_1,
        mass_mg=row.reagent_1_mass_mg,
        mw=reagent_1_mw,
        mmol=target_mmol * (reagent_1_schema.equivalents or 1.0),
    )
    reagent_amounts["Reagent_2"] = _amount_from_equivalents(reagent_2_schema, target_mmol, row.reagent_2, reagent_2_mw)

    for key, entry in schema.items():
        if key in {"Reagent_1", "Reagent_2"}:
            continue
        reagent_amounts[key] = _amount_from_equivalents(entry, target_mmol, StructureMetadata(), entry.mw)

    product_mmol = _safe_div(row.product_mass_mg, product_mw)
    percent_yield = product_mmol / target_mmol * 100 if product_mmol is not None and target_mmol else None
    rf_value, rf_system = _split_rf(compound.rf)

    values = _base_template_values(
        compound=compound,
        row=row,
        target_mmol=target_mmol,
        percent_yield=percent_yield,
        rf_value=rf_value,
        rf_system=rf_system,
    )
    values.update(_amount_template_values("Reagent_1", reagent_amounts["Reagent_1"]))
    values.update(_amount_template_values("Reagent_2", reagent_amounts["Reagent_2"]))
    for key, amount in reagent_amounts.items():
        values[_token_key(key)] = _display_schema_name(schema[key].label)
        values.update(_amount_template_values(key, amount))

    preparation = _render_template(template, values)
    compound.preparation = preparation.rstrip(".")
    compound.yield_text = _yield_text(row.product_mass_mg, percent_yield)
    if row.product.formula and not compound.formula:
        compound.formula = row.product.formula
    compound.reaction = {
        "scale_basis": "limiting_reagent",
        "target_mmol": round(target_mmol, 4),
        "limiting_reagent": "Reagent_1",
        "reagents": [_reaction_reagent(key, amount, schema.get(key)) for key, amount in reagent_amounts.items()],
        "template_values": values,
        "preparation_includes_summary": True,
        "hide_loadings_line": True,
        "source": "loadings_workflow",
    }
    return issues


def _base_template_values(
    compound: Compound,
    row: ScopeRow,
    target_mmol: float,
    percent_yield: float | None,
    rf_value: str,
    rf_system: str,
) -> dict[str, str]:
    return {
        _token_key("number_Product"): row.product_number,
        _token_key("number_Reagent_1"): _infer_precursor_number(row.product_number),
        _token_key("mg_yield_Product"): _format_mass(row.product_mass_mg),
        _token_key("percent_yield_Product"): _format_percent(percent_yield),
        _token_key("yield.Product.mg"): _format_mass(row.product_mass_mg),
        _token_key("yield.Product.percent"): _format_percent(percent_yield),
        _token_key("color"): _compound_appearance(compound),
        _token_key("appearance"): _compound_appearance(compound),
        _token_key("mp"): _strip_temperature_unit(compound.melting_point),
        _token_key("Rf"): rf_value,
        _token_key("system_Rf"): rf_system,
        _token_key("rf.value"): rf_value,
        _token_key("rf.system"): rf_system,
        _token_key("target_mmol"): _format_mmol(target_mmol),
    }


def _amount_template_values(name: str, amount: dict[str, Any]) -> dict[str, str]:
    keys = {
        _token_key(f"name_{name}"): str(amount.get("name") or ""),
        _token_key(f"mg_{name}"): _format_mass(amount.get("mass_mg")),
        _token_key(f"mol_{name}"): _format_mmol(amount.get("mmol")),
        _token_key(f"mmol_{name}"): _format_mmol(amount.get("mmol")),
        _token_key(f"uL_{name}"): _format_volume_ul(amount.get("volume_uL")),
        _token_key(f"\u03bcL_{name}"): _format_volume_ul(amount.get("volume_uL")),
        _token_key(f"ml_{name}"): _format_volume_ml(amount.get("volume_mL")),
    }
    if name == "Reagent_1":
        keys[_token_key("mg_Reagent 1")] = _format_mass(amount.get("mass_mg"))
    return keys


def _amount_from_mass(
    schema_entry: SchemaEntry,
    metadata: StructureMetadata,
    mass_mg: float | None,
    mw: float | None,
    mmol: float | None,
) -> dict[str, Any]:
    return _compact_amount(
        {
            "name": _metadata_display(metadata, schema_entry.label),
            "formula": metadata.formula,
            "mw": mw,
            "equivalents": schema_entry.equivalents,
            "mmol": mmol,
            "mass_mg": mass_mg,
            "volume_uL": _volume_from_mass(mass_mg, schema_entry.density_g_mL),
        }
    )


def _amount_from_equivalents(
    schema_entry: SchemaEntry,
    target_mmol: float,
    metadata: StructureMetadata,
    mw: float | None,
) -> dict[str, Any]:
    mmol = target_mmol * schema_entry.equivalents if schema_entry.equivalents is not None else None
    mass_mg = mmol * mw if mmol is not None and mw is not None else None
    volume_mL = _safe_div(target_mmol, schema_entry.concentration_M)
    return _compact_amount(
        {
            "name": _metadata_display(metadata, schema_entry.label),
            "formula": metadata.formula,
            "mw": mw,
            "equivalents": schema_entry.equivalents,
            "mmol": mmol,
            "mass_mg": mass_mg,
            "volume_uL": _volume_from_mass(mass_mg, schema_entry.density_g_mL),
            "volume_mL": volume_mL,
            "concentration_M": schema_entry.concentration_M,
            "density_g_mL": schema_entry.density_g_mL,
        }
    )


def _reaction_reagent(key: str, amount: dict[str, Any], schema_entry: SchemaEntry | None) -> ReagentAmount:
    role = "solvent" if schema_entry and schema_entry.concentration_M else "reagent"
    reagent: ReagentAmount = {
        "name": str(amount.get("name") or key),
        "role": role,  # type: ignore[typeddict-item]
    }
    for source_key in ("formula", "mw", "equivalents", "mmol", "mass_mg", "volume_uL", "density_g_mL", "concentration_M"):
        if amount.get(source_key) not in {None, ""}:
            reagent[source_key] = amount[source_key]  # type: ignore[literal-required]
    return reagent


def _render_template(template: str, values: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        raw_key = match.group(1)
        return values.get(_token_key(raw_key), match.group(0))

    text = re.sub(r"\{([^{}]+)\}", replace, template)
    text = re.sub(r"\s+([,.;])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _repair_known_template_placeholders(template: str) -> str:
    template = template.replace("{mg_ K2CO3},", "{mg_ K2CO3} mg,")
    template = template.replace("{\u03bcL_AcOH},", "{\u03bcL_AcOH} \u03bcL,")
    return template.replace("{K2CO3} ({\u03bcL_AcOH}", "{AcOH} ({\u03bcL_AcOH}").replace(
        "{K2CO3} ({uL_AcOH}", "{AcOH} ({uL_AcOH}"
    )


def _find_docx(directory: Path, expected_name: str) -> Path | None:
    expected = expected_name.lower()
    for path in directory.glob("*.docx"):
        if path.name.lower() == expected:
            return path
    return None


def _default_si_template_path() -> Path:
    return Path(__file__).resolve().parents[1] / "templates" / "SI_template.docx"


def _structure_names_for_template(scope_path: Path, template: str) -> tuple[dict[tuple[int, int, int], str], list[Issue]]:
    if not _template_requests_structure_names(template):
        return {}, []
    rows = read_scope(scope_path)
    cells = sorted({row.reagent_1_cell for row in rows} | {row.reagent_2_cell for row in rows} | {row.product_cell for row in rows})
    cells = [cell for cell in cells if cell != (0, 0, 0)]
    if not cells:
        return {}, []
    return _chemdraw_names_for_cells(scope_path, cells)


def _template_requests_structure_names(template: str) -> bool:
    for match in re.finditer(r"\{([^{}]+)\}", template):
        if _token_key(match.group(1)).startswith("name"):
            return True
    return False


def _paragraph_has_loadings_placeholders(text: str) -> bool:
    keys = {_token_key(match.group(1)) for match in re.finditer(r"\{([^{}]+)\}", text)}
    return any(
        key.startswith(prefix)
        for key in keys
        for prefix in ("name.reagent", "mg.reagent", "mmol.reagent", "number.product", "mg.yield.product")
    )


def _chemdraw_names_for_cells(scope_path: Path, cells: list[tuple[int, int, int]], timeout: int = 240) -> tuple[dict[tuple[int, int, int], str], list[Issue]]:
    cell_arg = ",".join(_format_cell_coordinate(cell) for cell in cells)
    if getattr(sys, "frozen", False):
        command = [sys.executable, "--si-generator-chemdraw-names", str(scope_path), "--cells", cell_arg]
    else:
        command = [sys.executable, "-m", "si_generator.chemdraw_names", str(scope_path), "--cells", cell_arg]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception as exc:
        return {}, [_loadings_name_issue(scope_path, str(exc))]
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "ChemDraw name generation failed.").strip()
        return {}, [_loadings_name_issue(scope_path, detail)]
    try:
        raw = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        return {}, [_loadings_name_issue(scope_path, f"Cannot parse ChemDraw name output: {exc}")]
    return {_parse_cell_coordinate(key): str(value).strip() for key, value in raw.items() if str(value).strip()}, []


def _loadings_name_issue(scope_path: Path, detail: str) -> Issue:
    return {
        "code": "LOADINGS_NAME_GENERATION_FAILED",
        "severity": "warning",
        "message": "Could not generate reagent/product names with ChemDraw. Formula fallback will be used.",
        "path": str(scope_path),
        "detail": detail,
    }


def _format_cell_coordinate(cell: tuple[int, int, int]) -> str:
    return f"{cell[0]}:{cell[1]}:{cell[2]}"


def _parse_cell_coordinate(value: str) -> tuple[int, int, int]:
    parts = [int(part.strip()) for part in value.split(":")]
    if len(parts) != 3:
        raise ValueError(f"Invalid cell coordinate: {value}")
    return parts[0], parts[1], parts[2]


def _metadata_with_name(
    metadata: StructureMetadata,
    structure_names_by_cell: dict[tuple[int, int, int], str] | None,
    cell: tuple[int, int, int],
) -> StructureMetadata:
    name = (structure_names_by_cell or {}).get(cell, "").strip()
    if not name:
        return metadata
    return replace(metadata, name=name)


def _cell_text(cells: Any, index: int) -> str:
    if index < 0 or index >= len(cells):
        return ""
    return cells[index].text.strip()


def _header_index(headers: list[str], *aliases: str) -> int:
    wanted = {_normalize_header(alias) for alias in aliases}
    for index, header in enumerate(headers):
        if header in wanted:
            return index
    return -1


def _normalize_header(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _schema_key(label: str) -> str:
    key = re.sub(r"\s+", "_", label.strip())
    return re.sub(r"[^A-Za-z0-9_]+", "", key)


def _token_key(text: str) -> str:
    normalized = text.replace("\u03bc", "u")
    return re.sub(r"[^a-z0-9]+", ".", normalized.lower()).strip(".")


def _display_schema_name(label: str) -> str:
    if label.startswith("Solvent_"):
        return label.split("_", 1)[1]
    return label


def _metadata_display(metadata: StructureMetadata, fallback: str) -> str:
    return metadata.name or metadata.formula or _display_schema_name(fallback)


def _metadata_mw(metadata: StructureMetadata) -> float | None:
    return metadata.molecular_weight or None


def _limiting_mmol(mass_mg: float | None, mw: float | None, equivalents: float | None) -> float | None:
    amount = _safe_div(mass_mg, mw)
    if amount is None:
        return None
    if equivalents:
        return amount / equivalents
    return amount


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in {None, 0}:
        return None
    return numerator / float(denominator)


def _volume_from_mass(mass_mg: float | None, density_g_mL: float | None) -> float | None:
    if mass_mg is None or not density_g_mL:
        return None
    return mass_mg / density_g_mL


def _float_or_none(value: str | float | int | None) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _split_rf(value: str) -> tuple[str, str]:
    text = value.strip()
    match = re.match(r"(.+?)\s*\((.+)\)\s*$", text)
    if not match:
        return text, ""
    return match.group(1).strip(), match.group(2).strip()


def _infer_precursor_number(product_number: str) -> str:
    match = re.match(r"(\d+)(.*)", product_number.strip())
    if not match:
        return product_number
    number = max(int(match.group(1)) - 1, 0)
    return f"{number}{match.group(2)}"


def _strip_temperature_unit(value: str) -> str:
    return re.sub(r"\s*(?:deg\.?\s*C|degrees?\s*C|C|°C)\s*$", "", value.strip(), flags=re.IGNORECASE)


def _normalize_sentence_piece(value: str) -> str:
    return value.strip().rstrip(".;")


def _compound_appearance(compound: Compound) -> str:
    return _normalize_sentence_piece(" ".join(part for part in [compound.color, compound.state] if part))


def _yield_text(mass_mg: float | None, percent_yield: float | None) -> str:
    mass = _format_mass(mass_mg)
    percent = _format_percent(percent_yield)
    if mass and percent:
        return f"{mass} mg ({percent})"
    return mass


def _format_mass(value: Any) -> str:
    parsed = _to_float(value)
    if parsed is None:
        return ""
    if abs(parsed) >= 10:
        return f"{parsed:.0f}"
    return _format_decimal(parsed, 1)


def _format_mmol(value: Any) -> str:
    parsed = _to_float(value)
    return _format_decimal(parsed, 2) if parsed is not None else ""


def _format_percent(value: Any) -> str:
    parsed = _to_float(value)
    return f"{parsed:.0f}%" if parsed is not None else ""


def _format_volume_ul(value: Any) -> str:
    parsed = _to_float(value)
    if parsed is None:
        return ""
    if abs(parsed) >= 10:
        return f"{parsed:.0f}"
    return _format_decimal(parsed, 1)


def _format_volume_ml(value: Any) -> str:
    parsed = _to_float(value)
    if parsed is None:
        return ""
    return _format_decimal(parsed, 1)


def _format_decimal(value: float | None, places: int) -> str:
    if value is None:
        return ""
    return f"{value:.{places}f}".rstrip("0").rstrip(".")


def _to_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compact_amount(amount: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in amount.items() if value not in {None, ""}}


def _compound_issue(compound: Compound, code: str, message: str) -> Issue:
    return {
        "code": code,
        "severity": "warning",
        "message": message,
        "compound_id": compound.id or compound.number,
    }
