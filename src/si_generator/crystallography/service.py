from __future__ import annotations

from dataclasses import asdict
import json
import re
from pathlib import Path
import shutil
import zipfile

from .alerts import parse_checkcif_pdf, preflight
from .fields import ORGANIC_FIELDS, field_value
from .model import read_cif


def discover_source(source: Path, staging: Path, numbers: set[str]) -> dict[str, list[Path]]:
    """CIF folders form a subset of the input table, never a second compound list."""
    if source.is_file() and source.suffix.lower() == ".zip":
        from ..spectra_zip import _safe_extract
        staging.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(source) as archive:
            _safe_extract(archive, staging)
        source = staging
    if not source.is_dir():
        raise ValueError(f"CIF source is not a folder or ZIP: {source}")
    files = sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() == ".cif")
    if not files:
        raise ValueError(f"No CIF files found in {source}")
    # Permit one archive wrapper (e.g. CIF_source/), but never guess compound numbers.
    root = source
    while not any(p.parent == root for p in files):
        children = {p.relative_to(root).parts[0] for p in files}
        if len(children) != 1 or next(iter(children)) in numbers:
            break
        child = root / next(iter(children))
        if any(p.parent == child for p in files):
            break
        root = child
    found: dict[str, list[Path]] = {}
    for path in files:
        parts = path.relative_to(root).parts
        if len(parts) < 2 or parts[0] not in numbers:
            raise ValueError(f"CIF source / Compound table mismatch: '{parts[0]}' in {path}; "
                             f"expected a numbered folder from: {', '.join(sorted(numbers))}")
        found.setdefault(parts[0], []).append(path)
    return found


def _metadata(source: Path, block: str) -> dict:
    path = source.with_suffix(".json")
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"Metadata must be a JSON object: {path}")
    blocks = data.pop("blocks", {})
    if not isinstance(blocks, dict) or not isinstance(blocks.get(block, {}), dict):
        raise ValueError(f"Invalid per-block metadata: {path}")
    data.update(blocks.get(block, {}))
    allowed = {"growth", "refinement", "ccdc", "image", "caption", "include_geometry", "notes"}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"Unknown metadata fields in {path}: {', '.join(sorted(unknown))}")
    for key, value in data.items():
        if key == "include_geometry":
            if not isinstance(value, bool):
                raise ValueError(f"{path}: include_geometry must be true or false")
        elif not isinstance(value, str):
            raise ValueError(f"{path}: {key} must be text")
    return data


def _description(record, metadata: dict) -> list[str]:
    lines = []
    growth = metadata.get("growth") or record.get("_exptl_crystal_preparation")
    if growth:
        lines.append(growth)
    instrument, radiation, temperature = (field_value(record, k) for k in ("instrument", "radiation", "temperature"))
    acquisition = []
    if instrument:
        acquisition.append(f"using {instrument}")
    if radiation:
        acquisition.append(f"with {radiation}")
    if temperature:
        acquisition.append(f"at {temperature} K")
    if acquisition:
        lines.append("Single-crystal X-ray diffraction data were collected " + " ".join(acquisition) + ".")
    for tag, prefix in (("_computing_structure_solution", "Structure solution"),
                        ("_computing_structure_refinement", "Structure refinement"),
                        ("_refine_ls_hydrogen_treatment", "Hydrogen-atom treatment")):
        if record.get(tag):
            lines.append(f"{prefix}: {record.get(tag)}.")
    refinement = metadata.get("refinement") or record.get("_refine_special_details")
    if refinement:
        lines.append(refinement)
    if metadata.get("notes"):
        lines.append(metadata["notes"])
    return lines


def _geometry(record) -> list[dict]:
    result = []
    for kind, tags in (("Bond", ("_geom_bond_atom_site_label_1", "_geom_bond_atom_site_label_2", "_geom_bond_distance")),
                       ("Angle", ("_geom_angle_atom_site_label_1", "_geom_angle_atom_site_label_2", "_geom_angle_atom_site_label_3", "_geom_angle"))):
        for row in record.rows_with(tags[-1]):
            result.append({"kind": kind, "atoms": " - ".join(row.get(t, "?") for t in tags[:-1]),
                           "value": row.get(tags[-1], "?"),
                           "symmetry": "; ".join(f"{k}: {v}" for k, v in row.items() if "site_symmetry" in k and v not in {".", "?"})})
    return result


