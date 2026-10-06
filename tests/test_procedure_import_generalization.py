"""Regression checks derived from failure classes, not held-out article labels."""
from si_generator.procedure_import import parse_procedure


def active(result):
    return [c for c in result["chemicals"] if c["role"] not in {"workup", "product", "equipment"}]


def test_equipment_dimensions_do_not_become_reagents():
    result = parse_procedure("Alkene 1 (1 mmol) and DBU (2 mmol) in DCM (5 mL) were stirred using a carbon plate (20 mm x 10 mm x 1 mm) and a platinum plate (15 mm x 10 mm x 0.1 mm).", variable_names=["Alkene 1"])
    assert {c["name"] for c in active(result)} == {"Alkene 1", "DBU", "DCM"}


def test_product_mass_and_late_workup_stay_literal():
    result = parse_procedure("Substrate 1 (100 mg, 1 mmol) was stirred in THF (5 mL). The mixture was filtered over Celite. The residue was suspended in ethanol (50 mL) and cooled, giving product 2 as an off-white powder (90 mg, 85% yield).", variable_names=["Substrate 1"])
    assert len(active(result)) == 2
    assert "ethanol (50 mL)" in result["template_text"]
    assert "powder (90 mg" in result["template_text"]


def test_unquantified_variable_and_compound_prefix_match_once():
    result = parse_procedure("The substrates alkyne-tethered ketoesters 1 (0.20 mmol, 1 equiv.) and boronic acid 2 (0.40 mmol, 2 equiv.) were stirred in ethyl acetate (3 mL).",variable_names=["alkyne-tethered ketoesters 1", "boronic acid 2"])
    variable = [c for c in active(result) if c["variable"]]
    assert len(variable) == 2
    assert variable[0]["amount_mmol"] == .2


def test_nested_prefix_name_remains_intact():
    result = parse_procedure("Substrate A (1 mmol) was treated with 10 mg (0.01 mmol) of Pd(PPh3)4 and NBS (1 mmol) in THF (5 mL).", variable_names=["Substrate A"])
    assert any(c["name"] == "Pd(PPh3)4" and c["mass_mg"] == 10 for c in active(result))


def test_purity_does_not_mark_mol_percent_as_formulation():
    result = parse_procedure("Substrate A (1 mmol) and DMAP (5 mol%) were stirred in DCM (5 mL).",variable_names=["Substrate A"])
    catalyst = next(c for c in result["chemicals"] if c["name"] == "DMAP")
    assert not catalyst["formulation"]


def test_no_zero_scale_assumption_for_missing_reference():
    result = parse_procedure("Substrate A and NBS (1.2 equiv.) were stirred in THF (5 mL).",variable_names=["Substrate A"])
    assert result["reference_amount_mmol"] is None
    assert any(i.get("field") == "concentration_m" for i in result["unresolved"])


def test_fractional_prefix_does_not_extract_last_digit_as_full_loading():
    result = parse_procedure("Substrate A (1 mmol) and catalyst Q (1/2 equiv.) were stirred in THF (5 mL).",variable_names=["Substrate A"])
    assert not any(i.get("field") == "method" for i in result["unresolved"])
    assert next(c for c in active(result) if c["name"] == "catalyst Q")["equivalents"] == .5
    assert "{catalyst_Q.eq} equiv" in result["template_text"]
    assert "1/{catalyst_Q.eq}" not in result["template_text"]


def test_solvent_mixture_does_not_assign_total_to_last_component():
    result = parse_procedure("Substrate A (1 mmol) and K2CO3 (2 mmol) were stirred in a mixture of ethanol and water (12 mL, 4:1).",variable_names=["Substrate A"])
    solvents = [c for c in active(result) if c["role"] == "solvent"]
    assert len(solvents) == 1
    assert solvents[0]["name"] == "ethanol and water"
    assert solvents[0]["volume_ml"] == 12


def test_next_stage_after_workup_is_not_discarded():
    result = parse_procedure("Substrate A (1 mmol) was stirred in DCM (5 mL). The mixture was extracted with water (10 mL), dried and concentrated. The crude residue was redissolved in THF (3 mL), and DBU (2 mmol) was added and stirred for 2 h.",variable_names=["Substrate A"])
    assert any(c["name"] == "DBU" and c["role"] == "reagent" for c in active(result))
    assert any(i.get("field") == "method" for i in result["unresolved"])


