from __future__ import annotations

import unittest

from si_generator.graph.state import make_initial_state
from si_generator.models import Compound


class GraphStateTests(unittest.TestCase):
    def test_initial_state_contains_dict_storage_and_defaults(self) -> None:
        state = make_initial_state(
            legacy_compounds=[Compound(number="2a", name="A")],
            input_paths={"table": "examples/test_input.docx"},
            output_paths={"docx": "output/support_information.docx"},
        )

        self.assertEqual(state["order"], ["cmp_001"])
        self.assertEqual(state["compounds"]["cmp_001"]["number"], "2a")
        self.assertEqual(state["spectra_config"]["insert_spectra_as"], "png")
        self.assertEqual(state["spectra_config"]["target_signal_height_fraction"], 0.80)
        self.assertEqual(state["journal_profile"]["id"], "default")


if __name__ == "__main__":
    unittest.main()