def _table_rows(record) -> list[dict]:
    rows = []
    for field in ORGANIC_FIELDS:
        label = field.en
        if field.key == "r_gt":
            threshold = record.get("_reflns_threshold_expression")
            if threshold:
                threshold = threshold.replace(r"\s", "\u03c3")
            label = f"Final R indices [{threshold}]" if threshold else "Final R indices (observed data)"
        rows.append({"key": field.key, "label": label, "value": field_value(record, field.key)})
    return rows


def process_compound(compound, target: Path, template: Path | None = None) -> list[dict]:
    from .preview import generate_preview
    from .render import write_report

    if template is None:
        from ..runtime_paths import bundled_resource_path
        template = bundled_resource_path(Path("si_generator/templates/Crystallography_template.docx"), package_file=__file__)
        if not template.is_file():
            template = Path(__file__).resolve().parents[1] / "templates" / "Crystallography_template.docx"
        if not template.is_file():
            raise FileNotFoundError("Bundled Crystallography_template.docx is missing")

    target.mkdir(parents=True, exist_ok=True)
    records, alerts, staged = [], [], []
    for file_index, filename in enumerate(compound.cif_files, 1):
        source = Path(filename).resolve()
        dest = target / f"source_{file_index}"
        dest.mkdir(exist_ok=True)
        cif_copy = dest / source.name
        shutil.copy2(source, cif_copy)
        staged.append(str(cif_copy))
        metadata_file = source.with_suffix(".json")
        if metadata_file.exists():
            shutil.copy2(metadata_file, dest / metadata_file.name)
        structures = [r for r in read_cif(source) if r.is_structure]
        if not structures:
            raise ValueError(f"No structure data blocks in {source}")
        for block_index, record in enumerate(structures, 1):
            meta = _metadata(source, record.block_name)
            record.ccdc = meta.get("ccdc") or record.get("_database_code_depnum_ccdc_archive", "_database_code_CSD")
            record.label = compound.number
            local = [asdict(a) for a in preflight(record, "organic")]
            image_path = target / f"structure_{file_index}_{block_index}.png"
            external = (source.parent / meta["image"]).resolve() if meta.get("image") else None
            if external:
                if not external.is_file() or external.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                    raise ValueError(f"Invalid crystallographic image: {external}")
                if not meta.get("caption"):
                    raise ValueError(f"Supply an accurate caption for the external image in {metadata_file}")
                image_path = image_path.with_suffix(external.suffix.lower())
                shutil.copy2(external, image_path)
                caption = meta["caption"]
            else:
                generate_preview(record, image_path)
                caption = ("Coordinate-derived ball-and-stick view of the asymmetric unit; hydrogen atoms omitted. "
                           "Not a thermal-ellipsoid plot; review inferred connectivity and supply an ORTEP plot for submission.")
                local.append({"source": "local-preflight", "severity": "warning", "code": "ELLIPSOID_PLOT_REQUIRED", "message": caption})
            if not (meta.get("growth") or record.get("_exptl_crystal_preparation")):
                local.append({"source": "local-preflight", "severity": "warning", "code": "CRYSTAL_GROWTH_MISSING",
                              "message": "Describe crystal growth in the CIF sidecar JSON before submission."})
            pdf = source.with_suffix(".checkcif.pdf")
            if pdf.exists():
                shutil.copy2(pdf, dest / pdf.name)
                local.extend(asdict(a) for a in parse_checkcif_pdf(pdf, record.block_name))
            def number_template(text):
                # Bare numeric labels are indistinguishable from measurement values.
                if compound.number.isdigit():
                    return text
                return re.sub(r"(?<![A-Za-z0-9])" + re.escape(compound.number) + r"(?![A-Za-z0-9])", "{Product.number}", text)
            records.append({"block": record.block_name, "source": str(cif_copy.relative_to(target)), "ccdc": record.ccdc or "",
                            "image": image_path.name, "caption": number_template(caption),
                            "description": [number_template(t) for t in _description(record, meta)],
                            "rows": _table_rows(record),
                            "geometry": _geometry(record) if meta.get("include_geometry", False) else [], "alerts": local})
            alerts.extend(local)
    template_copy = None
    if template:
        template_copy = target / "Crystallography_template.docx"
        shutil.copy2(template, template_copy)
    data = {"schema": "auto-si-crystallography-v1", "template": template_copy.name if template_copy else "", "records": records}
    data_path = target / "crystallography.json"
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    compound.cif_files = staged
    compound.cif_folder = str(target)
    compound.crystallography_data_path = str(data_path)
    compound.crystallography_report_path = str(target / "crystallography.docx")
    write_report(compound, Path(compound.crystallography_report_path))
    return alerts
