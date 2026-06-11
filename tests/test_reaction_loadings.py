from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from docx import Document

from si_generator.docx_builder import build_document_from_model
from si_generator.domain.reactions import calculate_reaction_loadings, format_reagent_amount, reaction_from_fields
from si_generator.graph.compound_store import make_compound_store
from si_generator.graph.nodes.loadings import calculate_loadings_node
from si_generator.input_table import read_compounds
from si_generator.models import Compound
from si_generator.render.document_model import build_si_document_model


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

    def test_reaction_from_tabular_fields(self) -> None:
        reaction = reaction_from_fields(
            {
                "target_mmol": "1.5",
                "reagent_1_name": "Piperidine",
                "reagent_1_equiv": "0.1",
                "reagent_1_mw": "85.15",
                "reagent_1_density_g_ml": "0.862",
            }
        )

        self.assertEqual(reaction["target_mmol"], 1.5)
        self.assertEqual(reaction["reagents"][0]["name"], "Piperidine")
        self.assertEqual(reaction["reagents"][0]["equivalents"], 0.1)
        self.assertEqual(reaction["reagents"][0]["density_g_mL"], 0.862)

    def test_csv_input_reads_reaction_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "compounds.csv"
            input_path.write_text(
                "number,name,target_mmol,reagent_1_name,reagent_1_equiv,reagent_1_mw\n"
                "2a,Example,1.0,NBS,1.1,177.98\n",
                encoding="utf-8",
            )

            compounds = read_compounds(input_path)

        self.assertEqual(compounds[0].reaction["target_mmol"], 1.0)
        self.assertEqual(compounds[0].reaction["reagents"][0]["name"], "NBS")

    def test_graph_node_runs_when_reaction_data_is_present(self) -> None:
        compound = Compound(
            number="2a",
            name="Example",
            reaction={
                "target_mmol": 1.0,
                "reagents": [{"name": "NBS", "equivalents": 1.1, "mw": 177.98}],
            },
        )
        compounds, order = make_compound_store([compound])

        applied = calculate_loadings_node({"compounds": compounds, "order": order, "generation_config": {"generate_loadings": False}})

        reagent = applied["compounds"]["cmp_001"].reaction["reagents"][0]
        self.assertEqual(reagent["mmol"], 1.1)
        self.assertEqual(reagent["mass_mg"], 195.78)

    def test_graph_node_skips_when_no_reaction_data_and_flag_is_disabled(self) -> None:
        compounds, order = make_compound_store([Compound(number="2a", name="Example")])

        result = calculate_loadings_node({"compounds": compounds, "order": order, "generation_config": {"generate_loadings": False}})

        self.assertEqual(result, {})

    def test_docx_renders_calculated_reaction_loadings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "support_information.docx"
            compound = Compound(
                id="cmp_001",
                number="2a",
                name="Example",
                reaction={
                    "target_mmol": 1.0,
                    "reagents": [{"name": "NBS", "equivalents": 1.1, "mw": 177.98}],
                },
            )

            build_document_from_model(build_si_document_model([compound]), output_path)
            text = "\n".join(paragraph.text for paragraph in Document(output_path).paragraphs)

        self.assertIn("Reaction loadings: NBS (195.78 mg, 1.1 mmol, 1.1 equiv).", text)


if __name__ == "__main__":
    unittest.main()
