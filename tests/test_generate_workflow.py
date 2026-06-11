from __future__ import annotations

import tempfile
import unittest
import json
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
            manifest_path = output_path.with_suffix(".manifest.json")
            self.assertTrue(manifest_path.exists())
            self.assertEqual(Path(state["artifacts"]["support_docx"]), output_path)
            self.assertEqual(Path(state["artifacts"]["manifest"]), manifest_path)
            self.assertIn("spectra_root", state["artifacts"])
            self.assertIn("1H", state["spectra_plan"]["cmp_001"])
            self.assertIn("13C", state["spectra_plan"]["cmp_001"])
            self.assertIsInstance(state["compounds"]["cmp_001"].nmr_spectra, dict)
            self.assertEqual(state["document_model"]["sections"][0]["id"], "compound_descriptions")
            self.assertEqual(state["document_model"]["sections"][0]["blocks"][0]["compound_id"], "cmp_001")
            self.assertEqual(state["journal_profile"]["id"], "default")
            self.assertEqual(state["document_model"]["metadata"]["journal_profile"], "default")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["order"][:2], ["cmp_001", "cmp_002"])
            self.assertEqual(manifest["compounds"]["cmp_001"]["number"], "2a")
            self.assertIn("compound_table", manifest["input_hashes"])
            self.assertIn("spectra_zip", manifest["input_hashes"])
            self.assertFalse(manifest["configs"]["spectra"]["extract_nmr"])
            self.assertFalse(manifest["configs"]["generation"]["check_support"])
            self.assertEqual(manifest["configs"]["journal_profile"], "default")
            self.assertEqual(Path(manifest["artifacts"]["support_docx"]), output_path)
            self.assertEqual(Path(manifest["artifacts"]["manifest"]), manifest_path)
            text = "\n".join(paragraph.text for paragraph in Document(output_path).paragraphs)
            self.assertIn("Methyl (E)-3-(2-(bromomethyl)phenyl)acrylate", text)
            self.assertNotIn("Compound 2a", text)


if __name__ == "__main__":
    unittest.main()
