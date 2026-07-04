from __future__ import annotations

import json
import unittest
from pathlib import Path

from si_generator.domain.spectra_config import build_spectra_config, build_spectrum_render_spec
from si_generator.graph.compound_store import make_compound_store
from si_generator.graph.nodes.spectra import plan_nmr_processing_node
from si_generator.mnova import _format_task_line, _render_spec_arg
from si_generator.models import Compound


REPO_ROOT = Path(__file__).resolve().parents[1]
QS_SCRIPT = REPO_ROOT / "src" / "si_generator" / "resources" / "scripts" / "extract_nmr_report.qs"


class MnovaRenderSpecTests(unittest.TestCase):
    def test_task_line_serializes_render_spec_as_sixth_tsv_column(self) -> None:
        render_spec = {
            "nucleus": "1H",
            "x_range_ppm": (-1.0, 12.0),
            "target_signal_height_fraction": 0.72,
            "peak_threshold_fraction": 0.08,
            "ignore_regions_ppm": [(7.20, 7.35)],
            "peak_picking": "minimal",
            "baseline_mode": "whittaker",
            "baseline_apply": True,
            "baseline_poly_order": 5,
            "whittaker_lambda": 200000,
            "whittaker_asymmetry": 0.002,
        }

        line = _format_task_line(
            "2a",
            "1H",
            "C:/ascii/input/fid",
            image_path="C:/ascii/out/2a_1H.png",
            mnova_path="C:/ascii/out/2a.mnova",
            render_spec=render_spec,
            single_mnova_path="C:/ascii/out/2a_1H.mnova",
        )
        parts = line.split("\t")

        self.assertEqual(len(parts), 7)
        parsed = json.loads(parts[5])
        self.assertEqual(parsed["target_signal_height_fraction"], 0.72)
        self.assertEqual(parsed["peak_threshold_fraction"], 0.08)
        self.assertEqual(parsed["ignore_regions_ppm"], [[7.2, 7.35]])
        self.assertEqual(parsed["peak_picking"], "minimal")
        self.assertEqual(parsed["baseline_mode"], "whittaker")
        self.assertTrue(parsed["baseline_apply"])
        self.assertEqual(parsed["baseline_poly_order"], 5)
        self.assertEqual(parsed["whittaker_lambda"], 200000)
        self.assertEqual(parsed["whittaker_asymmetry"], 0.002)
        self.assertEqual(parts[6], "C:/ascii/out/2a_1H.mnova")

    def test_empty_render_spec_is_empty_json_object(self) -> None:
        self.assertEqual(_render_spec_arg(None), "{}")
        self.assertEqual(_render_spec_arg({}), "{}")

    def test_plan_nmr_processing_carries_custom_render_policy(self) -> None:
        compound = Compound(id="cmp_001", number="2a", name="Example", h1_spectrum_path="1/fid", c13_spectrum_path="2/fid")
        compounds, order = make_compound_store([compound])
        state = {
            "compounds": compounds,
            "order": order,
            "spectra_config": {
                "target_signal_height_fraction": 0.7,
                "peak_threshold_fraction_1h": 0.075,
                "peak_threshold_fraction_13c": 0.04,
                "peak_picking": "dense",
                "ignore_regions_ppm": {"1H": [(7.2, 7.4)], "13C": [(76.0, 78.2)]},
            },
        }

        result = plan_nmr_processing_node(state)

        h1 = result["spectra_plan"]["cmp_001"]["1H"]
        c13 = result["spectra_plan"]["cmp_001"]["13C"]
        self.assertEqual(h1["target_signal_height_fraction"], 0.7)
        self.assertEqual(h1["peak_threshold_fraction"], 0.075)
        self.assertEqual(h1["peak_picking"], "dense")
        self.assertEqual(h1["ignore_regions_ppm"], [(7.2, 7.4)])
        self.assertEqual(c13["peak_threshold_fraction"], 0.04)
        self.assertEqual(c13["ignore_regions_ppm"], [(76.0, 78.2)])

    def test_baseline_render_spec_defaults_and_whittaker_settings(self) -> None:
        default_config = build_spectra_config()

        h1 = build_spectrum_render_spec("1H", default_config)
        c13 = build_spectrum_render_spec("13C", default_config)

        self.assertEqual(h1["baseline_mode"], "auto")
        self.assertFalse(h1["baseline_apply"])
        self.assertEqual(c13["baseline_mode"], "auto")
        self.assertTrue(c13["baseline_apply"])
        self.assertEqual(c13["baseline_poly_order"], 3)
        self.assertEqual(c13["whittaker_lambda"], 100000.0)
        self.assertEqual(c13["whittaker_asymmetry"], 0.001)

        whittaker_config = build_spectra_config(
            baseline_mode="whittaker",
            baseline_apply_1h=True,
            baseline_apply_13c=False,
            whittaker_lambda=250000,
            whittaker_asymmetry=0.004,
        )

        h1_whittaker = build_spectrum_render_spec("1H", whittaker_config)
        c13_whittaker = build_spectrum_render_spec("13C", whittaker_config)

        self.assertEqual(h1_whittaker["baseline_mode"], "whittaker")
        self.assertTrue(h1_whittaker["baseline_apply"])
        self.assertEqual(h1_whittaker["whittaker_lambda"], 250000.0)
        self.assertEqual(h1_whittaker["whittaker_asymmetry"], 0.004)
        self.assertFalse(c13_whittaker["baseline_apply"])

    def test_mnova_qs_consumes_render_spec_column(self) -> None:
        script = QS_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("var renderSpec = parts.length >= 6 ? _parseRenderSpec(parts[5]) : {};", script)
        self.assertIn("var singleMnovaPath = parts.length >= 7 ? parts[6] : \"\";", script)
        self.assertIn("_saveSingleProcessedMnovaFile(compound, nucleus, spectrum, singleMnovaPath", script)
        self.assertIn("x_range_ppm", script)
        self.assertIn("_targetSignalHeightFraction(renderSpec", script)
        self.assertIn("_peakThresholdFraction(nucleus, renderSpec", script)
        self.assertIn("_filterMultipletReportByPeakThreshold", script)
        self.assertIn("_isIgnoredByRenderSpec(delta, renderSpec", script)
        self.assertIn("_prepareSpectrumForExport(spectrum, nucleus, tasks[i].renderSpec || {})", script)

    def test_mnova_qs_uses_render_spec_for_baseline_processing(self) -> None:
        script = QS_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function _baselineMode(renderSpec)", script)
        self.assertIn("function _baselineApply(nucleus, renderSpec)", script)
        self.assertIn("return nucleus === \"13C\";", script)
        self.assertIn("BC.algorithm\", \"Whittaker", script)
        self.assertIn("renderSpec.whittaker_lambda", script)
        self.assertIn("renderSpec.whittaker_asymmetry", script)
        self.assertIn("WARNING baseline parameter", script)
        self.assertIn("_processForReport(spectrum, nucleus, undefined, true, false, renderSpec, statusPath)", script)
        self.assertIn("_processForReport(spectrum, nucleus, 1, false, true, renderSpec, statusPath)", script)


if __name__ == "__main__":
    unittest.main()
