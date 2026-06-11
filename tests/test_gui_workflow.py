from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from si_generator.gui import (
    _build_check_summary,
    _build_check_request,
    _build_generate_request,
    _build_patch_request,
    _build_patch_summary,
    _build_result_summary,
    _dialog_initialdir,
    _example_field_updates,
    _existing_result_path,
    _mousewheel_units,
    _report_overview,
)
from si_generator.graph.state import CheckSIRequest


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

    def test_rejects_directory_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            with self.assertRaisesRegex(ValueError, "must be a file"):
                _build_generate_request(
                    input_kind="word",
                    input_path_text=str(root),
                    output_docx_text=str(root / "support_information.docx"),
                )

    def test_rejects_wrong_optional_file_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            table = root / "input.docx"
            spectra = root / "spectra.txt"
            table.write_text("placeholder", encoding="utf-8")
            spectra.write_text("placeholder", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Spectra zip must have one of these extensions"):
                _build_generate_request(
                    input_kind="word",
                    input_path_text=str(table),
                    output_docx_text=str(root / "support_information.docx"),
                    spectra_zip_text=str(spectra),
                )

    def test_rejects_directory_mnova_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            table = root / "input.docx"
            table.write_text("placeholder", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "MestReNova .exe must be a file"):
                _build_generate_request(
                    input_kind="word",
                    input_path_text=str(table),
                    output_docx_text=str(root / "support_information.docx"),
                    mnova_exe_text=str(root),
                )

    def test_builds_result_summary_from_graph_state_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "support_information.docx"
            input_docx = root / "input.docx"
            package = root / "processed_spectra.zip"
            processed_mnova = root / "processed_mnova"
            mnova_reports = root / "mnova_reports"
            logs = root / "logs"
            manifest = root / "support_information.manifest.json"
            run_summary = root / "support_information.run_summary.json"
            warnings = logs / "input_warnings.txt"
            support_warnings = logs / "support_warnings.txt"
            processed_mnova.mkdir()
            mnova_reports.mkdir()
            logs.mkdir()
            input_docx.write_text("placeholder", encoding="utf-8")
            run_summary.write_text(
                '{"status":"completed_with_warnings","compound_count":2,'
                '"issue_counts":{"warning":3},'
                '"issue_code_counts":{"HRMS_MISMATCH":2,"NMR_H_COUNT_MISMATCH":1}}',
                encoding="utf-8",
            )
            state = {
                "request": _build_generate_request(
                    input_kind="word",
                    input_path_text=str(input_docx),
                    output_docx_text=str(output),
                ),
                "output_path": output,
                "artifacts": {
                    "support_docx": str(output),
                    "processed_spectra_zip": str(package),
                    "processed_mnova_dir": str(processed_mnova),
                    "mnova_reports_dir": str(mnova_reports),
                    "logs_dir": str(logs),
                    "manifest": str(manifest),
                    "run_summary": str(run_summary),
                    "input_warnings": str(warnings),
                    "support_warnings": str(support_warnings),
                },
            }

            summary = _build_result_summary(state)

        self.assertEqual(summary["support_docx"], str(output.resolve()))
        self.assertEqual(summary["processed_spectra_zip"], str(package.resolve()))
        self.assertEqual(summary["processed_mnova_dir"], str(processed_mnova.resolve()))
        self.assertEqual(summary["mnova_reports_dir"], str(mnova_reports.resolve()))
        self.assertEqual(summary["logs_dir"], str(logs.resolve()))
        self.assertEqual(summary["manifest"], str(manifest.resolve()))
        self.assertEqual(summary["run_summary"], str(run_summary.resolve()))
        self.assertEqual(summary["input_warnings"], str(warnings.resolve()))
        self.assertEqual(summary["support_warnings"], str(support_warnings.resolve()))
        self.assertEqual(
            summary["overview"],
            "Status: completed with warnings | Compounds: 2 | Warnings: 3 | Top issues: HRMS_MISMATCH x2, NMR_H_COUNT_MISMATCH x1",
        )

    def test_builds_check_request_from_manifest_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "support_information.manifest.json"
            manifest.write_text("{}", encoding="utf-8")

            request = _build_check_request(str(manifest))

        self.assertEqual(request.manifest_path, manifest)

    def test_builds_check_summary_from_report_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "support_information.manifest.json"
            report = root / "support_information.check_report.json"
            manifest.write_text("{}", encoding="utf-8")
            report.write_text('{"status":"pass","issue_counts":{}}', encoding="utf-8")

            summary = _build_check_summary(
                {"artifacts": {"manifest": str(manifest), "check_report": str(report)}},
                CheckSIRequest(manifest_path=manifest),
            )

        self.assertEqual(summary["manifest"], str(manifest.resolve()))
        self.assertEqual(summary["run_summary"], str(report.resolve()))
        self.assertEqual(summary["overview"], "Status: pass | Issues: 0")

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
            report = root / "patched.patch_report.json"
            report.write_text('{"status":"fail","issue_counts":{"error":1,"warning":2}}', encoding="utf-8")

            summary = _build_patch_summary(
                {
                    "artifacts": {
                        "support_docx": str(support),
                        "manifest": str(manifest),
                        "patch_report": str(report),
                    }
                }
            )

        self.assertEqual(summary["support_docx"], str(support.resolve()))
        self.assertEqual(summary["manifest"], str(manifest.resolve()))
        self.assertEqual(summary["run_summary"], str(report.resolve()))
        self.assertEqual(summary["overview"], "Status: fail | Errors: 1 | Warnings: 2")

    def test_report_overview_ignores_missing_or_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "broken.json"
            report.write_text("{", encoding="utf-8")

            invalid_result = _report_overview(str(report))
            missing_result = _report_overview(str(Path(tmp) / "missing.json"))

        self.assertEqual(invalid_result, "")
        self.assertEqual(missing_result, "")

    def test_existing_result_path_returns_resolved_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "support_information.docx"
            path.write_text("placeholder", encoding="utf-8")

            result = _existing_result_path(str(path), "Support .docx")

        self.assertEqual(result, path.resolve())

    def test_existing_result_path_rejects_empty_or_missing_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "not been generated"):
            _existing_result_path("", "Manifest")
        with self.assertRaisesRegex(ValueError, "does not exist"):
            _existing_result_path("missing.manifest.json", "Manifest")

    def test_dialog_initialdir_uses_existing_file_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "input.docx"
            file_path.write_text("placeholder", encoding="utf-8")

            result = _dialog_initialdir(str(file_path))

        self.assertEqual(result, str(file_path.parent.resolve()))

    def test_dialog_initialdir_uses_existing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = _dialog_initialdir(Path(tmp))

        self.assertEqual(result, str(Path(tmp).resolve()))

    def test_dialog_initialdir_uses_future_file_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            future_path = Path(tmp) / "support_information.docx"

            result = _dialog_initialdir(str(future_path))

        self.assertEqual(result, str(Path(tmp).resolve()))

    def test_dialog_initialdir_falls_back_to_next_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fallback = Path(tmp) / "input.docx"
            fallback.write_text("placeholder", encoding="utf-8")

            result = _dialog_initialdir(Path(tmp) / "missing" / "out.docx", fallback)

        self.assertEqual(result, str(fallback.parent.resolve()))

    def test_example_field_updates_clear_project_specific_paths(self) -> None:
        updates = _example_field_updates(
            Path("examples/test_input.docx"),
            Path("examples/test_input.zip"),
            Path("output/support_information.docx"),
        )

        self.assertEqual(updates["input_kind"], "word")
        self.assertEqual(updates["input_path"], str(Path("examples/test_input.docx")))
        self.assertEqual(updates["spectra_zip"], str(Path("examples/test_input.zip")))
        self.assertEqual(updates["output_docx"], str(Path("output/support_information.docx")))
        self.assertEqual(updates["template_docx"], "")
        self.assertEqual(updates["style_config"], "")
        self.assertEqual(updates["journal_profile"], "")
        self.assertEqual(updates["references_file"], "")
        self.assertEqual(updates["existing_manifest"], "")
        self.assertEqual(updates["patch_renumber"], "")
        self.assertNotIn("mnova_exe", updates)

    def test_mousewheel_units_scroll_in_platform_direction(self) -> None:
        self.assertEqual(_mousewheel_units(120), -1)
        self.assertEqual(_mousewheel_units(-120), 1)
        self.assertEqual(_mousewheel_units(0), 0)


if __name__ == "__main__":
    unittest.main()