def test_explicit_substrate_takes_priority_over_first_salt():
    result = parse_procedure("KCN (35.1 mg, 0.54 mmol), NH4Cl (28.9 mg, 0.54 mmol), and the starting material 12a (23.8 mg, 0.09 mmol) were stirred in DMF (4 mL).")
    assert result["reference_chemical"] == "starting material 12a"
    assert result["reference_amount_mmol"] == .09
    assert next(c for c in result["chemicals"] if c["name"] == "KCN")["variable"] is False
    assert any(i.get("field") == "variable_assignment" for i in result["unresolved"])


def test_user_reference_overrides_automatic_substrate_cue():
    result = parse_procedure("Reagent A (1 mmol) and substrate B (2 mmol) were stirred in THF (5 mL).", variable_names=["Reagent A"])
    assert result["reference_chemical"] == "Reagent A"
    assert result["reference_amount_mmol"] == 1


def test_obtained_from_uses_first_reagent_for_concentration_and_ignores_tlc_solvents():
    procedure = (
        "Cyclobutane 3d was obtained from cyclopropane 2d (200 mg, 0.8 mmol), "
        "4a (203 mg, 1.1 mmol) in DCE (1.5 mL) according to General procedure A, 6.5 h. "
        "Yield 231 mg (80%); white solid; mp 147-148 °C; "
        "Rf=0.36 (petroleum ether - ethyl acetate, 4:1)."
    )
    result = parse_procedure(procedure)
    by_name = {chemical["name"]: chemical for chemical in active(result)}

    assert result["reference_chemical"] == "cyclopropane 2d"
    assert result["reference_amount_mmol"] == 0.8
    assert by_name["cyclopropane 2d"]["alias"] == "Reagent_1"
    assert by_name["cyclopropane 2d"]["mass_mg"] == 200
    assert by_name["4a"]["amount_mmol"] == 1.1
    assert abs(by_name["DCE"]["concentration_m"] - (0.8 / 1.5)) < 1e-9
    assert "petroleum ether" not in by_name
    assert "ethyl acetate" not in by_name

    explicitly_marked = parse_procedure(procedure, variable_names=["2d"])
    active_names = [chemical["name"] for chemical in active(explicitly_marked)]
    assert explicitly_marked["reference_chemical"] == "cyclopropane 2d"
    assert active_names.count("cyclopropane 2d") == 1
    assert "2d" not in active_names


def test_mass_after_chemical_before_loading_parentheses():
    result = parse_procedure("Substrate A 120 mg (0.5 mmol, 1 equiv.) followed by NBS (1 mmol) were stirred in THF (5 mL).", variable_names=["Substrate A"])
    substrate = next(c for c in active(result) if c["name"] == "Substrate A")
    assert substrate["mass_mg"] == 120
    assert substrate["amount_mmol"] == .5
    assert "{Reagent_1.name} {Reagent_1.mg} mg" in result["template_text"]


def test_sampling_aliquots_are_not_reagents():
    result = parse_procedure("Substrate A (1 mmol) was stirred in THF (5 mL). A 20 µL aliquot was withdrawn for GC analysis.", variable_names=["Substrate A"])
    assert not any("aliquot" in c["name"] for c in active(result))
    assert "20 µL aliquot" in result["template_text"]


def test_symbolic_catalyst_loading_is_unresolved_not_missing():
    result = parse_procedure("Substrate A (1 mmol), catalyst Q (Y mol%) and base (x equiv.) were stirred in THF (5 mL).", variable_names=["Substrate A"])
    assert {c["name"] for c in active(result)} == {"Substrate A", "catalyst Q", "base", "THF"}
    assert next(c for c in active(result) if c["name"] == "base")["equivalents"] is None
    assert "(Y mol%)" in result["template_text"]


def test_glacial_acetic_acid_volume_is_a_solvent_not_reference():
    result = parse_procedure("Substrate A (1 mmol) in glacial acetic acid (5 mL) was heated with HCl (1 mmol).", variable_names=["Substrate A"])
    assert next(c for c in active(result) if c["name"] == "glacial acetic acid")["role"] == "solvent"


def test_stock_concentration_and_purity_are_not_chemical_names():
    result = parse_procedure("Substrate A (1 mmol) was treated with 200 µL aqueous 3 M NaOH and 200 µL 30% H2O2 in THF (5 mL).", variable_names=["Substrate A"])
    base = next(c for c in active(result) if c["name"] == "NaOH")
    assert base["volume_ml"] == .2
    assert base["concentration_m"] == 3
    peroxide = next(c for c in active(result) if c["name"] == "H2O2")
    assert peroxide["formulation"] is True
    assert "aqueous 3 M NaOH" in result["template_text"]
    assert "30% H2O2" in result["template_text"]


