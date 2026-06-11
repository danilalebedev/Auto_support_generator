from __future__ import annotations

import unittest

from si_generator.domain.ir import format_ir_block, parse_ir_block


class IRTests(unittest.TestCase):
    def test_parses_full_ir_line_with_method_and_peaks(self) -> None:
        block = parse_ir_block("IR (ATR, cm-1): 3038, 2957, 1711.")

        self.assertEqual(block["method"], "ATR")
        self.assertEqual(block["peaks_cm1"], [3038, 2957, 1711])
        self.assertEqual(block["formatted_text"], "IR (ATR, cm-1): 3038, 2957, 1711.")

    def test_parses_plain_peak_list_with_default_method(self) -> None:
        block = parse_ir_block("3038, 2957, 1711")

        self.assertEqual(block["method"], "KBr")
        self.assertEqual(block["peaks_cm1"], [3038, 2957, 1711])

    def test_formats_structured_ir_block(self) -> None:
        self.assertEqual(
            format_ir_block({"method": "film", "peaks_cm1": [1711, 1606]}),
            "IR (film, cm-1): 1711, 1606.",
        )


if __name__ == "__main__":
    unittest.main()
