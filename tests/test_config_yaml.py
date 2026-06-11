from __future__ import annotations

import unittest

from si_generator.config_yaml import parse_simple_yaml
from si_generator.style_config import parse_simple_yaml as parse_legacy_style_yaml


class ConfigYamlTests(unittest.TestCase):
    def test_parses_nested_scalars_and_inline_lists(self) -> None:
        parsed = parse_simple_yaml(
            "generation:\n"
            "  include_ir: false\n"
            "  threshold: 0.75\n"
            "  order: [compound_descriptions, spectra_appendix]\n"
            "label: 'ACS SI'\n"
        )

        self.assertEqual(parsed["generation"]["include_ir"], False)
        self.assertEqual(parsed["generation"]["threshold"], 0.75)
        self.assertEqual(parsed["generation"]["order"], ["compound_descriptions", "spectra_appendix"])
        self.assertEqual(parsed["label"], "ACS SI")

    def test_style_config_reexports_simple_yaml_parser(self) -> None:
        self.assertIs(parse_legacy_style_yaml, parse_simple_yaml)


if __name__ == "__main__":
    unittest.main()