def test_later_stage_recognition_survives_decimal_loadings():
    result = parse_procedure("Substrate A (1 mmol) was stirred in THF (5 mL). The mixture was filtered and concentrated to afford the crude intermediate. Catalyst Q (0.1 mmol) and EDCI (1.1 equiv.) were added, and the suspension was stirred overnight.", variable_names=["Substrate A"])
    assert next(c for c in active(result) if c["name"] == "Catalyst Q")["amount_mmol"] == .1


def test_colon_solvent_mixture_at_start_of_text():
    result = parse_procedure("MeCN:H2O (20:1, 5 mL) and substrate A (1 mmol) were stirred.", variable_names=["substrate A"])
    solvents = [c for c in active(result) if c["role"] == "solvent"]
    assert len(solvents) == 1
    assert solvents[0]["name"] == "MeCN:H2O"
    assert solvents[0]["volume_ml"] == 5


def test_reaction_start_after_reagent_preparation_filtration():
    result = parse_procedure("Monomer was filtered through alumina. To a 5 mL vial was added substrate A (1 mmol) and catalyst Q (0.1 mmol) in THF (5 mL). The mixture was stirred for 2 h.", variable_names=["substrate A"])
    assert {c["name"] for c in active(result)} == {"substrate A", "catalyst Q", "THF"}


def test_copper_wire_with_chemical_loading_is_not_equipment_dimensions():
    result = parse_procedure("Substrate A (1 mmol) and Cu (0) wire (20 mg, 0.315 mmol) were stirred in THF (5 mL), using a platinum wire (1 mm x 20 mm).", variable_names=["Substrate A"])
    assert next(c for c in active(result) if c["name"] == "Cu (0) wire")["mass_mg"] == 20
    assert not any(c["name"] == "platinum wire" for c in active(result))


def test_literature_aside_between_name_and_loading():
    result = parse_procedure("Substrate A (1 mmol) and ester B, prepared as previously described,4 (50 mg, 0.5 mmol) were stirred in THF (5 mL).", variable_names=["Substrate A", "ester B"])
    assert next(c for c in active(result) if c["name"] == "ester B")["mass_mg"] == 50


def test_corresponding_prefix_does_not_duplicate_marked_substrate():
    result = parse_procedure("The corresponding substrate 1 (0.4 mmol, 4 equiv.) was stirred in THF (5 mL).", variable_names=["substrate 1"])
    substrates = [c for c in active(result) if c["variable"]]
    assert len(substrates) == 1
    assert substrates[0]["amount_mmol"] == .4


def test_stock_solution_quantities_belong_to_active_reagent():
    result = parse_procedure("Substrate A (1 mmol) and HCl in Et2O (2 M, 5 mL, 10 mmol) were stirred in THF (5 mL).", variable_names=["Substrate A"])
    stock=next(c for c in active(result) if c["name"] == "HCl in Et2O")
    assert stock["role"] == "reagent"
    assert stock["amount_mmol"] == 10
    assert stock["volume_ml"] == 5
    assert stock["formulation"] is True
    assert not any(c["name"]=="Et2O" and c["amount_mmol"]==10 for c in active(result))


def test_marked_stock_partner_retains_carrier_literal():
    result = parse_procedure("Substrate A (1 mmol) and partner B in hexane (2 M, 1 mL, 2 mmol) were stirred in THF (5 mL).", variable_names=["Substrate A", "partner B"])
    assert "{Reagent_2.name} in hexane (2 M, {Reagent_2.ml} mL, {Reagent_2.mmol} mmol)" in result["template_text"]


def test_normality_is_not_silently_molarity():
    result = parse_procedure("Substrate A (1 mmol) and 6 N HCl (2 mL) were stirred in THF (5 mL).", variable_names=["Substrate A"])
    acid=next(c for c in active(result) if c["name"]=="HCl")
    assert acid["concentration_m"] is None
    assert acid["formulation"] is True
    assert any("Normality" in item["issue"] for item in result["unresolved"])


def test_marked_second_stage_substrate_is_not_silently_discarded():
    result = parse_procedure("Substrate A (1 mmol) was stirred in THF (5 mL). The mixture was filtered and concentrated. Substrate B (2 mmol) was added and stirred overnight.", variable_names=["Substrate A", "Substrate B"])
    assert next(c for c in active(result) if c["name"]=="Substrate B")["amount_mmol"] == 2
    assert any("stage review" in item["issue"] for item in result["unresolved"])
