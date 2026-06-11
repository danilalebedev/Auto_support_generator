from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from si_generator.graph.state import GenerateSIRequest
from si_generator.runtime_diagnostics import format_preflight_issues, issue_has_errors, preflight_generate_request


class RuntimeDiagnosticsTests(unittest.TestCase):
    def test_preflight_passes_for_basic_word_request_without_mnova(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_docx = root / "input.docx"
            input_docx.write_bytes(b"placeholder")
            output_docx = root / "nested" / "support_information.docx"
            request = GenerateSIRequest(
                input_path=input_docx,
                input_kind="word",
                output_path=output_docx,
                no_extract_nmr=True,
            )

            issues = preflight_generate_request(request, mnova_finder=_raising_mnova_finder)

        self.assertEqual(issues, [])

    def test_preflight_reports_invalid_spectra_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_docx = root / "input.docx"
            spectra_zip = root / "spectra.zip"
            input_docx.write_bytes(b"placeholder")
            spectra_zip.write_text("not a zip", encoding="utf-8")
            request = GenerateSIRequest(
                input_path=input_docx,
                input_kind="word",
                output_path=root / "support_information.docx",
                spectra_zip=spectra_zip,
                no_extract_nmr=True,
            )

            issues = preflight_generate_request(request)

        self.assertTrue(issue_has_errors(issues))
        self.assertIn("PREFLIGHT_SPECTRA_ZIP_INVALID", {issue["code"] for issue in issues})

    def test_preflight_requires_mnova_when_spectra_will_be_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_docx = root / "input.docx"
            spectra_zip = root / "spectra.zip"
            input_docx.write_bytes(b"placeholder")
            with zipfile.ZipFile(spectra_zip, "w") as archive:
                archive.writestr("2a/1H/fid", "fid")
            request = GenerateSIRequest(
                input_path=input_docx,
                input_kind="word",
                output_path=root / "support_information.docx",
                spectra_zip=spectra_zip,
                no_extract_nmr=False,
            )

            issues = preflight_generate_request(request, mnova_finder=_raising_mnova_finder)

        self.assertTrue(issue_has_errors(issues))
        self.assertIn("PREFLIGHT_MNOVA_NOT_FOUND", {issue["code"] for issue in issues})

    def test_preflight_skips_mnova_when_extraction_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_docx = root / "input.docx"
            spectra_zip = root / "spectra.zip"
            input_docx.write_bytes(b"placeholder")
            with zipfile.ZipFile(spectra_zip, "w") as archive:
                archive.writestr("2a/1H/fid", "fid")
            request = GenerateSIRequest(
                input_path=input_docx,
                input_kind="word",
                output_path=root / "support_information.docx",
                spectra_zip=spectra_zip,
                no_extract_nmr=True,
            )

            issues = preflight_generate_request(request, mnova_finder=_raising_mnova_finder)

        self.assertEqual(issues, [])

    def test_format_preflight_issues_is_log_friendly(self) -> None:
        issues = [{"code": "PREFLIGHT_INPUT_MISSING", "severity": "error", "message": "Missing", "path": "input.docx"}]

        formatted = format_preflight_issues(issues)

        self.assertIn("[ERROR] PREFLIGHT_INPUT_MISSING: Missing (input.docx)", formatted)


def _raising_mnova_finder(path):
    raise FileNotFoundError("not found")


if __name__ == "__main__":
    unittest.main()
