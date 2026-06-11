from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from docx import Document

from si_generator.graph.state import GenerateSIRequest
from si_generator.workflows.generate_si import output_path_from_state, run_generate_si


REPO_ROOT = Path(__file__).resolve().parents[1]


class GenerateWorkflowTests(unittest.TestCase):
    def test_graph_generates_docx_without_mnova_or_support_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "support_information.docx"
            request = GenerateSIRequest(
                input_path=REPO_ROOT / "examples" / "test_input.docx",
                input_kind="word",
                spectra_zip=REPO_ROOT / "examples" / "test_input.zip",
                output_path=output_path,
                no_extract_nmr=True,
                no_check_support=True,
            )

            state = run_generate_si(request)

            self.assertEqual(output_path_from_state(state), output_path)
            self.assertTrue(output_path.exists())
            self.assertEqual(Path(state["artifacts"]["support_docx"]), output_path)
            self.assertIn("spectra_root", state["artifacts"])
            text = "\n".join(paragraph.text for paragraph in Document(output_path).paragraphs)
            self.assertIn("Methyl (E)-3-(2-(bromomethyl)phenyl)acrylate", text)
            self.assertNotIn("Compound 2a", text)


if __name__ == "__main__":
    unittest.main()
