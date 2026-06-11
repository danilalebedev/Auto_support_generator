from __future__ import annotations

from pathlib import Path
import unittest

from si_generator.graph.nodes.spectra import route_nmr_processing
from si_generator.graph.state import GenerateSIRequest
from si_generator.models import Compound
from si_generator.workflows.generate_si import make_initial_generate_state


class GraphStateTests(unittest.TestCase):
    def test_initial_state_stores_request_artifacts_and_issues(self) -> None:
        request = GenerateSIRequest(
            input_path=Path("examples/test_input.docx"),
            input_kind="word",
            output_path=Path("output/support_information.docx"),
        )
        state = make_initial_generate_state(request)

        self.assertIs(state["request"], request)
        self.assertEqual(state["artifacts"], {})
        self.assertEqual(state["issues"], [])
        self.assertEqual(request.input_base_dir, Path("examples"))
        self.assertEqual(request.output_dir, Path("output"))

    def test_nmr_route_skips_when_disabled(self) -> None:
        request = GenerateSIRequest(
            input_path=Path("examples/test_input.docx"),
            input_kind="word",
            output_path=Path("output/support_information.docx"),
            no_extract_nmr=True,
        )

        self.assertEqual(route_nmr_processing({"request": request, "compounds": []}), "skip_mnova")

    def test_nmr_route_runs_when_spectra_are_assigned(self) -> None:
        request = GenerateSIRequest(
            input_path=Path("examples/test_input.docx"),
            input_kind="word",
            output_path=Path("output/support_information.docx"),
        )
        compound = Compound(number="2a", name="Test compound", h1_spectrum_path="2a/1H/fid")

        self.assertEqual(route_nmr_processing({"request": request, "compounds": [compound]}), "run_mnova")


if __name__ == "__main__":
    unittest.main()

