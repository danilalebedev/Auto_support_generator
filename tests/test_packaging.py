from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from si_generator.graph.compound_store import make_compound_store
from si_generator.graph.nodes.packaging import build_manifest, build_run_summary, collect_output_artifacts
from si_generator.graph.state import GenerateSIRequest
from si_generator.domain.bookmarks import bookmark_name_for_block_id
from si_generator.models import Compound


class PackagingTests(unittest.TestCase):
    def test_collects_product_output_artifacts_when_paths_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "input.docx"
            output_path = root / "output" / "support_information.docx"
            input_path.write_text("input", encoding="utf-8")
            output_path.parent.mkdir()
            output_path.write_text("docx placeholder", encoding="utf-8")
            (output_path.parent / "processed_spectra.zip").write_bytes(b"zip")
            for folder in ["processed_spectra", "processed_mnova", "mnova_reports", "logs"]:
                (output_path.parent / folder).mkdir()
            input_warnings = output_path.parent / "logs" / "input_warnings.txt"
            input_warnings.write_text("warning", encoding="utf-8")
            support_warnings = output_path.parent / "logs" / "support_warnings.txt"
            support_warnings.write_text("warning", encoding="utf-8")
            h1_image = output_path.parent / "processed_spectra" / "2a" / "2a_1H.png"
            h1_image.parent.mkdir(parents=True)

            structure_path = root / "structures" / "2a.cdx"
            compound = Compound(
                number="2a",
                name="Example",
                formula="C2H6O",
                color="white",
                state="solid",
                h1_nmr="1.23 (s, 3H)",
                hrms_found="47.0491",
                ir="IR (KBr, cm-1): 1700",
            )
            compound.structure_path = str(structure_path)
            compound.has_word_structure = True
            compound.h1_image_path = str(h1_image)
            compounds, order = make_compound_store([compound])
            state = {
                "run_id": "run",
                "request": GenerateSIRequest(input_path=input_path, input_kind="word", output_path=output_path),
                "output_path": output_path,
                "artifacts": {"input_warnings": str(input_warnings), "support_warnings": str(support_warnings)},
                "compounds": compounds,
                "order": order,
                "spectra_config": {"extract_nmr": False},
                "generation_config": {"check_support": False},
                "runtime_config": {"dry_run": False},
                "journal_profile": {"id": "default"},
                "issues": [{"code": "INPUT_WARNING", "severity": "warning", "message": "2a: missing HRMS", "compound_id": "cmp_001"}],
            }

            artifacts = collect_output_artifacts(state)
            manifest = build_manifest(state)
            run_summary = build_run_summary(state, manifest)

        self.assertIn("processed_spectra_zip", artifacts)
        self.assertIn("processed_spectra_dir", artifacts)
        self.assertIn("processed_mnova_dir", artifacts)
        self.assertIn("mnova_reports_dir", artifacts)
        self.assertIn("logs_dir", artifacts)
        self.assertEqual(manifest["output_paths"]["processed_spectra_zip"], artifacts["processed_spectra_zip"])
        self.assertEqual(manifest["output_paths"]["logs_dir"], artifacts["logs_dir"])
        self.assertEqual(manifest["output_paths"]["run_summary"], str(output_path.with_suffix(".run_summary.json")))
        self.assertEqual(manifest["artifacts"]["support_docx"], str(output_path))
        self.assertEqual(manifest["relative_paths"]["support_docx"], "support_information.docx")
        self.assertEqual(manifest["relative_paths"]["processed_spectra_zip"], "processed_spectra.zip")
        self.assertEqual(manifest["relative_paths"]["input_warnings"], str(Path("logs") / "input_warnings.txt"))
        self.assertEqual(manifest["relative_paths"]["support_warnings"], str(Path("logs") / "support_warnings.txt"))
        self.assertEqual(manifest["compounds"]["cmp_001"]["name"], "Example")
        self.assertEqual(manifest["compounds"]["cmp_001"]["formula"], "C2H6O")
        self.assertEqual(
            manifest["compounds"]["cmp_001"]["structure"],
            {"has_word_structure": True, "path": str(structure_path)},
        )
        self.assertEqual(
            manifest["compounds"]["cmp_001"]["analytical_blocks"],
            {
                "preparation": False,
                "yield": False,
                "physical_properties": True,
                "h1_nmr": True,
                "c13_nmr": False,
                "extra_nmr": False,
                "ir": True,
                "hrms": True,
                "elemental_analysis": False,
            },
        )
        self.assertEqual(manifest["compounds"]["cmp_001"]["relative_artifacts"]["h1_png"], str(Path("processed_spectra") / "2a" / "2a_1H.png"))
        self.assertEqual(manifest["configs"]["spectra"]["extract_nmr"], False)
        self.assertEqual(
            manifest["compounds"]["cmp_001"]["docx_bookmark"],
            bookmark_name_for_block_id("compound:cmp_001"),
        )
        self.assertEqual(run_summary["status"], "completed_with_warnings")
        self.assertEqual(run_summary["compound_count"], 1)
        self.assertEqual(run_summary["issue_counts"]["warning"], 1)
        self.assertEqual(run_summary["compound_issue_counts"], {"cmp_001": 1})
        self.assertEqual(run_summary["compounds"][0]["id"], "cmp_001")
        self.assertEqual(run_summary["compounds"][0]["issue_count"], 1)
        self.assertEqual(run_summary["compounds"][0]["issues"][0]["code"], "INPUT_WARNING")
        self.assertEqual(run_summary["output_paths"]["support_docx"], str(output_path))


if __name__ == "__main__":
    unittest.main()
