from __future__ import annotations

import unittest

from si_generator.domain.generation_config import build_generation_config


class GenerationConfigTests(unittest.TestCase):
    def test_builds_defaults_from_runtime_flags(self) -> None:
        config = build_generation_config(generate_loadings=True, has_references=True, check_support=False)

        self.assertTrue(config["generate_loadings"])
        self.assertTrue(config["include_ir"])
        self.assertTrue(config["include_elemental_analysis"])
        self.assertFalse(config["calculate_elemental_analysis"])
        self.assertTrue(config["include_references"])
        self.assertFalse(config["check_support"])

    def test_references_are_disabled_without_reference_file(self) -> None:
        config = build_generation_config(has_references=False)

        self.assertTrue(config["include_ir"])
        self.assertTrue(config["include_elemental_analysis"])
        self.assertFalse(config["calculate_elemental_analysis"])
        self.assertFalse(config["include_references"])


if __name__ == "__main__":
    unittest.main()
