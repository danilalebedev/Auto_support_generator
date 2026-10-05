from __future__ import annotations

import argparse
import html
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from si_generator.procedure_import import parse_procedure  # noqa: E402


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    cases.extend(_explicit_loading_cases())
    cases.extend(_equivalents_only_cases())
    cases.extend(_catalyst_cases())
    cases.extend(_stock_solution_cases())
    cases.extend(_liquid_reagent_cases())
    cases.extend(_unit_conversion_cases())
    cases.extend(_multiple_variable_cases())
    cases.extend(_workup_cases())
    cases.extend(_prefix_loading_cases())
    cases.extend(_known_limitation_cases())
    if len(cases) != 100:
        raise AssertionError(f"Expected 100 validation cases, got {len(cases)}")
    return cases


def evaluate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated: list[dict[str, Any]] = []
    for case in cases:
        parsed = parse_procedure(case["input_method"], variable_names=case.get("variable_names", ()))
        checks = _evaluate_expected(parsed, case["expected"])
        support_level = case.get("support_level", "supported")
        if support_level == "known_limitation":
            automatic_status = "manual_review_expected"
        else:
            automatic_status = "pass" if all(check["passed"] for check in checks) else "fail"
        evaluated.append(
            {
                **case,
                "actual": {
                    "reference_chemical": parsed["reference_chemical"],
                    "reference_amount_mmol": parsed["reference_amount_mmol"],
                    "reaction_schema": _compact_schema(parsed),
                    "template_text": parsed["template_text"],
                    "ignored_workup_entities": parsed["ignored_workup_entities"],
                    "unresolved": parsed["unresolved"],
                },
                "automatic_checks": checks,
                "automatic_status": automatic_status,
            }
        )

    status_counts = Counter(case["automatic_status"] for case in evaluated)
    supported = [case for case in evaluated if case["support_level"] == "supported"]
    supported_passes = sum(case["automatic_status"] == "pass" for case in supported)
    return {
        "schema_version": "1.0",
        "description": (
            "Synthetic validation pack for the deterministic procedure importer. "
            "Cases are designed to be readable and manually reviewable; they are not extracted from publications."
        ),
        "case_count": len(evaluated),
        "supported_case_count": len(supported),
        "known_limitation_count": len(evaluated) - len(supported),
        "supported_pass_count": supported_passes,
        "supported_pass_rate": supported_passes / len(supported) if supported else 0.0,
        "automatic_status_counts": dict(sorted(status_counts.items())),
        "cases": evaluated,
    }


