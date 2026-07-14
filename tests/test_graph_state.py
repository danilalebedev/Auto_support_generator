from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from si_generator.chemistry import calc_hrms_mz
from si_generator.domain.requests import CheckSIRequest as DomainCheckSIRequest
from si_generator.domain.requests import GenerateSIRequest as DomainGenerateSIRequest
from si_generator.domain.requests import PatchSIRequest as DomainPatchSIRequest
from si_generator.domain.types import Issue as DomainIssue
from si_generator.graph.compound_store import make_compound_store, ordered_compounds
from si_generator.graph.nodes.hrms import calculate_hrms_node
from si_generator.graph.nodes.nmr import apply_peak_picking_policy_node, parse_nmr_reports_node
from si_generator.graph.nodes.render import build_document_model_node
from si_generator.graph.nodes.settings import load_settings_node
from si_generator.graph.nodes.spectra import plan_nmr_processing_node, route_nmr_processing
from si_generator.graph.nodes.validation import validate_input_node, validate_support_node
from si_generator.graph.state import CheckSIRequest as GraphCheckSIRequest
from si_generator.graph.state import GenerateSIRequest
from si_generator.graph.state import PatchSIRequest as GraphPatchSIRequest
from si_generator.graph.state import Issue as GraphIssue
from si_generator.domain.compound import Compound
from si_generator.workflows.generate_si import make_initial_generate_state


