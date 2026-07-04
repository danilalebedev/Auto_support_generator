from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from si_generator.cli import _build_parser
from si_generator.spectra_zip import prepare_spectra_source
from si_generator.workflows.generate_si import request_from_args


class SpectraSourceTests(unittest.TestCase):
    def test_prepare_spectra_source_accepts_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spectra_folder = root / "spectra"
            spectra_folder.mkdir()

            prepared = prepare_spectra_source(spectra_folder, root / "work")

        self.assertEqual(prepared, spectra_folder.resolve())

    def test_prepare_spectra_source_accepts_zip_and_unwraps_single_container(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spectra_zip = root / "test_input.zip"
            with zipfile.ZipFile(spectra_zip, "w") as archive:
                archive.writestr("test_input/2a/1H/fid", "fid")
                archive.writestr("test_input/2a/1H/acqus", "##$NUC1= <1H>")

            prepared = prepare_spectra_source(spectra_zip, root / "work")
            self.assertEqual(prepared.name, "test_input")
            self.assertTrue((prepared / "2a" / "1H" / "fid").exists())

    def test_prepare_spectra_source_rejects_zip_slip_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spectra_zip = root / "unsafe.zip"
            with zipfile.ZipFile(spectra_zip, "w") as archive:
                archive.writestr("../evil.txt", "owned")

            with self.assertRaisesRegex(ValueError, "Unsafe path in zip"):
                prepare_spectra_source(spectra_zip, root / "work")

            self.assertFalse((root / "evil.txt").exists())

    def test_prepare_spectra_source_rejects_windows_zip_slip_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spectra_zip = root / "unsafe_windows.zip"
            with zipfile.ZipFile(spectra_zip, "w") as archive:
                archive.writestr("..\\evil.txt", "owned")

            with self.assertRaisesRegex(ValueError, "Unsafe path in zip"):
                prepare_spectra_source(spectra_zip, root / "work")

            self.assertFalse((root / "evil.txt").exists())

    def test_prepare_spectra_source_rejects_zip_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spectra_zip = root / "unsafe_symlink.zip"
            symlink = zipfile.ZipInfo("test_input/2a/link")
            symlink.create_system = 3
            symlink.external_attr = 0o120777 << 16
            with zipfile.ZipFile(spectra_zip, "w") as archive:
                archive.writestr(symlink, "../outside")

            with self.assertRaisesRegex(ValueError, "Unsafe symlink in zip"):
                prepare_spectra_source(spectra_zip, root / "work")

    def test_prepare_spectra_source_rejects_too_many_zip_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spectra_zip = root / "too_many.zip"
            with zipfile.ZipFile(spectra_zip, "w") as archive:
                archive.writestr("test_input/2a/1H/fid", "fid")
                archive.writestr("test_input/2a/1H/acqus", "##$NUC1= <1H>")

            with self.assertRaisesRegex(ValueError, "too many entries"):
                prepare_spectra_source(spectra_zip, root / "work", max_members=1)

    def test_prepare_spectra_source_rejects_too_large_zip_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spectra_zip = root / "too_large.zip"
            with zipfile.ZipFile(spectra_zip, "w") as archive:
                archive.writestr("test_input/2a/1H/fid", "fid")

            with self.assertRaisesRegex(ValueError, "too large after extraction"):
                prepare_spectra_source(spectra_zip, root / "work", max_uncompressed_bytes=1)

    def test_cli_accepts_spectra_source_folder(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(
            [
                "--word-input",
                "input.docx",
                "--output",
                "support.docx",
                "--spectra-source",
                "spectra-folder",
            ]
        )

        request = request_from_args(args)

        self.assertEqual(request.spectra_source, Path("spectra-folder"))
        self.assertIsNone(request.spectra_zip)
        self.assertEqual(request.resolved_spectra_source, Path("spectra-folder"))

    def test_cli_keeps_spectra_zip_as_deprecated_alias(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(
            [
                "--word-input",
                "input.docx",
                "--output",
                "support.docx",
                "--spectra-zip",
                "spectra.zip",
            ]
        )

        request = request_from_args(args)

        self.assertIsNone(request.spectra_source)
        self.assertEqual(request.spectra_zip, Path("spectra.zip"))
        self.assertEqual(request.resolved_spectra_source, Path("spectra.zip"))

    def test_spectra_source_takes_precedence_over_deprecated_zip_alias(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(
            [
                "--word-input",
                "input.docx",
                "--output",
                "support.docx",
                "--spectra-source",
                "spectra-folder",
                "--spectra-zip",
                "legacy.zip",
            ]
        )

        request = request_from_args(args)

        self.assertEqual(request.spectra_source, Path("spectra-folder"))
        self.assertEqual(request.spectra_zip, Path("legacy.zip"))
        self.assertEqual(request.resolved_spectra_source, Path("spectra-folder"))


if __name__ == "__main__":
    unittest.main()