def test_prefix_quantity_preserves_parenthesized_compound_label():
    parsed = parse_procedure("144 mg (0.6 mmol) methyl ((methylsulfonyl)oxy)-L-leucinate (3ab) and pyridine were dissolved in THF.", variable_names=["methyl ((methylsulfonyl)oxy)-L-leucinate (3ab)"])
    assert len([c for c in parsed["chemicals"] if c["variable"]]) == 1
    assert "{Reagent_1.name}" in parsed["template_text"]
    assert "{Reagent_1.mg}" in parsed["template_text"]


def test_user_marked_label_that_looks_like_volume_retains_loadings():
    parsed = parse_procedure("3l (26.5 mg, 0.1 mmol) and DCM were added to a flask.", variable_names=["3l"])
    assert "{Reagent_1.name} ({Reagent_1.mg} mg, {Reagent_1.mmol} mmol)" in parsed["template_text"]


def test_user_marked_suffix_after_unpunctuated_heading():
    parsed = parse_procedure("Product heading pyridine A (10 mg, 1 mmol) was dissolved in THF.", variable_names=["pyridine A"])
    assert parsed["template_text"].startswith("Product heading {Reagent_1.name} ({Reagent_1.mg}")


def test_dry_solvent_variants_share_identity_without_losing_occurrences():
    parsed = parse_procedure("A (1 mmol) was dissolved in 1 mL anhyd THF. B (2 mmol) in 1 mL anhyd. THF was added.", variable_names=["A", "B"])
    solvents = [c for c in parsed["chemicals"] if c["role"] == "solvent"]
    assert len(solvents) == 1
    assert len([q for q in solvents[0]["quantities"] if q["kind"] == "volume_ml" and not q["derived"]]) == 2


def test_leading_yield_is_not_a_reagent_loading():
    parsed = parse_procedure("Yield: 81 mg (46%) a) 144 mg (0.6 mmol) substrate A was dissolved in THF.", variable_names=["substrate A"])
    assert parsed["template_text"].startswith("Yield: 81 mg (46%)")
    assert not any(c["name"] == "a) 144 mg" for c in parsed["chemicals"])


def test_stock_with_only_concentration_and_volume_belongs_to_active_reagent():
    parsed = parse_procedure("A (1 mmol) and HCl in Et2O (2 M, 5 mL) were stirred.", variable_names=["A"])
    stock = next(c for c in parsed["chemicals"] if c["name"] == "HCl in Et2O")
    assert stock["role"] == "reagent"
    assert stock["property_sources"]["stock_carrier"]["name"] == "Et2O"
    assert not any(c["name"] == "Et2O" for c in parsed["chemicals"])


def test_stock_parenthetical_carrier_is_not_assigned_separate_loading():
    parsed = parse_procedure("A (1 mmol) and Me2Zn (0.6 M solution in Et2O/DME, 5 mL, 3 mmol) were stirred.", variable_names=["A"])
    stock = next(c for c in parsed["chemicals"] if c["name"] == "Me2Zn")
    assert stock["formulation"]
    assert stock["property_sources"]["stock_carrier"]["name"] == "Et2O/DME"
    assert not any(c["name"] == "Et2O/DME" for c in parsed["chemicals"])


def test_marked_numeric_partner_does_not_steal_formula_suffix():
    parsed = parse_procedure("A (1 mmol), 2 (2 mmol) and Pd(S-BINAP)Cl 2 (8 mg, 0.01 mmol) were stirred.", variable_names=["A","2"])
    catalyst=next(c for c in parsed["chemicals"] if c["name"]=="Pd(S-BINAP)Cl 2")
    assert not catalyst["variable"]
    assert any(q["value"]==8 and q["kind"]=="mass_mg" for q in catalyst["quantities"])


def test_marked_reagent_does_not_claim_vessel_capacity():
    parsed = parse_procedure("A 500 mL round-bottom flask containing decalin S5 (14.4 g, 44.9 mmol) was placed under argon.",variable_names=["decalin S5"])
    assert parsed["template_text"].startswith("A 500 mL round-bottom flask")
    reagent=next(c for c in parsed["chemicals"] if c["variable"])
    assert not any(q["kind"]=="volume_ml" and not q["derived"] for q in reagent["quantities"])


