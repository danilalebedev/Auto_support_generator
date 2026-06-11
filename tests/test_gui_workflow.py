from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from si_generator.gui import (
    _build_check_request,
    _build_generate_request,
    _build_patch_request,
    _build_patch_summary,
    _build_result_summary,
)


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
            warnings = root / "logs" / "input_warnings.txt"
            support_warnings = root / "logs" / "support_warnings.txt"
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
                    "input_warnings": str(warnings),
                    "support_warnings": str(support_warnings),
                },
            }

            summary = _build_result_summary(state)

        self.assertEqual(summary["support_docx"], str(output.resolve()))
        self.assertEqual(summary["processed_spectra_zip"], str(package.resolve()))
        self.assertEqual(summary["manifest"], str(manifest.resolve()))
        self.assertEqual(summary["input_warnings"], str(warnings.resolve()))
        self.assertEqual(summary["support_warnings"], str(support_warnings.resolve()))

    def test_builds_check_request_from_manifest_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "support_information.manifest.json"
            manifest.write_text("{}", encoding="utf-8")

            request = _build_check_request(str(manifest))

        self.assertEqual(request.manifest_path, manifest)

    def test_builds_patch_request_from_gui_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "support_information.manifest.json"
            output = root / "patched.docx"
            manifest.write_text("{}", encoding="utf-8")

            request = _build_patch_request(
                manifest_text=str(manifest),
                renumber_text="2a=3a,2b=3b",
                remove_text="2c",
                reorder_text="2b,2a",
                output_docx_text=str(output),
            )

        self.assertEqual(request.manifest_path, manifest)
        self.assertEqual(request.renumber, {"2a": "3a", "2b": "3b"})
        self.assertEqual(request.remove, ("2c",))
        self.assertEqual(request.reorder, ("2b", "2a"))
        self.assertEqual(request.output_docx, output)

    def test_patch_request_requires_operation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "support_information.manifest.json"
            manifest.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "renumber, remove, or reorder"):
                _build_patch_request(
                    manifest_text=str(manifest),
                    renumber_text="",
                    remove_text="",
                    reorder_text="",
                )

    def test_builds_patch_summary_from_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            support = root / "patched.docx"
            manifest = root / "patched.manifest.json"

            summary = _build_patch_summary(
                {
                    "artifacts": {
                        "support_docx": str(support),
                        "manifest": str(manifest),
                    }
                }
            )

        self.assertEqual(summary["support_docx"], str(support.resolve()))
        self.assertEqual(summary["manifest"], str(manifest.resolve()))


if __name__ == "__main__":
    unittest.main()
