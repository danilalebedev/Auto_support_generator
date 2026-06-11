from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from si_generator.gui import _build_generate_request, _build_result_summary


class GuiWorkflowTests(unittest.TestCase):
    def test_builds_graph_request_from_gui_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            table = root / "input.docx"
            spectra = root / "spectra.zip"
            output = root / "support_information.docx"
            table.write_text("placeholder", encoding="utf-8")
            spectra.write_text("placeholder", encoding="utf-8")

            request = _build_generate_request(
                input_kind="word",
                input_path_text=str(table),
                output_docx_text=str(output),
                spectra_zip_text=str(spectra),
                journal_profile_text="acs",
                references_text="",
                generate_loadings=True,
                check_support=False,
            )

        self.assertEqual(request.input_path, table)
        self.assertEqual(request.input_kind, "word")
        self.assertEqual(request.output_path, output)
        self.assertEqual(request.spectra_zip, spectra)
        self.assertEqual(request.journal_profile, "acs")
        self.assertTrue(request.generate_loadings)
        self.assertTrue(request.no_check_support)

    def test_rejects_missing_input_file(self) -> None:
        with self.assertRaisesRegex(ValueError, "compound table"):
            _build_generate_request(
                input_kind="csv",
                input_path_text="missing.csv",
                output_docx_text="support_information.docx",
            )

    def test_builds_result_summary_from_graph_state_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "support_information.docx"
            package = root / "processed_spectra.zip"
            manifest = root / "support_information.manifest.json"
            state = {
                "request": _build_generate_request(
                    input_kind="word",
                    input_path_text=__file__,
                    output_docx_text=str(output),
                ),
                "output_path": output,
                "artifacts": {
                    "support_docx": str(output),
                    "processed_spectra_zip": str(package),
                    "manifest": str(manifest),
                },
            }

            summary = _build_result_summary(state)

        self.assertEqual(summary["support_docx"], str(output.resolve()))
        self.assertEqual(summary["processed_spectra_zip"], str(package.resolve()))
        self.assertEqual(summary["manifest"], str(manifest.resolve()))


if __name__ == "__main__":
    unittest.main()