def test_freshly_distilled_solvent_is_not_rejected_as_led_equipment():
    parsed = parse_procedure("A (1 mmol) was stirred in freshly distilled iPrOH (5 mL).",variable_names=["A"])
    assert any(c["role"]=="solvent" and "iPrOH" in c["name"] for c in parsed["chemicals"])


def test_stock_concentration_before_active_name_preserves_ownership():
    parsed = parse_procedure("A (1 mmol) and 2 M NaOtBu in THF (2 equiv, 2 mmol, 1 mL) were stirred.",variable_names=["A"])
    stock=next(c for c in parsed["chemicals"] if c["name"]=="NaOtBu in THF")
    assert stock["role"]=="reagent"
    assert any(q["kind"]=="concentration_m" and q["value"]==2 for q in stock["quantities"])


def test_spaced_locants_do_not_split_chemical_identity():
    name="2-tert-butyl-1, 1, 3, 3-tetramethylguanidine"
    parsed = parse_procedure(f"A (1 mmol) and {name} (300 µL, 1.9 mmol) were stirred.", variable_names=["A"])
    assert any(c["name"]==name for c in parsed["chemicals"])


def test_catalog_normalization_accepts_drying_description():
    from si_generator.reagent_catalog import normalize_reagent_name
    assert normalize_reagent_name("freshly distilled iPrOH")=="iproh"
    assert normalize_reagent_name("anhyd. THF")=="thf"


def test_terminal_aqueous_addition_before_extraction_is_workup():
    parsed=parse_procedure("A (1 mmol) was stirred for 2 h. Saturated NaHCO3 (10 mL) was added and the mixture was extracted with EtOAc.",variable_names=["A"])
    assert any("NaHCO3" in name for name in parsed["ignored_workup_entities"])


def test_residue_redissolution_remains_workup_unless_new_reaction_follows():
    purification=parse_procedure("A (1 mmol) was stirred and concentrated. The residue was taken up in petroleum ether (10 mL), filtered and purified.",variable_names=["A"])
    assert "petroleum ether" in purification["ignored_workup_entities"]
    stage=parse_procedure("A (1 mmol) was stirred and concentrated. The residue was dissolved in THF (5 mL), B (2 mmol) was added and stirred for 2 h.",variable_names=["A","B"])
    assert any(c["name"]=="THF" and c["role"]=="solvent" for c in stage["chemicals"])


def test_component_specific_slash_loadings_remain_literal():
    parsed=parse_procedure("A (1 mmol), Pd/SPhos (10 mg/12 mg) in DCM/toluene (4 mL/4 mL) were stirred.",variable_names=["A"])
    assert "10 mg/12 mg" in parsed["template_text"] and "4 mL/4 mL" in parsed["template_text"]
    assert not any(q["span"][0] in {16,22,44,49} for c in parsed["chemicals"] for q in c["quantities"] if not q["derived"])


def test_missing_space_before_numbered_solvent_is_parsed_without_rewriting_source():
    parsed=parse_procedure("A (1 mmol) in1,4-dioxane (5 mL) was stirred.",variable_names=["A"])
    assert any(c["name"]=="1,4-dioxane" for c in parsed["chemicals"])
    assert "in1,4-dioxane" in parsed["template_text"]


def test_general_prose_prefixes_are_not_part_of_chemical_names():
    parsed=parse_procedure("After that I2 (228 mg, 0.9 mmol) was added. To a toluene solution (4 mL) was added B (1 mmol).",variable_names=["B"])
    names={c["name"] for c in parsed["chemicals"]}
    assert "I2" in names and "toluene" in names


def test_quantity_before_solvent_name_is_owned_without_joining_name():
    parsed=parse_procedure("A (1 mmol) in 4 mL Acetone (0.05 M) was heated.",variable_names=["A"])
    solvent=next(c for c in parsed["chemicals"] if c["name"]=="Acetone")
    assert {(q["kind"],q["value"]) for q in solvent["quantities"] if not q["derived"]}=={("volume_ml",4),("concentration_m",.05)}


def test_cooling_bath_and_separatory_funnel_are_not_chemicals():
    parsed=parse_procedure("A (1 mmol) in THF (5 mL) was cooled in a dry ice/acetonitrile bath. The mixture was transferred to a 2 L separatory funnel.",variable_names=["A"])
    assert not any(c["name"] in {"acetonitrile","separatory funnel"} for c in parsed["chemicals"])
