from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from si_generator.external_tools import find_mnova_executable


class ExternalToolsTests(unittest.TestCase):
    def test_find_mnova_accepts_quoted_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "MestReNova.exe"
            executable.write_text("placeholder", encoding="utf-8")

            found = find_mnova_executable(f'"{executable}"')

        self.assertEqual(found, executable.resolve())

    def test_find_mnova_accepts_quoted_environment_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "MestReNova.exe"
            executable.write_text("placeholder", encoding="utf-8")

            with patch.dict("os.environ", {"AUTO_SUPPORT_MNOVA_EXE": f'"{executable}"'}):
                found = find_mnova_executable()

        self.assertEqual(found, executable.resolve())


if __name__ == "__main__":
    unittest.main()
