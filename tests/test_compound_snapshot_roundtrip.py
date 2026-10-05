from si_generator.domain.compound import Compound, compound_from_domain_dict


def test_saved_compound_preserves_preparation_and_nmr_warnings():
    compound = Compound(
        number="3c", name="Example",
        preparation="Obtained from 150 mg (0.6 mmol); yield 87%.",
        nmr_check_warning="C signals expected 20, found 26",
        reaction={"method": "GP A"},
    )
    restored = compound_from_domain_dict(compound.to_domain_dict())
    assert restored.preparation == compound.preparation
    assert restored.nmr_check_warning == compound.nmr_check_warning
    assert restored.reaction["method"] == "GP A"
    assert compound.reaction == {"method": "GP A"}


def test_saved_reaction_preparation_survives_empty_legacy_field():
    compound = Compound(number="3c", name="Example", reaction={"preparation": "GP A"})
    assert compound_from_domain_dict(compound.to_domain_dict()).preparation == "GP A"


def test_saved_compound_accepts_missing_warnings_and_reaction():
    restored = compound_from_domain_dict({"number": "3c", "name": "Example"})
    assert restored.preparation == ""
    assert restored.nmr_check_warning == ""
