from __future__ import annotations

import unittest

from si_generator.domain.runtime_config import build_runtime_config


class RuntimeConfigTests(unittest.TestCase):
    def test_builds_default_runtime_config(self) -> None:
        config = build_runtime_config()

        self.assertFalse(config["gui"])
        self.assertFalse(config["debug"])
        self.assertFalse(config["dry_run"])

    def test_builds_runtime_config_from_flags(self) -> None:
        config = build_runtime_config(gui=True, debug=True, dry_run=True)

        self.assertTrue(config["gui"])
        self.assertTrue(config["debug"])
        self.assertTrue(config["dry_run"])


if __name__ == "__main__":
    unittest.main()
