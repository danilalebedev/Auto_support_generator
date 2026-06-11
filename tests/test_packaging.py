from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from si_generator.graph.compound_store import make_compound_store
from si_generator.graph.nodes.packaging import build_manifest, collect_output_artifacts
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

            compound = Compound(number="2a", name="Example")
            compounds, order = make_compound_store([compound])
            state = {
                "run_id": "run",
                "request": GenerateSIRequest(input_path=input_path, input_kind="word", output_path=output_path),
                "output_path": output_path,
                "artifacts": {},
                "compounds": compounds,
                "order": order,
                "spectra_config": {"extract_nmr": False},
                "generation_config": {"check_support": False},
                "runtime_config": {"dry_run": False},
                "journal_profile": {"id": "default"},
            }

            artifacts = collect_output_artifacts(state)
            manifest = build_manifest(state)

        self.assertIn("processed_spectra_zip", artifacts)
        self.assertIn("processed_spectra_dir", artifacts)
        self.assertIn("processed_mnova_dir", artifacts)
        self.assertIn("mnova_reports_dir", artifacts)
        self.assertIn("logs_dir", artifacts)
        self.assertEqual(manifest["output_paths"]["processed_spectra_zip"], artifacts["processed_spectra_zip"])
        self.assertEqual(manifest["output_paths"]["logs_dir"], artifacts["logs_dir"])
        self.assertEqual(manifest["artifacts"]["support_docx"], str(output_path))
        self.assertEqual(manifest["configs"]["spectra"]["extract_nmr"], False)
        self.assertEqual(
            manifest["compounds"]["cmp_001"]["docx_bookmark"],
            bookmark_name_for_block_id("compound:cmp_001"),
        )


if __name__ == "__main__":
    unittest.main()