def write_validation_pack(result: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "procedure_import_100_cases.json"
    html_path = output_dir / "procedure_import_100_cases.html"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(_render_html(result), encoding="utf-8")
    return json_path, html_path


def _case(
    case_id: str,
    category: str,
    title: str,
    input_method: str,
    variable_names: list[str],
    expected: dict[str, Any],
    *,
    support_level: str = "supported",
    rationale: str = "",
) -> dict[str, Any]:
    return {
        "id": case_id,
        "category": category,
        "title": title,
        "input_method": input_method,
        "variable_names": variable_names,
        "support_level": support_level,
        "rationale": rationale,
        "expected": expected,
    }


def _expected(
    reference: str | None,
    aliases: dict[str, dict[str, Any]],
    *,
    template_contains: list[str] | None = None,
    template_not_contains: list[str] | None = None,
    ignored_workup: list[str] | None = None,
    unresolved_min: int = 0,
) -> dict[str, Any]:
    return {
        "reference_chemical": reference,
        "aliases": aliases,
        "template_contains": template_contains or [],
        "template_not_contains": template_not_contains or [],
        "ignored_workup_entities": ignored_workup or [],
        "unresolved_min": unresolved_min,
    }


def _explicit_loading_cases() -> list[dict[str, Any]]:
    substrates = [
        "aryl bromide 1a",
        "benzyl alcohol 2b",
        "alkene 3c",
        "ketone 4d",
        "amine 5e",
        "boronate 6f",
        "phenol 7g",
        "aldehyde 8h",
        "epoxide 9i",
        "amide 10j",
    ]
    reagents = ["NBS", "K2CO3", "NaBH4", "DIPEA", "Cs2CO3", "Selectfluor", "DCC", "PCC", "NaN3", "LiAlH4"]
    solvents = ["CHCl3", "MeCN", "THF", "DCM", "DMF", "toluene", "MeOH", "EtOH", "dioxane", "DMSO"]
    cases: list[dict[str, Any]] = []
    for index, (substrate, reagent, solvent) in enumerate(zip(substrates, reagents, solvents), start=1):
        reference_mmol = round(0.4 + index * 0.11, 3)
        reference_mass = round(reference_mmol * (150 + index * 7), 1)
        equivalents = round(1.0 + (index % 4) * 0.25, 2)
        reagent_mmol = round(reference_mmol * equivalents, 4)
        reagent_mass = round(reagent_mmol * (90 + index * 8), 1)
        solvent_volume = round(reference_mmol / (0.05 + index * 0.01), 2)
        input_method = (
            f"To a solution of {substrate} ({reference_mass} mg, {reference_mmol} mmol, 1.0 equiv) "
            f"in {solvent} ({solvent_volume} mL) was added {reagent} "
            f"({reagent_mass} mg, {reagent_mmol} mmol, {equivalents} equiv). "
            "The mixture was stirred at room temperature for 3 h."
        )
        aliases = {
            "Reagent_1": {"name": substrate, "variable": True, "equivalents": 1.0},
            reagent.replace("-", "_"): {"name": reagent, "equivalents": equivalents},
            f"Solvent_{solvent.replace('-', '_')}": {
                "name": solvent,
                "role": "solvent",
                "concentration_m": reference_mmol / solvent_volume,
            },
        }
        cases.append(
            _case(
                f"E{index:03d}",
                "explicit_loadings",
                "Explicit mass, mmol, equivalents and solvent volume",
                input_method,
                [substrate],
                _expected(
                    substrate,
                    aliases,
                    template_contains=["{Reagent_1.name}", f"{{{reagent.replace('-', '_')}.mg}}", f"{{Solvent_{solvent.replace('-', '_')}.ml}}"],
                ),
            )
        )
    return cases


def _equivalents_only_cases() -> list[dict[str, Any]]:
    substrates = [f"scope substrate {number}" for number in range(11, 21)]
    reagents = ["K2CO3", "Cs2CO3", "DBU", "DABCO", "NaOtBu", "KOtBu", "Et3N", "DIPEA", "NaH", "LiHMDS"]
    solvents = ["MeCN", "DMF", "THF", "DCM", "toluene", "dioxane", "DMSO", "MeOH", "EtOH", "CHCl3"]
    cases: list[dict[str, Any]] = []
    for offset, (substrate, reagent, solvent) in enumerate(zip(substrates, reagents, solvents), start=1):
        case_number = 10 + offset
        equivalents = round(1.25 + offset * 0.25, 2)
        concentration = round(0.04 + offset * 0.02, 2)
        input_method = (
            f"{substrate} (1.0 equiv) and {reagent} ({equivalents} equiv) were stirred in "
            f"{solvent} ({concentration} M) at 50 °C for 6 h."
        )
        reagent_alias = reagent.replace("-", "_")
        solvent_alias = f"Solvent_{solvent.replace('-', '_')}"
        cases.append(
            _case(
                f"E{case_number:03d}",
                "equivalents_only",
                "Equivalents without an absolute scale",
                input_method,
                [substrate],
                _expected(
                    substrate,
                    {
                        "Reagent_1": {"name": substrate, "equivalents": 1.0, "variable": True},
                        reagent_alias: {"name": reagent, "equivalents": equivalents},
                        solvent_alias: {"name": solvent, "role": "solvent", "concentration_m": concentration},
                    },
                    template_contains=["{Reagent_1.eq}", f"{{{reagent_alias}.eq}}", f"{concentration} M"],
                    unresolved_min=1,
                ),
                rationale="MW for the fixed reagent must be supplied by inventory or confirmed by the user.",
            )
        )
    return cases


def _catalyst_cases() -> list[dict[str, Any]]:
    catalysts = [
        "DBP",
        "AIBN",
        "TEMPO",
        "CuI",
        "nickel chloride",
        "palladium acetate",
        "photocatalyst PC-1",
        "copper bromide",
        "iron chloride",
        "ruthenium catalyst",
    ]
    solvents = ["CHCl3", "toluene", "MeCN", "DMF", "THF", "dioxane", "DMSO", "DCM", "EtOH", "MeOH"]
    cases: list[dict[str, Any]] = []
    for offset, (catalyst, solvent) in enumerate(zip(catalysts, solvents), start=1):
        case_number = 20 + offset
        substrate = f"catalysis substrate {case_number}"
        reference_mmol = round(0.45 + offset * 0.05, 3)
        reference_mass = round(reference_mmol * (180 + offset * 3), 1)
        mol_percent = 2 + offset
        catalyst_mmol = round(reference_mmol * mol_percent / 100, 5)
        catalyst_mass = round(catalyst_mmol * (150 + offset * 5), 2)
        solvent_volume = round(reference_mmol / 0.1, 2)
        catalyst_alias = _identifier(catalyst)
        solvent_alias = f"Solvent_{_identifier(solvent)}"
        input_method = (
            f"{substrate} ({reference_mass} mg, {reference_mmol} mmol, 1.0 equiv), "
            f"{catalyst} ({catalyst_mass} mg, {catalyst_mmol} mmol, {mol_percent} mol%) and "
            f"{solvent} ({solvent_volume} mL) were irradiated for 12 h."
        )
        cases.append(
            _case(
                f"E{case_number:03d}",
                "catalyst_mol_percent",
                "Catalyst loading in mol percent",
                input_method,
                [substrate],
                _expected(
                    substrate,
                    {
                        "Reagent_1": {"name": substrate, "equivalents": 1.0, "variable": True},
                        catalyst_alias: {"name": catalyst, "equivalents": mol_percent / 100},
                        solvent_alias: {"name": solvent, "role": "solvent", "concentration_m": 0.1},
                    },
                    template_contains=[f"{{{catalyst_alias}.mg}}", f"{mol_percent} mol%"],
                    template_not_contains=[f"{{{catalyst_alias}.eq}} mol%"],
                ),
            )
        )
    return cases


def _stock_solution_cases() -> list[dict[str, Any]]:
    stocks = [
        "n-BuLi",
        "LDA",
        "LiHMDS",
        "NaHMDS",
        "KHMDS",
        "DIBAL-H",
        "BH3-THF",
        "ethylmagnesium bromide",
        "methylmagnesium bromide",
        "TBAF",
    ]
    reaction_solvents = ["THF", "THF", "THF", "toluene", "THF", "DCM", "THF", "ether", "THF", "THF"]
    cases: list[dict[str, Any]] = []
    for offset, (stock, solvent) in enumerate(zip(stocks, reaction_solvents), start=1):
        case_number = 30 + offset
        substrate = f"stock-solution substrate {case_number}"
        reference_mmol = round(0.6 + offset * 0.07, 3)
        reference_mass = round(reference_mmol * (170 + offset * 2), 1)
        stock_concentration = round(0.7 + offset * 0.15, 2)
        stock_volume = round(0.45 + offset * 0.08, 2)
        expected_equivalents = stock_concentration * stock_volume / reference_mmol
        solvent_volume = round(reference_mmol / 0.12, 2)
        stock_alias = _identifier(stock)
        solvent_alias = f"Solvent_{_identifier(solvent)}"
        input_method = (
            f"A solution of {substrate} ({reference_mass} mg, {reference_mmol} mmol) in "
            f"{solvent} ({solvent_volume} mL) was treated with {stock} "
            f"({stock_concentration} M, {stock_volume} mL) at -78 °C."
        )
        cases.append(
            _case(
                f"E{case_number:03d}",
                "stock_solution",
                "Reagent supplied as a stock solution",
                input_method,
                [substrate],
                _expected(
                    substrate,
                    {
                        "Reagent_1": {"name": substrate, "equivalents": 1.0, "variable": True},
                        stock_alias: {
                            "name": stock,
                            "equivalents": expected_equivalents,
                            "concentration_m": stock_concentration,
                        },
                        solvent_alias: {"name": solvent, "role": "solvent", "concentration_m": 0.12},
                    },
                    template_contains=[f"{{{stock_alias}.ml}} mL", f"{stock_concentration} M"],
                ),
            )
        )
    return cases


def _liquid_reagent_cases() -> list[dict[str, Any]]:
    liquids = ["AcOH", "Et3N", "DIPEA", "piperidine", "morpholine", "DBU", "TfOH", "TFA", "pyridine", "anisole"]
    solvents = ["MeCN", "DCM", "THF", "toluene", "DMF", "DMSO", "CHCl3", "dioxane", "EtOH", "MeOH"]
    cases: list[dict[str, Any]] = []
    for offset, (liquid, solvent) in enumerate(zip(liquids, solvents), start=1):
        case_number = 40 + offset
        substrate = f"liquid-reagent substrate {case_number}"
        reference_mmol = round(0.35 + offset * 0.045, 3)
        reference_mass = round(reference_mmol * (190 + offset), 1)
        equivalents = float(2 + offset % 5)
        liquid_mmol = round(reference_mmol * equivalents, 4)
        molecular_weight = 60 + offset * 9
        liquid_mass = round(liquid_mmol * molecular_weight, 2)
        density = 0.75 + offset * 0.035
        volume_ul = round(liquid_mass / density, 1)
        solvent_volume = round(reference_mmol / 0.15, 2)
        liquid_alias = _identifier(liquid)
        solvent_alias = f"Solvent_{_identifier(solvent)}"
        input_method = (
            f"{substrate} ({reference_mass} mg, {reference_mmol} mmol, 1.0 equiv) was combined with "
            f"{liquid} ({volume_ul} µL, {liquid_mass} mg, {liquid_mmol} mmol, {equivalents} equiv) "
            f"in {solvent} ({solvent_volume} mL)."
        )
        cases.append(
            _case(
                f"E{case_number:03d}",
                "liquid_reagent",
                "Liquid reagent with volume, mass and amount",
                input_method,
                [substrate],
                _expected(
                    substrate,
                    {
                        "Reagent_1": {"name": substrate, "equivalents": 1.0, "variable": True},
                        liquid_alias: {
                            "name": liquid,
                            "equivalents": equivalents,
                            "density_g_ml": liquid_mass / (volume_ul / 1000 * 1000),
                        },
                        solvent_alias: {"name": solvent, "role": "solvent", "concentration_m": 0.15},
                    },
                    template_contains=[f"{{{liquid_alias}.mcl}} µL", f"{{{liquid_alias}.mg}} mg"],
                ),
            )
        )
    return cases


def _unit_conversion_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    formats = [
        ("0.250 g", "1.20 mmol", 250.0, 1.2, "0.020 L", 20.0),
        ("250000 µg", "1200 µmol", 250.0, 1.2, "20000 µL", 20.0),
        ("0.00025 kg", "0.0012 mol", 250.0, 1.2, "20 mL", 20.0),
        ("0,250 g", "1,20 mmol", 250.0, 1.2, "0,020 L", 20.0),
        ("300 mg", "1500 µmol", 300.0, 1.5, "0.015 L", 15.0),
        ("0.180 g", "0.90 mmol", 180.0, 0.9, "9000 µL", 9.0),
        ("420000 µg", "0.002 mol", 420.0, 2.0, "25 mL", 25.0),
        ("0.00016 kg", "800 µmol", 160.0, 0.8, "0.008 L", 8.0),
        ("95 mg", "500 µmol", 95.0, 0.5, "5000 µL", 5.0),
        ("0.525 g", "0.0025 mol", 525.0, 2.5, "0.050 L", 50.0),
    ]
    solvents = ["THF", "MeCN", "DCM", "toluene", "DMF", "DMSO", "CHCl3", "dioxane", "EtOH", "MeOH"]
    for offset, (values, solvent) in enumerate(zip(formats, solvents), start=1):
        case_number = 50 + offset
        mass_text, amount_text, mass_mg, amount_mmol, volume_text, volume_ml = values
        substrate = f"unit-conversion substrate {case_number}"
        solvent_alias = f"Solvent_{_identifier(solvent)}"
        input_method = (
            f"{substrate} ({mass_text}, {amount_text}, 1 equiv) was dissolved in "
            f"{solvent} ({volume_text}) and stirred for 1 h."
        )
        cases.append(
            _case(
                f"E{case_number:03d}",
                "unit_conversion",
                "Normalization of mass, amount and volume units",
                input_method,
                [substrate],
                _expected(
                    substrate,
                    {
                        "Reagent_1": {
                            "name": substrate,
                            "equivalents": 1.0,
                            "mass_mg": mass_mg,
                            "amount_mmol": amount_mmol,
                            "variable": True,
                        },
                        solvent_alias: {
                            "name": solvent,
                            "role": "solvent",
                            "volume_ml": volume_ml,
                            "concentration_m": amount_mmol / volume_ml,
                        },
                    },
                    template_contains=["{Reagent_1.name}", solvent_alias],
                ),
            )
        )
    return cases


def _multiple_variable_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    solvents = ["MeCN", "DMF", "THF", "DMSO", "toluene", "dioxane", "DCM", "EtOH", "MeOH", "CHCl3"]
    for offset, solvent in enumerate(solvents, start=1):
        case_number = 60 + offset
        reagent_one = f"aryl halide {case_number}a"
        reagent_two = f"amine {case_number}b"
        reference_mmol = round(0.5 + offset * 0.05, 3)
        reference_mass = round(reference_mmol * (200 + offset * 4), 1)
        second_equivalents = round(1.1 + offset * 0.1, 2)
        second_mmol = round(reference_mmol * second_equivalents, 4)
        second_mass = round(second_mmol * (95 + offset * 2), 1)
        base_mmol = round(reference_mmol * 2.0, 4)
        base_mass = round(base_mmol * 138.21, 1)
        solvent_volume = round(reference_mmol / 0.2, 2)
        solvent_alias = f"Solvent_{_identifier(solvent)}"
        input_method = (
            f"{reagent_one} ({reference_mass} mg, {reference_mmol} mmol, 1.0 equiv), "
            f"{reagent_two} ({second_mass} mg, {second_mmol} mmol, {second_equivalents} equiv), "
            f"K2CO3 ({base_mass} mg, {base_mmol} mmol, 2.0 equiv) and {solvent} "
            f"({solvent_volume} mL) were heated at 80 °C."
        )
        cases.append(
            _case(
                f"E{case_number:03d}",
                "multiple_variable_reagents",
                "Two variable structures in Scope",
                input_method,
                [reagent_one, reagent_two],
                _expected(
                    reagent_one,
                    {
                        "Reagent_1": {"name": reagent_one, "equivalents": 1.0, "variable": True},
                        "Reagent_2": {"name": reagent_two, "equivalents": second_equivalents, "variable": True},
                        "K2CO3": {"name": "K2CO3", "equivalents": 2.0},
                        solvent_alias: {"name": solvent, "role": "solvent", "concentration_m": 0.2},
                    },
                    template_contains=["{Reagent_1.name}", "{Reagent_2.name}", "{K2CO3.mg}"],
                ),
            )
        )
    return cases


def _workup_cases() -> list[dict[str, Any]]:
    workups = [
        ("water", "EtOAc"),
        ("brine", "ether"),
        ("saturated NH4Cl", "EtOAc"),
        ("water", "DCM"),
        ("brine", "MTBE"),
        ("aqueous NaHCO3", "EtOAc"),
        ("water", "ether"),
        ("saturated NaCl", "DCM"),
        ("water", "hexane"),
        ("aqueous HCl", "EtOAc"),
    ]
    cases: list[dict[str, Any]] = []
    for offset, (quench, extraction) in enumerate(workups, start=1):
        case_number = 70 + offset
        substrate = f"workup substrate {case_number}"
        reference_mmol = round(0.4 + offset * 0.06, 3)
        reference_mass = round(reference_mmol * 210, 1)
        thf_volume = round(reference_mmol / 0.1, 2)
        input_method = (
            f"{substrate} ({reference_mass} mg, {reference_mmol} mmol) was stirred in THF "
            f"({thf_volume} mL) for 4 h. The reaction was quenched with {quench} (20 mL) "
            f"and extracted with {extraction} (30 mL)."
        )
        cases.append(
            _case(
                f"E{case_number:03d}",
                "workup_exclusion",
                "Workup liquids remain literal and are excluded from the reaction schema",
                input_method,
                [substrate],
                _expected(
                    substrate,
                    {
                        "Reagent_1": {"name": substrate, "equivalents": 1.0, "variable": True},
                        "Solvent_THF": {"name": "THF", "role": "solvent", "concentration_m": 0.1},
                    },
                    template_contains=[f"{quench} (20 mL)", f"{extraction} (30 mL)"],
                    template_not_contains=["Solvent_water", f"Solvent_{_identifier(extraction)}"],
                    ignored_workup=[quench, extraction],
                ),
            )
        )
    return cases


def _prefix_loading_cases() -> list[dict[str, Any]]:
    reagents = ["Et3N", "DIPEA", "K2CO3", "Cs2CO3", "NaBH4", "DABCO", "DBU", "NaN3", "NBS", "Selectfluor"]
    solvents = ["THF", "MeCN", "DMF", "DMSO", "DCM", "toluene", "dioxane", "EtOH", "MeOH", "CHCl3"]
    cases: list[dict[str, Any]] = []
    for offset, (reagent, solvent) in enumerate(zip(reagents, solvents), start=1):
        case_number = 80 + offset
        substrate = f"prefix substrate {case_number}"
        reference_mmol = round(0.3 + offset * 0.08, 3)
        equivalents = round(1.2 + offset * 0.2, 2)
        reagent_mmol = round(reference_mmol * equivalents, 4)
        solvent_volume = round(reference_mmol / 0.08, 2)
        reagent_alias = _identifier(reagent)
        solvent_alias = f"Solvent_{_identifier(solvent)}"
        input_method = (
            f"1.0 equiv ({reference_mmol} mmol) of {substrate} was mixed with "
            f"{equivalents} equiv ({reagent_mmol} mmol) of {reagent} in {solvent} "
            f"({solvent_volume} mL)."
        )
        cases.append(
            _case(
                f"E{case_number:03d}",
                "prefix_loading",
                "Loading appears before the chemical name",
                input_method,
                [substrate],
                _expected(
                    substrate,
                    {
                        "Reagent_1": {"name": substrate, "equivalents": 1.0, "variable": True},
                        reagent_alias: {"name": reagent, "equivalents": equivalents},
                        solvent_alias: {"name": solvent, "role": "solvent", "concentration_m": 0.08},
                    },
                    template_contains=["{Reagent_1.name}", f"{{{reagent_alias}.mmol}}", f"{{{solvent_alias}.ml}}"],
                    unresolved_min=1,
                ),
                rationale="The fixed reagent has no mass or inventory MW, so its MW remains unresolved.",
            )
        )
    return cases


def _known_limitation_cases() -> list[dict[str, Any]]:
    inputs = [
        ("Implicit quantities", "A mixture of substrate 91, base and catalyst was heated overnight."),
        ("Nested catalyst name", "substrate 92 (1.0 mmol) and Pd(PPh3)4 (5 mol%) were stirred in THF (10 mL)."),
        ("Amount range", "substrate 93 (0.5-0.7 mmol) was treated with NBS (1.0-1.2 equiv)."),
        ("Two-step one-pot", "substrate 94 (1 mmol) was reduced, then the alcohol was oxidized with PCC (2 equiv)."),
        ("Pronoun reference", "compound 95 (1 mmol) was dissolved in THF (5 mL). It was treated with base."),
        ("Table-like prose", "substrate 96 | 1.0 equiv | reagent X | 2.0 equiv | MeCN | 0.1 M"),
        ("OCR damage", "substrate 97 (l00 mg, O.5 mmol) and N8S (89 mg, 0.5 mmol) were mixed."),
        ("Concentration without owner", "substrate 98 (1 mmol) was reacted at 0.1 M with reagent X (2 equiv)."),
        ("Ambiguous solution", "substrate 99 (1 mmol) was added to a 1 M solution (2 mL) at -78 °C."),
        ("Multiple reference scales", "substrate 100a (1 mmol, 1 equiv) and substrate 100b (1 mmol, 0.5 equiv) were combined."),
    ]
    cases: list[dict[str, Any]] = []
    for offset, (title, input_method) in enumerate(inputs, start=1):
        case_number = 90 + offset
        expected_variable = f"substrate {case_number}" if case_number < 100 else "substrate 100a"
        cases.append(
            _case(
                f"E{case_number:03d}",
                "known_limitation",
                title,
                input_method,
                [expected_variable],
                _expected(None, {}, unresolved_min=0),
                support_level="known_limitation",
                rationale=(
                    "This case intentionally requires semantic interpretation, OCR repair, range handling, "
                    "or stage separation. The generated output is shown for manual review and is not counted as a pass."
                ),
            )
        )
    return cases


def _evaluate_expected(parsed: dict[str, Any], expected: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if expected.get("reference_chemical") is not None:
        checks.append(
            _check(
                "reference_chemical",
                parsed.get("reference_chemical") == expected["reference_chemical"],
                expected["reference_chemical"],
                parsed.get("reference_chemical"),
            )
        )

    by_alias = {chemical["alias"]: chemical for chemical in parsed["chemicals"] if chemical.get("alias")}
    for alias, expected_fields in expected.get("aliases", {}).items():
        actual = by_alias.get(alias)
        checks.append(_check(f"alias:{alias}", actual is not None, "present", "present" if actual else "missing"))
        if actual is None:
            continue
        for field, expected_value in expected_fields.items():
            actual_value = actual.get(field)
            passed = _values_equal(actual_value, expected_value)
            checks.append(_check(f"{alias}.{field}", passed, expected_value, actual_value))

    template = parsed["template_text"]
    for fragment in expected.get("template_contains", []):
        checks.append(_check(f"template contains {fragment}", fragment in template, fragment, template))
    for fragment in expected.get("template_not_contains", []):
        checks.append(_check(f"template excludes {fragment}", fragment not in template, f"not {fragment}", template))

    ignored_expected = expected.get("ignored_workup_entities", [])
    if ignored_expected:
        actual_ignored = parsed.get("ignored_workup_entities", [])
        passed = all(entity in actual_ignored for entity in ignored_expected)
        checks.append(_check("ignored_workup_entities", passed, ignored_expected, actual_ignored))

    unresolved_min = expected.get("unresolved_min", 0)
    checks.append(
        _check(
            "unresolved_min",
            len(parsed.get("unresolved", [])) >= unresolved_min,
            f">={unresolved_min}",
            len(parsed.get("unresolved", [])),
        )
    )
    return checks


def _check(name: str, passed: bool, expected: Any, actual: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "expected": expected, "actual": actual}


def _values_equal(actual: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return actual is expected
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        # Method prose commonly rounds volumes to two decimals. Values within
        # 0.5% are chemically identical for this extraction benchmark.
        return math.isclose(float(actual), float(expected), rel_tol=5e-3, abs_tol=1e-6)
    return actual == expected


def _compact_schema(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    keys = (
        "alias",
        "name",
        "role",
        "variable",
        "equivalents",
        "molecular_weight_g_mol",
        "density_g_ml",
        "concentration_m",
        "mass_mg",
        "amount_mmol",
        "volume_ml",
    )
    return [
        {key: chemical.get(key) for key in keys}
        for chemical in parsed["chemicals"]
        if chemical.get("role") != "workup"
    ]


def _identifier(name: str) -> str:
    import re

    value = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    if value and value[0].isdigit():
        value = "R_" + value
    return value


def _render_html(result: dict[str, Any]) -> str:
    cards = "\n".join(_render_case_card(case) for case in result["cases"])
    categories = sorted({case["category"] for case in result["cases"]})
    category_options = "".join(
        f'<option value="{html.escape(category)}">{html.escape(category)}</option>' for category in categories
    )
    summary = (
        f"{result['case_count']} cases · {result['supported_case_count']} supported · "
        f"{result['supported_pass_count']} automatic passes · "
        f"{result['known_limitation_count']} known limitations"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Procedure import validation 100 cases</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, Segoe UI, Arial, sans-serif; }}
    body {{ margin: 0; background: #f5f7fb; color: #18202c; }}
    header {{ position: sticky; top: 0; z-index: 2; padding: 18px 24px; background: white; border-bottom: 1px solid #d8dee9; }}
    h1 {{ margin: 0 0 6px; font-size: 24px; }}
    .summary {{ color: #536176; margin-bottom: 12px; }}
    .controls {{ display: flex; gap: 10px; flex-wrap: wrap; }}
    input, select, textarea {{ font: inherit; border: 1px solid #bec8d6; border-radius: 6px; padding: 7px 9px; background: white; }}
    #search {{ min-width: 320px; flex: 1; }}
    main {{ max-width: 1400px; margin: 20px auto; padding: 0 20px 60px; }}
    details.case {{ background: white; border: 1px solid #d8dee9; border-radius: 10px; margin: 10px 0; overflow: hidden; }}
    details.case > summary {{ cursor: pointer; padding: 14px 16px; font-weight: 650; display: flex; gap: 10px; align-items: center; }}
    .badge {{ border-radius: 999px; padding: 3px 8px; font-size: 12px; font-weight: 700; }}
    .pass {{ background: #dff6e9; color: #12683f; }}
    .fail {{ background: #ffe0df; color: #a52925; }}
    .manual_review_expected {{ background: #fff1c9; color: #765600; }}
    .category {{ background: #e7eefb; color: #315a96; }}
    .content {{ padding: 0 16px 18px; }}
    .grid {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 14px; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
    .panel {{ border: 1px solid #e1e6ee; border-radius: 8px; padding: 12px; min-width: 0; }}
    .panel h3 {{ margin: 0 0 8px; font-size: 15px; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #f7f9fc; padding: 10px; border-radius: 6px; margin: 0; font: 13px/1.45 Consolas, monospace; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border: 1px solid #dce2ea; padding: 6px; text-align: left; vertical-align: top; }}
    th {{ background: #f2f5f9; }}
    .review {{ display: flex; gap: 10px; align-items: center; margin-top: 12px; }}
    .review textarea {{ flex: 1; min-height: 36px; }}
    .failed-check {{ color: #a52925; font-weight: 650; }}
    .hidden {{ display: none; }}
  </style>
</head>
<body>
<header>
  <h1>Procedure import validation</h1>
  <div class="summary">{html.escape(summary)}. Synthetic cases, not publication-derived ground truth.</div>
  <div class="controls">
    <input id="search" type="search" placeholder="Search id, input, template or reagent">
    <select id="category"><option value="">All categories</option>{category_options}</select>
    <select id="automatic"><option value="">All automatic statuses</option><option value="pass">pass</option><option value="fail">fail</option><option value="manual_review_expected">manual review expected</option></select>
    <select id="reviewFilter"><option value="">All review statuses</option><option value="unreviewed">unreviewed</option><option value="correct">correct</option><option value="incorrect">incorrect</option><option value="discussion">needs discussion</option></select>
  </div>
</header>
<main id="cases">{cards}</main>
<script>
const storageKey = id => `procedure-import-review:${{id}}`;
document.querySelectorAll('.case').forEach(card => {{
  const id = card.dataset.id;
  const saved = JSON.parse(localStorage.getItem(storageKey(id)) || '{{}}');
  const select = card.querySelector('.review-status');
  const note = card.querySelector('.review-note');
  select.value = saved.status || 'unreviewed';
  note.value = saved.note || '';
  card.dataset.review = select.value;
  const save = () => {{
    card.dataset.review = select.value;
    localStorage.setItem(storageKey(id), JSON.stringify({{status: select.value, note: note.value}}));
    applyFilters();
  }};
  select.addEventListener('change', save);
  note.addEventListener('input', save);
}});
function applyFilters() {{
  const query = document.querySelector('#search').value.toLowerCase();
  const category = document.querySelector('#category').value;
  const automatic = document.querySelector('#automatic').value;
  const review = document.querySelector('#reviewFilter').value;
  document.querySelectorAll('.case').forEach(card => {{
    const visible = (!query || card.textContent.toLowerCase().includes(query)) &&
      (!category || card.dataset.category === category) &&
      (!automatic || card.dataset.automatic === automatic) &&
      (!review || card.dataset.review === review);
    card.classList.toggle('hidden', !visible);
  }});
}}
document.querySelectorAll('#search,#category,#automatic,#reviewFilter').forEach(element => element.addEventListener('input', applyFilters));
</script>
</body>
</html>"""


def _render_case_card(case: dict[str, Any]) -> str:
    schema_rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(_display(row.get(key)))}</td>" for key in ("alias", "name", "role", "equivalents", "molecular_weight_g_mol", "density_g_ml", "concentration_m")) + "</tr>"
        for row in case["actual"]["reaction_schema"]
    )
    checks = "".join(
        f"<li class=\"{'passed-check' if check['passed'] else 'failed-check'}\">"
        f"{'✓' if check['passed'] else '✗'} {html.escape(check['name'])}: expected "
        f"{html.escape(_display(check['expected']))}; actual {html.escape(_display(check['actual']))}</li>"
        for check in case["automatic_checks"]
    )
    actual_status = case["automatic_status"]
    expected_json = html.escape(json.dumps(case["expected"], ensure_ascii=False, indent=2))
    unresolved_json = html.escape(json.dumps(case["actual"]["unresolved"], ensure_ascii=False, indent=2))
    rationale = f"<p><strong>Why included:</strong> {html.escape(case['rationale'])}</p>" if case.get("rationale") else ""
    search_blob = " ".join(
        (
            case["input_method"],
            case["actual"]["template_text"],
            json.dumps(case["actual"]["reaction_schema"], ensure_ascii=False),
        )
    )
    return f"""
<details class="case" data-id="{html.escape(case['id'])}" data-category="{html.escape(case['category'])}" data-automatic="{html.escape(actual_status)}" data-review="unreviewed" data-search="{html.escape(search_blob)}">
  <summary><span>{html.escape(case['id'])}</span><span class="badge category">{html.escape(case['category'])}</span><span>{html.escape(case['title'])}</span><span class="badge {html.escape(actual_status)}">{html.escape(actual_status.replace('_', ' '))}</span></summary>
  <div class="content">
    {rationale}
    <div class="grid">
      <section class="panel"><h3>Input method</h3><pre>{html.escape(case['input_method'])}</pre><p><strong>Variable compounds:</strong> {html.escape(', '.join(case['variable_names']) or '<automatic>')}</p></section>
      <section class="panel"><h3>Generated SI template</h3><pre>{html.escape(case['actual']['template_text'])}</pre></section>
      <section class="panel"><h3>Generated reaction schema</h3><table><thead><tr><th>alias</th><th>name</th><th>role</th><th>eq</th><th>MW</th><th>density</th><th>concentration</th></tr></thead><tbody>{schema_rows}</tbody></table></section>
      <section class="panel"><h3>Expected checkpoints</h3><pre>{expected_json}</pre></section>
      <section class="panel"><h3>Automatic comparison</h3><ul>{checks}</ul></section>
      <section class="panel"><h3>Unresolved fields</h3><pre>{unresolved_json}</pre></section>
    </div>
    <div class="review"><strong>Your review</strong><select class="review-status"><option value="unreviewed">unreviewed</option><option value="correct">correct</option><option value="incorrect">incorrect</option><option value="discussion">needs discussion</option></select><textarea class="review-note" placeholder="Optional note"></textarea></div>
  </div>
</details>"""


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.8g}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the 100-case procedure importer validation pack.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "output" / "procedure_import_validation",
        help="Directory for JSON and HTML output.",
    )
    args = parser.parse_args(argv)
    result = evaluate_cases(build_cases())
    json_path, html_path = write_validation_pack(result, args.output_dir)
    print(f"JSON: {json_path}")
    print(f"HTML: {html_path}")
    print(
        f"Supported automatic checks: {result['supported_pass_count']}/{result['supported_case_count']} "
        f"({result['supported_pass_rate']:.1%})"
    )
    print(f"Status counts: {result['automatic_status_counts']}")
    return 0 if result["supported_pass_count"] == result["supported_case_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
