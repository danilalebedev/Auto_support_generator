from __future__ import annotations

import unittest

from si_generator.domain.reactions import calculate_reaction_loadings, format_reagent_amount
from si_generator.graph.compound_store import make_compound_store
from si_generator.graph.nodes.loadings import calculate_loadings_node
from si_generator.models import Compound


class ReactionLoadingsTests(unittest.TestCase):
    def test_calculates_mmol_mass_and_density_volume(self) -> None:
        reaction = {
            "target_mmol": 1.5,
            "reagents": [
                {
                    "name": "Piperidine",
                    "equivalents": 0.1,
                    "mw": 85.15,
                    "density_g_mL": 0.862,
                }
            ],
        }

        result = calculate_reaction_loadings(reaction)
        reagent = result["reagents"][0]

        self.assertEqual(reagent["mmol"], 0.15)
        self.assertEqual(reagent["mass_mg"], 12.77)
        self.assertEqual(reagent["volume_uL"], 14.81)
        self.assertIn("Piperidine", result["formatted_text"])

    def test_calculates_solution_volume_from_concentration(self) -> None:
        reaction = {
            "target_mmol": 2.0,
            "reagents": [
                {
                    "name": "NBS solution",
                    "equivalents": 1.2,
                    "concentration_M": 0.5,
                }
            ],
        }

        result = calculate_reaction_loadings(reaction)

        self.assertEqual(result["reagents"][0]["mmol"], 2.4)
        self.assertEqual(result["reagents"][0]["volume_uL"], 4800.0)

    def test_formats_reagent_amount(self) -> None:
        self.assertEqual(
            format_reagent_amount({"name": "NBS", "mass_mg": 320, "mmol": 1.8, "equivalents": 1.2}),
            "NBS (320 mg, 1.8 mmol, 1.2 equiv)",
        )

    def test_graph_node_is_gated_by_generation_config(self) -> None:
        compound = Compound(
            number="2a",
            name="Example",
            reaction={
                "target_mmol": 1.0,
                "reagents": [{"name": "NBS", "equivalents": 1.1, "mw": 177.98}],
            },
        )
        compounds, order = make_compound_store([compound])

        skipped = calculate_loadings_node({"compounds": compounds, "order": order, "generation_config": {"generate_loadings": False}})
        applied = calculate_loadings_node({"compounds": compounds, "order": order, "generation_config": {"generate_loadings": True}})

        self.assertEqual(skipped, {})
        reagent = applied["compounds"]["cmp_001"].reaction["reagents"][0]
        self.assertEqual(reagent["mmol"], 1.1)
        self.assertEqual(reagent["mass_mg"], 195.78)


if __name__ == "__main__":
    unittest.main()
