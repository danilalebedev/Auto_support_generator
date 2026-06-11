from __future__ import annotations

import unittest

from si_generator.domain.bookmarks import bookmark_name_for_block_id


class BookmarkTests(unittest.TestCase):
    def test_bookmark_names_are_word_safe_and_stable(self) -> None:
        first = bookmark_name_for_block_id("spectrum:cmp_001:13C")
        second = bookmark_name_for_block_id("spectrum:cmp_001:13C")

        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 40)
        self.assertRegex(first, r"^[A-Za-z][A-Za-z0-9_]+$")
        self.assertNotIn(":", first)


if __name__ == "__main__":
    unittest.main()
