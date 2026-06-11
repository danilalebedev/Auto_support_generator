from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from docx import Document

from si_generator.cli import main as cli_main
from si_generator.word_input import read_word_compounds


REPO_ROOT = Path(__file__).resolve().parents[1]


class WordAndDocxSmokeTests(unittest.TestCase):
    def test_reads_example_word_input(self) -> None:
        compounds = read_word_compounds(REPO_ROOT / "examples" / "test_input.docx")
        self.assertEqual([compound.number for compound in compounds[:2]], ["2a", "2b"])
        self.assertTrue(compounds[0].name.startswith("Methyl"))
        self.assertTrue(compounds[0].has_word_structure)

    def test_cli_generates_docx_without_mnova(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "support_information.docx"
            stdout = StringIO()
            with redirect_stdout(stdout), redirect_stderr(StringIO()):
                exit_code = cli_main(
                    [
                        "--word-input",
                        str(REPO_ROOT / "examples" / "test_input.docx"),
                        "--spectra-zip",
                        str(REPO_ROOT / "examples" / "test_input.zip"),
                        "--no-extract-nmr",
                        "--no-check-support",
                        "--output",
                        str(output_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(output_path.exists())
            self.assertTrue(output_path.with_suffix(".run_summary.json").exists())
            self.assertIn("Run summary:", stdout.getvalue())
            text = "\n".join(paragraph.text for paragraph in Document(output_path).paragraphs)
            self.assertIn("Methyl (E)-3-(2-(bromomethyl)phenyl)acrylate", text)
            self.assertNotIn("Compound 2a", text)


if __name__ == "__main__":
    unittest.main()
