from __future__ import annotations

from typing import Any

from .types import ReactionBlock, ReagentAmount


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