class GraphStateTests(unittest.TestCase):
    def test_graph_state_reexports_domain_issue_type(self) -> None:
        self.assertIs(GraphIssue, DomainIssue)

    def test_graph_state_reexports_domain_request_types(self) -> None:
        self.assertIs(GenerateSIRequest, DomainGenerateSIRequest)
        self.assertIs(GraphCheckSIRequest, DomainCheckSIRequest)
        self.assertIs(GraphPatchSIRequest, DomainPatchSIRequest)

    def test_initial_state_stores_request_artifacts_and_issues(self) -> None:
        request = GenerateSIRequest(
            input_path=Path("examples/example_1/Compound_table.docx"),
            input_kind="word",
            output_path=Path("output/support_information.docx"),
        )
        state = make_initial_generate_state(request)

        self.assertRegex(state["run_id"], r"^\d{8}T\d{6}$")
        self.assertIs(state["request"], request)
        self.assertEqual(state["artifacts"], {})
        self.assertEqual(state["issues"], [])
        self.assertEqual(request.input_base_dir, Path("examples/example_1"))
        self.assertEqual(request.output_dir, Path("output"))

    def test_compound_store_assigns_ids_and_preserves_order(self) -> None:
        compounds, order = make_compound_store(
            [Compound(number="2a", name="A"), Compound(number="2b", name="B", id="custom")]
        )

        self.assertEqual(order, ["cmp_001", "custom"])
        self.assertEqual(compounds["cmp_001"].id, "cmp_001")
        self.assertEqual(compounds["cmp_001"].source_row, 1)
        self.assertEqual([compound.number for compound in ordered_compounds({"compounds": compounds, "order": order})], ["2a", "2b"])

    def test_settings_node_builds_generation_and_runtime_configs(self) -> None:
        request = GenerateSIRequest(
            input_path=Path("examples/example_1/Compound_table.docx"),
            input_kind="word",
            output_path=Path("output/support_information.docx"),
            mnova_exe=Path("C:/Tools/MestReNova.exe"),
            mnova_graphics_profile=Path("C:/Profiles/default.mngp"),
            mnova_graphics_profile_1h=Path("C:/Profiles/classic_1H.mngp"),
            mnova_graphics_profile_13c=Path("C:/Profiles/classic_13C.mngp"),
            no_extract_nmr=True,
            no_check_support=True,
            target_signal_height_fraction=0.72,
            peak_threshold_fraction_1h=0.08,
            peak_threshold_fraction_13c=0.04,
            x_range_ppm_1h=(-0.5, 11.5),
            x_range_ppm_13c=(-5.0, 205.0),
            baseline_mode="whittaker",
            baseline_apply_1h=True,
            baseline_apply_13c=False,
            baseline_poly_order=4,
            whittaker_lambda=300000,
            whittaker_asymmetry=0.003,
            calculate_elemental_analysis=True,
        )

        result = load_settings_node({"request": request})

        self.assertFalse(result["spectra_config"]["extract_nmr"])
        self.assertEqual(result["spectra_config"]["insert_spectra_as"], "png")
        self.assertEqual(result["spectra_config"]["target_signal_height_fraction"], 0.72)
        self.assertEqual(result["spectra_config"]["peak_threshold_fraction_1h"], 0.08)
        self.assertEqual(result["spectra_config"]["peak_threshold_fraction_13c"], 0.04)
        self.assertEqual(result["spectra_config"]["x_ranges_ppm"]["1H"], (-0.5, 11.5))
        self.assertEqual(result["spectra_config"]["x_ranges_ppm"]["13C"], (-5.0, 205.0))
        self.assertEqual(result["spectra_config"]["baseline_mode"], "whittaker")
        self.assertTrue(result["spectra_config"]["baseline_apply_1h"])
        self.assertFalse(result["spectra_config"]["baseline_apply_13c"])
        self.assertEqual(result["spectra_config"]["baseline_poly_order"], 4)
        self.assertEqual(result["spectra_config"]["whittaker_lambda"], 300000.0)
        self.assertEqual(result["spectra_config"]["whittaker_asymmetry"], 0.003)
        self.assertEqual(result["spectra_config"]["mnova_executable_path"], "C:\\Tools\\MestReNova.exe")
        self.assertEqual(result["spectra_config"]["mnova_graphics_profile_path"], "C:\\Profiles\\default.mngp")
        self.assertEqual(result["spectra_config"]["mnova_graphics_profile_1h_path"], "C:\\Profiles\\classic_1H.mngp")
        self.assertEqual(result["spectra_config"]["mnova_graphics_profile_13c_path"], "C:\\Profiles\\classic_13C.mngp")
        self.assertFalse(result["generation_config"]["check_support"])
        self.assertTrue(result["generation_config"]["calculate_elemental_analysis"])
        self.assertTrue(result["generation_config"]["include_ir"])
        self.assertTrue(result["generation_config"]["include_elemental_analysis"])
        self.assertFalse(result["runtime_config"]["dry_run"])

    def test_settings_node_enables_references_when_reference_file_is_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            references_path = Path(tmp) / "references.yml"
            references_path.write_text("references:\norder: []\n", encoding="utf-8")
            request = GenerateSIRequest(
                input_path=Path("examples/example_1/Compound_table.docx"),
                input_kind="word",
                output_path=Path("output/support_information.docx"),
                references_path=references_path,
            )

            result = load_settings_node({"request": request})

        self.assertTrue(result["generation_config"]["include_ir"])
        self.assertTrue(result["generation_config"]["include_elemental_analysis"])
        self.assertFalse(result["generation_config"]["calculate_elemental_analysis"])
        self.assertTrue(result["generation_config"]["include_references"])

    def test_document_model_node_honors_generation_visibility_flags(self) -> None:
        compound = Compound(
            number="2a",
            name="Example",
            formula="C17H11FN2O3",
            ir="IR (ATR, cm-1): 3038, 2957.",
            elemental_analysis={"found": "C, 66.03; H, 3.55; N, 8.92"},
            references=["ref1"],
        )
        compounds, order = make_compound_store([compound])
        store = {
            "references": {"ref1": {"key": "ref1", "authors": ["Doe J."], "title": "Reference"}},
            "order": ["ref1"],
        }

        result = build_document_model_node(
            {
                "compounds": compounds,
                "order": order,
                "reference_store": store,
                "spectra_config": {"insert_spectra_as": "none"},
                "generation_config": {
                    "include_ir": False,
                    "include_elemental_analysis": False,
                    "include_references": False,
                },
            }
        )

        model = result["document_model"]
        rendered_compound = model["sections"][0]["blocks"][0]["content"]
        self.assertEqual([section["id"] for section in model["sections"]], ["compound_descriptions"])
        self.assertEqual(rendered_compound.ir, "")
        self.assertEqual(rendered_compound.elemental_analysis, {})
        self.assertEqual(compounds["cmp_001"].ir, "IR (ATR, cm-1): 3038, 2957.")
        self.assertTrue(compounds["cmp_001"].elemental_analysis)

    def test_nmr_route_skips_when_disabled(self) -> None:
        request = GenerateSIRequest(
            input_path=Path("examples/example_1/Compound_table.docx"),
            input_kind="word",
            output_path=Path("output/support_information.docx"),
            no_extract_nmr=True,
        )

        self.assertEqual(
            route_nmr_processing({"request": request, "compounds": {}, "order": [], "spectra_config": {"extract_nmr": False}}),
            "skip_mnova",
        )

    def test_nmr_route_runs_when_spectra_are_assigned(self) -> None:
        request = GenerateSIRequest(
            input_path=Path("examples/example_1/Compound_table.docx"),
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

        result = plan_nmr_processing_node(
            {
                "compounds": compounds,
                "order": order,
                "spectra_config": {
                    "target_signal_height_fraction": 0.65,
                    "peak_picking": "minimal",
                    "ignore_regions_ppm": {"1H": [(7.20, 7.30)]},
                },
            }
        )
        plan = result["spectra_plan"]["cmp_001"]

        self.assertEqual(plan["1H"]["x_range_ppm"], (-1.0, 12.0))
        self.assertEqual(plan["13C"]["x_range_ppm"], (-10.0, 210.0))
        self.assertEqual(plan["1H"]["target_signal_height_fraction"], 0.65)
        self.assertEqual(plan["13C"]["peak_picking"], "minimal")
        self.assertEqual(plan["1H"]["ignore_regions_ppm"], [(7.20, 7.30)])

    def test_hrms_node_calculates_before_rendering(self) -> None:
        request = GenerateSIRequest(
            input_path=Path("examples/example_1/Compound_table.docx"),
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
        self.assertEqual(updated.hrms["calculated_mz"], 272.9921)
        self.assertEqual(updated.hrms["isotope_labels"], {"Br": 79})
        self.assertEqual(result["issues"], [])

    def test_hrms_node_accepts_structured_block_found_text_and_adduct(self) -> None:
        found = f"{calc_hrms_mz('C2H4O2', '[M+Na]+'):.4f}"
        compound = Compound(
            number="2a",
            name="Test compound",
            formula="C2H4O2",
            hrms={"adduct": "[M+Na]+", "found_text": found},
        )
        compounds, order = make_compound_store([compound])

        result = calculate_hrms_node({"compounds": compounds, "order": order, "issues": []})

        updated = result["compounds"]["cmp_001"]
        self.assertEqual(updated.hrms["adduct"], "[M+Na]+")
        self.assertEqual(updated.hrms["found_text"], found)
        self.assertEqual(updated.hrms_found, found)
        self.assertEqual(updated.hrms["ion_formula"], "C2H4O2Na+")

    def test_nmr_nodes_parse_text_and_apply_policy(self) -> None:
        compound = Compound(
            number="2a",
            name="Test compound",
            h1_nmr="δ = 8.07 (d, J = 15.8 Hz, 1H, CH), 4.59 (s, 2H, CH2Br).",
            h1_conditions="CDCl3, 600 MHz",
        )
        compounds, order = make_compound_store([compound])
        state = {
            "compounds": compounds,
            "order": order,
            "spectra_plan": {"cmp_001": {"1H": {"nucleus": "1H", "peak_picking": "minimal"}}},
        }

        parse_nmr_reports_node(state)
        result = apply_peak_picking_policy_node(state)

        spectrum = result["compounds"]["cmp_001"].nmr_spectra["1H"]
        self.assertEqual(spectrum["conditions"], "CDCl3, 600 MHz")
        self.assertEqual(spectrum["signals"][0]["shift"], 8.07)
        self.assertEqual(spectrum["peak_picking"], "minimal")

    def test_input_validation_writes_warning_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            request = GenerateSIRequest(
                input_path=Path("examples/example_1/Compound_table.docx"),
                input_kind="csv",
                output_path=Path(tmp) / "support_information.docx",
            )
            compound = Compound(number="2a", name="Compound 2a")
            compounds, order = make_compound_store([compound])

            result = validate_input_node({"request": request, "compounds": compounds, "order": order, "issues": [], "artifacts": {}})

            warning_path = Path(result["artifacts"]["input_warnings"])
            text = warning_path.read_text(encoding="utf-8")

        self.assertTrue(any(issue["code"] == "INPUT_WARNING" for issue in result["issues"]))
        self.assertTrue(
            any(issue["code"] == "INPUT_WARNING" and issue.get("compound_id") == "cmp_001" for issue in result["issues"])
        )
        self.assertIn("2a: missing generated/name field", text)

    def test_support_validation_writes_warning_artifact_and_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            request = GenerateSIRequest(
                input_path=Path("examples/example_1/Compound_table.docx"),
                input_kind="word",
                output_path=Path(tmp) / "support_information.docx",
            )
            compound = Compound(
                number="2a",
                name="Test compound",
                formula="C2H6O",
                h1_nmr="delta = 3.70 (q, J = 7.0 Hz, 2H).",
                c13_nmr="delta = 58.0.",
                hrms_found="999.0000",
            )
            compounds, order = make_compound_store([compound])

            result = validate_support_node(
                {
                    "request": request,
                    "compounds": compounds,
                    "order": order,
                    "issues": [],
                    "artifacts": {},
                    "generation_config": {"check_support": True},
                }
            )

            warning_path = Path(result["artifacts"]["support_warnings"])
            text = warning_path.read_text(encoding="utf-8")

        issue_codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("NMR_H_COUNT_MISMATCH", issue_codes)
        self.assertIn("HRMS_MISMATCH", issue_codes)
        self.assertIn("2a: H expected 6, found 2", text)
        self.assertIn("HRMS calcd", text)


if __name__ == "__main__":
    unittest.main()

