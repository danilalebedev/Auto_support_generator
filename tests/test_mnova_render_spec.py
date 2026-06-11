from __future__ import annotations

import json
import unittest
from pathlib import Path

from si_generator.graph.compound_store import make_compound_store
from si_generator.graph.nodes.spectra import plan_nmr_processing_node
from si_generator.mnova import _format_task_line, _render_spec_arg
from si_generator.models import Compound


REPO_ROOT = Path(__file__).resolve().parents[1]


class MnovaRenderSpecTests(unittest.TestCase):
    def test_task_line_serializes_render_spec_as_sixth_tsv_column(self) -> None:
        render_spec = {
            "nucleus": "1H",
            "x_range_ppm": (-1.0, 12.0),
            "target_signal_height_fraction": 0.72,
            "peak_threshold_fraction": 0.08,
            "ignore_regions_ppm": [(7.20, 7.35)],
            "peak_picking": "minimal",
        }

        line = _format_task_line(
            "2a",
            "1H",
            "C:/ascii/input/fid",
            image_path="C:/ascii/out/2a_1H.png",
            mnova_path="C:/ascii/out/2a.mnova",
            render_spec=render_spec,
        )
        parts = line.split("\t")

        self.assertEqual(len(parts), 6)
        parsed = json.loads(parts[5])
        self.assertEqual(parsed["target_signal_height_fraction"], 0.72)
        self.assertEqual(parsed["peak_threshold_fraction"], 0.08)
        self.assertEqual(parsed["ignore_regions_ppm"], [[7.2, 7.35]])
        self.assertEqual(parsed["peak_picking"], "minimal")

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

    def test_mnova_qs_consumes_render_spec_column(self) -> None:
        script = (REPO_ROOT / "scripts" / "extract_nmr_report.qs").read_text(encoding="utf-8")

        self.assertIn("var renderSpec = parts.length >= 6 ? _parseRenderSpec(parts[5]) : {};", script)
        self.assertIn("x_range_ppm", script)
        self.assertIn("_targetSignalHeightFraction(renderSpec", script)
        self.assertIn("_peakThresholdFraction(nucleus, renderSpec", script)
        self.assertIn("_filterMultipletReportByPeakThreshold", script)
        self.assertIn("_isIgnoredByRenderSpec(delta, renderSpec", script)
        self.assertIn("_prepareSpectrumForExport(spectrum, nucleus, tasks[i].renderSpec || {})", script)


if __name__ == "__main__":
    unittest.main()
