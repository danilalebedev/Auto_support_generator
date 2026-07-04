from __future__ import annotations

import unittest

from si_generator.domain.elemental_analysis import (
    calculate_elemental_analysis_block,
    calculate_elemental_percentages,
    parse_found_percentages,
)
from si_generator.graph.compound_store import make_compound_store
from si_generator.graph.nodes.elemental_analysis import calculate_elemental_analysis_node
from si_generator.domain.compound import Compound


class ElementalAnalysisTests(unittest.TestCase):
    def test_calculates_theoretical_percentages(self) -> None:
        percentages = calculate_elemental_percentages("C2H6O")

        self.assertEqual(percentages["C"], 52.14)
        self.assertEqual(percentages["H"], 13.13)

    def test_builds_block_and_formats_found_values(self) -> None:
        block = calculate_elemental_analysis_block("C17H11FN2O3", found="C, 66.03; H, 3.55; N, 8.92")

        self.assertEqual(block["calculated"]["C"], 65.81)
        self.assertEqual(block["found"], {"C": 66.03, "H": 3.55, "N": 8.92})
        self.assertEqual(
            block["formatted_text"],
            "Anal. Calcd for C17H11FN2O3: C, 65.81; H, 3.57; N, 9.03. Found: C, 66.03; H, 3.55; N, 8.92.",
        )

    def test_builds_block_for_found_non_default_elements(self) -> None:
        block = calculate_elemental_analysis_block("C2H6OS", found="C, 30.75; H, 7.74; S, 41.04")

        self.assertIn("S", block["calculated"])
        self.assertEqual(block["found"]["S"], 41.04)
        self.assertIn("S,", block["formatted_text"])

    def test_parse_found_percentages_accepts_mapping(self) -> None:
        self.assertEqual(parse_found_percentages({"C": 68.421, "H": 5.314}), {"C": 68.42, "H": 5.31})

    def test_graph_node_respects_generation_flags(self) -> None:
        compound = Compound(
            number="2a",
            name="Example",
            formula="C2H6O",
            elemental_analysis={"found": {"C": 52.10, "H": 13.20}},
        )
        compounds, order = make_compound_store([compound])

        skipped = calculate_elemental_analysis_node(
            {"compounds": compounds, "order": order, "issues": [], "generation_config": {"include_elemental_analysis": False}}
        )
        applied = calculate_elemental_analysis_node(
            {
                "compounds": compounds,
                "order": order,
                "issues": [],
                "generation_config": {"include_elemental_analysis": True, "calculate_elemental_analysis": False},
            }
        )

        self.assertEqual(skipped, {})
        updated = applied["compounds"]["cmp_001"].elemental_analysis
        self.assertEqual(updated["calculated"]["C"], 52.14)
        self.assertEqual(updated["found"]["H"], 13.20)
        self.assertEqual(applied["issues"], [])

    def test_graph_node_can_calculate_elemental_analysis_for_all_compounds(self) -> None:
        compound = Compound(number="2a", name="Example", formula="C2H6O")
        compounds, order = make_compound_store([compound])

        skipped = calculate_elemental_analysis_node(
            {
                "compounds": compounds,
                "order": order,
                "issues": [],
                "generation_config": {"include_elemental_analysis": True, "calculate_elemental_analysis": False},
            }
        )
        applied = calculate_elemental_analysis_node(
            {
                "compounds": compounds,
                "order": order,
                "issues": [],
                "generation_config": {"include_elemental_analysis": True, "calculate_elemental_analysis": True},
            }
        )

        self.assertEqual(skipped, {})
        self.assertEqual(applied["compounds"]["cmp_001"].elemental_analysis["calculated"]["C"], 52.14)


if __name__ == "__main__":
    unittest.main()
