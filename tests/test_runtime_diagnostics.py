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
                insert_spectra_as="none",
            )

            issues = preflight_generate_request(request, mnova_finder=_raising_mnova_finder)

        self.assertEqual(issues, [])

    def test_preflight_reports_invalid_spectra_source_zip(self) -> None:
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

    def test_preflight_reports_unsafe_spectra_source_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_docx = root / "input.docx"
            spectra_zip = root / "spectra.zip"
            input_docx.write_bytes(b"placeholder")
            with zipfile.ZipFile(spectra_zip, "w") as archive:
                archive.writestr("../evil.txt", "owned")
            request = GenerateSIRequest(
                input_path=input_docx,
                input_kind="word",
                output_path=root / "support_information.docx",
                spectra_source=spectra_zip,
                no_extract_nmr=True,
            )

            issues = preflight_generate_request(request)

        self.assertTrue(issue_has_errors(issues))
        self.assertIn("PREFLIGHT_SPECTRA_ZIP_UNSAFE", {issue["code"] for issue in issues})

    def test_preflight_warns_when_spectra_appendix_is_enabled_without_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_docx = root / "input.docx"
            input_docx.write_bytes(b"placeholder")
            request = GenerateSIRequest(
                input_path=input_docx,
                input_kind="word",
                output_path=root / "support_information.docx",
                insert_spectra_as="png",
            )

            issues = preflight_generate_request(request, mnova_finder=_raising_mnova_finder)

        self.assertFalse(issue_has_errors(issues))
        self.assertIn("PREFLIGHT_SPECTRA_SOURCE_NOT_SELECTED", {issue["code"] for issue in issues})

    def test_preflight_accepts_spectra_source_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_docx = root / "input.docx"
            spectra_folder = root / "spectra"
            input_docx.write_bytes(b"placeholder")
            spectra_folder.mkdir()
            request = GenerateSIRequest(
                input_path=input_docx,
                input_kind="word",
                output_path=root / "support_information.docx",
                spectra_source=spectra_folder,
                no_extract_nmr=True,
            )

            issues = preflight_generate_request(request, mnova_finder=_raising_mnova_finder)

        self.assertFalse(issue_has_errors(issues))

    def test_preflight_is_silent_without_zip_when_spectra_appendix_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_docx = root / "input.docx"
            input_docx.write_bytes(b"placeholder")
            request = GenerateSIRequest(
                input_path=input_docx,
                input_kind="word",
                output_path=root / "support_information.docx",
                insert_spectra_as="none",
            )

            issues = preflight_generate_request(request, mnova_finder=_raising_mnova_finder)

        self.assertEqual(issues, [])

    def test_preflight_reports_incomplete_loadings_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_docx = root / "input.docx"
            schema = root / "Reaction_schema.docx"
            input_docx.write_bytes(b"placeholder")
            schema.write_bytes(b"placeholder")
            request = GenerateSIRequest(
                input_path=input_docx,
                input_kind="word",
                output_path=root / "support_information.docx",
                insert_spectra_as="none",
                loadings_schema_docx=schema,
            )

            issues = preflight_generate_request(request, mnova_finder=_raising_mnova_finder)

        self.assertTrue(issue_has_errors(issues))
        self.assertIn("PREFLIGHT_LOADINGS_FILES_INCOMPLETE", {issue["code"] for issue in issues})

    def test_preflight_reports_invalid_mnova_graphics_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_docx = root / "input.docx"
            profile = root / "default.txt"
            input_docx.write_bytes(b"placeholder")
            profile.write_bytes(b"placeholder")
            request = GenerateSIRequest(
                input_path=input_docx,
                input_kind="word",
                output_path=root / "support_information.docx",
                insert_spectra_as="none",
                mnova_graphics_profile=profile,
            )

            issues = preflight_generate_request(request, mnova_finder=_raising_mnova_finder)

        self.assertTrue(issue_has_errors(issues))
        self.assertIn("PREFLIGHT_MNOVA_GRAPHICS_PROFILE_EXTENSION", {issue["code"] for issue in issues})

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

    def test_preflight_reports_missing_mnova_script(self) -> None:
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

            issues = preflight_generate_request(
                request,
                mnova_finder=_successful_mnova_finder,
                mnova_script_path=root / "missing.qs",
            )

        self.assertTrue(issue_has_errors(issues))
        self.assertIn("PREFLIGHT_MNOVA_SCRIPT_MISSING", {issue["code"] for issue in issues})

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
        issues = [
            {
                "code": "PREFLIGHT_INPUT_MISSING",
                "severity": "error",
                "message": "Missing",
                "path": "input.docx",
                "detail": "file is absent",
            }
        ]

        formatted = format_preflight_issues(issues)

        self.assertIn("[ERROR] PREFLIGHT_INPUT_MISSING: Missing (input.docx)", formatted)
        self.assertIn("Details: file is absent", formatted)


def _raising_mnova_finder(path):
    raise FileNotFoundError("not found")


def _successful_mnova_finder(path):
    return Path("C:/Program Files/MestReNova/MestReNova.exe")


if __name__ == "__main__":
    unittest.main()
