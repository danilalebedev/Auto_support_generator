from __future__ import annotations

from typing import Any

from .types import ReactionBlock, ReagentAmount


REAGENT_FIELD_NAMES = {
    "name": "name",
    "role": "role",
    "formula": "formula",
    "mw": "mw",
    "equiv": "equivalents",
    "equivalents": "equivalents",
    "mmol": "mmol",
    "mass_mg": "mass_mg",
    "massmg": "mass_mg",
    "volume_ul": "volume_uL",
    "volumeuL": "volume_uL",
    "volumeul": "volume_uL",
    "density": "density_g_mL",
    "density_g_ml": "density_g_mL",
    "densitygml": "density_g_mL",
    "concentration": "concentration_M",
    "concentration_m": "concentration_M",
    "concentrationm": "concentration_M",
}


def reaction_from_fields(fields: dict[str, str]) -> ReactionBlock:
    reaction: ReactionBlock = {}
    target_mmol = _field_value(fields, "target_mmol", "targetmmol", "reaction_target_mmol", "reactiontargetmmol")
    if target_mmol:
        reaction["target_mmol"] = _float_or_text(target_mmol)

    reagents: list[ReagentAmount] = []
    for index in range(1, 21):
        reagent = _reagent_from_fields(fields, index)
        if reagent:
            reagents.append(reagent)
    if reagents:
        reaction["reagents"] = reagents

    return reaction


def calculate_reaction_loadings(reaction: ReactionBlock) -> ReactionBlock:
    """Calculate reagent mmol, mass and volume values from a structured reaction block."""
    result: ReactionBlock = dict(reaction)
    target_mmol = _float_or_none(result.get("target_mmol"))
    calculated_reagents: list[ReagentAmount] = []

    for reagent in result.get("reagents", []):
        amount: ReagentAmount = dict(reagent)
        mmol = _float_or_none(amount.get("mmol"))
        equivalents = _float_or_none(amount.get("equivalents"))
        if mmol is None and target_mmol is not None and equivalents is not None:
            mmol = target_mmol * equivalents
            amount["mmol"] = round(mmol, 4)

        mw = _float_or_none(amount.get("mw"))
        if amount.get("mass_mg") in {None, ""} and mmol is not None and mw is not None:
            amount["mass_mg"] = round(mmol * mw, 2)

        if amount.get("volume_uL") in {None, ""}:
            volume = _volume_uL(amount, mmol)
            if volume is not None:
                amount["volume_uL"] = round(volume, 2)

        calculated_reagents.append(amount)

    result["reagents"] = calculated_reagents
    result["formatted_text"] = format_reaction_loadings(result)
    return result


def format_reaction_loadings(reaction: ReactionBlock) -> str:
    parts = [format_reagent_amount(reagent) for reagent in reaction.get("reagents", [])]
    return "; ".join(part for part in parts if part)


def format_reagent_amount(reagent: ReagentAmount) -> str:
    name = str(reagent.get("name", "")).strip()
    if not name:
        return ""
    details: list[str] = []
    if reagent.get("mass_mg") not in {None, ""}:
        details.append(f"{float(reagent['mass_mg']):g} mg")
    if reagent.get("volume_uL") not in {None, ""}:
        details.append(f"{float(reagent['volume_uL']):g} uL")
    if reagent.get("mmol") not in {None, ""}:
        details.append(f"{float(reagent['mmol']):g} mmol")
    if reagent.get("equivalents") not in {None, ""}:
        details.append(f"{float(reagent['equivalents']):g} equiv")
    return f"{name} ({', '.join(details)})" if details else name


def _volume_uL(reagent: ReagentAmount, mmol: float | None) -> float | None:
    mass_mg = _float_or_none(reagent.get("mass_mg"))
    density = _float_or_none(reagent.get("density_g_mL"))
    if mass_mg is not None and density:
        return mass_mg / density

    concentration = _float_or_none(reagent.get("concentration_M"))
    if mmol is not None and concentration:
        return mmol / concentration * 1000
    return None


def _float_or_none(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_or_text(value: str) -> float | str:
    parsed = _float_or_none(value)
    return parsed if parsed is not None else value


def _reagent_from_fields(fields: dict[str, str], index: int) -> ReagentAmount:
    amount: ReagentAmount = {}
    for source_name, target_name in REAGENT_FIELD_NAMES.items():
        value = _field_value(
            fields,
            f"reagent_{index}_{source_name}",
            f"reagent{index}_{source_name}",
            f"reagent{index}{source_name}",
        )
        if not value:
            continue
        if target_name in {"name", "role", "formula"}:
            amount[target_name] = value
        else:
            amount[target_name] = _float_or_text(value)
    return amount if amount.get("name") else {}


def _field_value(fields: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = fields.get(key)
        if value not in {None, ""}:
            return str(value).strip()
    return ""
