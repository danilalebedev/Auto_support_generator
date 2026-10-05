import pytest

from si_generator.template_renderer import _chemical_token_segments, _formula_with_isotope_labels


@pytest.mark.parametrize('formula,counts', [('C22H21O4+', ['22', '21', '4']), ('C27H22O5Na+', ['27', '22', '5'])])
def test_atom_counts_are_not_guessed_as_isotopes(formula, counts):
    segments = _chemical_token_segments(formula)
    assert [text for text, flags in segments if flags.get('subscript')] == counts
    assert [text for text, flags in segments if flags.get('superscript')] == ['+']


@pytest.mark.parametrize('formula,labels,expected', [
    ('C25H18BrO3+', {'Br': 79}, '79'),
    ('C2H6O', {'C': 13}, '13'),
    ('C2H6O', {'H': 2}, '2'),
])
def test_explicit_isotope_metadata_is_typeset_as_superscript(formula, labels, expected):
    segments = _chemical_token_segments(_formula_with_isotope_labels(formula, labels))
    assert expected in [text for text, flags in segments if flags.get('superscript')]
    assert '^' not in ''.join(text for text, _flags in segments)
