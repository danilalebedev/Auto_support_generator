from __future__ import annotations

from pathlib import Path
import unittest

from si_generator.graph.compound_store import make_compound_store, ordered_compounds
from si_generator.graph.nodes.hrms import calculate_hrms_node
from si_generator.graph.nodes.spectra import plan_nmr_processing_node, route_nmr_processing
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

        self.assertRegex(state["run_id"], r"^\d{8}T\d{6}$")
        self.assertIs(state["request"], request)
        self.assertEqual(state["artifacts"], {})
        self.assertEqual(state["issues"], [])
        self.assertEqual(request.input_base_dir, Path("examples"))
        self.assertEqual(request.output_dir, Path("output"))

    def test_compound_store_assigns_ids_and_preserves_order(self) -> None:
        compounds, order = make_compound_store(
            [Compound(number="2a", name="A"), Compound(number="2b", name="B", id="custom")]
        )

        self.assertEqual(order, ["cmp_001", "custom"])
        self.assertEqual(compounds["cmp_001"].id, "cmp_001")
        self.assertEqual(compounds["cmp_001"].source_row, 1)
        self.assertEqual([compound.number for compound in ordered_compounds({"compounds": compounds, "order": order})], ["2a", "2b"])

    def test_nmr_route_skips_when_disabled(self) -> None:
        request = GenerateSIRequest(
            input_path=Path("examples/test_input.docx"),
            input_kind="word",
            output_path=Path("output/support_information.docx"),
            no_extract_nmr=True,
        )

        self.assertEqual(route_nmr_processing({"request": request, "compounds": {}, "order": []}), "skip_mnova")

    def test_nmr_route_runs_when_spectra_are_assigned(self) -> None:
        request = GenerateSIRequest(
            input_path=Path("examples/test_input.docx"),
            input_kind="word",
            output_path=Path("output/support_information.docx"),
        )
        compound = Compound(number="2a", name="Test compound", h1_spectrum_path="2a/1H/fid")
        compounds, order = make_compound_store([compound])

        self.assertEqual(route_nmr_processing({"request": request, "compounds": compounds, "order": order}), "run_mnova")

    def test_nmr_plan_adds_default_render_specs(self) -> None:
        compound = Compound(
            number="2a",
            name="Test compound",
            h1_spectrum_path="2a/1H/fid",
            c13_spectrum_path="2a/13C/fid",
        )
        compounds, order = make_compound_store([compound])

        result = plan_nmr_processing_node({"compounds": compounds, "order": order})
        plan = result["spectra_plan"]["cmp_001"]

        self.assertEqual(plan["1H"]["x_range_ppm"], (-1.0, 12.0))
        self.assertEqual(plan["13C"]["x_range_ppm"], (-10.0, 210.0))
        self.assertEqual(plan["1H"]["target_signal_height_fraction"], 0.80)
        self.assertEqual(plan["13C"]["peak_picking"], "normal")

    def test_hrms_node_calculates_before_rendering(self) -> None:
        request = GenerateSIRequest(
            input_path=Path("examples/test_input.docx"),
            input_kind="word",
            output_path=Path("output/support_information.docx"),
        )
        compound = Compound(
            number="2a",
            name="Test compound",
            formula="C11H10BrFO2",
            hrms_found="272.9921",
            hrms_adduct="[M+H]+",
        )
        compounds, order = make_compound_store([compound])

        result = calculate_hrms_node({"request": request, "compounds": compounds, "order": order, "issues": []})

        updated = result["compounds"]["cmp_001"]
        self.assertEqual(updated.hrms_calculated, 272.9921)
        self.assertEqual(updated.hrms_ion_formula, "C11H11BrFO2+")
        self.assertEqual(result["issues"], [])


if __name__ == "__main__":
    unittest.main()

