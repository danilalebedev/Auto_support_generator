from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re

from pypdf import PdfReader

from .fields import cell_volume_from_parameters, field_value
from .model import CifRecord, cif_number


@dataclass(slots=True)
class Alert:
    source: str
    severity: str
    code: str
    message: str
    record: str | None = None
    alert_type: int | None = None


REQUIRED = {
    "organic": ("formula", "weight", "temperature", "space_group", "a", "b", "c", "volume", "z", "r_gt", "r_all", "gof"),
    "coordination": ("formula", "weight", "temperature", "space_group", "a", "b", "c", "volume", "z", "reflections", "r_gt", "r_all", "gof"),
}


def _numeric(record: CifRecord, tag: str) -> float | None:
    return cif_number(record.get(tag))


def preflight(record: CifRecord, mode: str) -> list[Alert]:
    result: list[Alert] = []
    for note in record.parser_notes:
        result.append(Alert("local-preflight", "warning", "CIF_IN_MEMORY_REPAIR", note, record.display_label))
    for key in REQUIRED[mode]:
        if field_value(record, key) is None:
            result.append(Alert("local-preflight", "warning", "MISSING_FIELD", f"Required report field is absent: {key}", record.display_label))

    reported_volume = cif_number(field_value(record, "volume"))
    calculated_volume = cell_volume_from_parameters(record)
    if reported_volume and calculated_volume:
        relative_error = abs(reported_volume - calculated_volume) / reported_volume
        if relative_error > 0.005:
            result.append(Alert("local-preflight", "warning", "CELL_VOLUME", f"Cell parameters imply V={calculated_volume:.3f} Å³, differing from the reported value by {relative_error:.1%}.", record.display_label))

    measured = _numeric(record, "_diffrn_reflns_number")
    independent = _numeric(record, "_reflns_number_total")
    observed = _numeric(record, "_reflns_number_gt")
    if measured and independent and measured < independent:
        result.append(Alert("local-preflight", "warning", "REFLECTION_COUNTS", "Measured reflections are fewer than independent reflections.", record.display_label))
    if independent and observed and independent < observed:
        result.append(Alert("local-preflight", "warning", "REFLECTION_COUNTS", "Independent reflections are fewer than observed reflections.", record.display_label))

    t_min = _numeric(record, "_exptl_absorpt_correction_T_min")
    t_max = _numeric(record, "_exptl_absorpt_correction_T_max")
    if t_min is not None and t_max is not None and (t_min > t_max or t_min < 0 or t_max > 1.2):
        result.append(Alert("local-preflight", "warning", "TRANSMISSION", "Absorption-correction transmission limits are inconsistent.", record.display_label))

    for tag in ("_refine_ls_R_factor_gt", "_refine_ls_R_factor_all", "_refine_ls_wR_factor_gt", "_refine_ls_wR_factor_ref"):
        value = _numeric(record, tag)
        if value is not None and not 0 <= value <= 1:
            result.append(Alert("local-preflight", "warning", "R_FACTOR_RANGE", f"{tag} is outside 0–1: {value}", record.display_label))

    r_gt = _numeric(record, "_refine_ls_R_factor_gt")
    r_all = _numeric(record, "_refine_ls_R_factor_all")
    if r_gt is not None and r_all is not None and r_gt > r_all + 1e-9:
        result.append(Alert("local-preflight", "warning", "R_FACTOR_ORDER", "R1 for observed data exceeds R1 for all data.", record.display_label))

    if not record.ccdc and record.get("_database_code_depnum_ccdc_archive", "_database_code_CSD") is None:
        result.append(Alert("local-preflight", "info", "NO_DEPOSITION_CODE", "No CCDC deposition number was supplied or found in the CIF.", record.display_label))

    result.append(Alert("local-preflight", "info", "CHECKCIF_REQUIRED", "Local preflight is not an IUCr/CCDC checkCIF validation. Supply the official checkCIF PDF for alert capture.", record.display_label))
    return result


CHECKCIF_PATTERN = re.compile(r"\b(?P<code>[A-Z]{3,}\d{3})_ALERT_(?P<type>[1-5])_(?P<level>[ABCG])\b\s*(?P<message>.*)")


def parse_checkcif_pdf(path: str | Path, record: str | None = None) -> list[Alert]:
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    alerts: list[Alert] = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        match = CHECKCIF_PATTERN.search(line)
        if match:
            alerts.append(Alert(
                "official-checkcif-pdf",
                match.group("level"),
                match.group("code"),
                match.group("message").strip(),
                record or Path(path).stem,
                int(match.group("type")),
            ))
    return alerts


def write_alerts(path: str | Path, alerts: list[Alert]) -> None:
    payload = {
        "schema": "cif-reporter-alerts-v1",
        "note": "A/B/C/G entries are transcribed from supplied official checkCIF PDFs; local-preflight entries are not official checkCIF alerts.",
        "alerts": [asdict(alert) for alert in alerts],
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
