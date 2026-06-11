from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from si_generator.domain.journal_profile import load_journal_profile as load_domain_journal_profile
from si_generator.domain.journal_profile import profile_template_path as domain_profile_template_path
from si_generator.render.document_model import build_si_document_model
from si_generator.render.journal_profile import available_builtin_profiles, load_journal_profile, profile_template_path
from si_generator.models import Compound
from si_generator.workflows.generate_si import request_from_args


class JournalProfileTests(unittest.TestCase):
    def test_render_module_reexports_domain_journal_profile_api(self) -> None:
        self.assertIs(load_journal_profile, load_domain_journal_profile)
        self.assertIs(profile_template_path, domain_profile_template_path)

    def test_loads_builtin_profile(self) -> None:
        profile = load_journal_profile("acs")

        self.assertIn("acs", available_builtin_profiles())
        self.assertEqual(profile["id"], "acs")
        self.assertEqual(profile["reference_style"], "acs")
        self.assertTrue(profile["use_italic_j"])

    def test_custom_profile_controls_section_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "custom.yml"
            profile_path.write_text(
                "id: custom\n"
                "name: Custom profile\n"
                "section_order: [spectra_appendix, compound_descriptions]\n",
                encoding="utf-8",
            )
            image_path = Path(tmp) / "2a_1H.png"
            image_path.write_bytes(b"model-only")
            compound = Compound(id="cmp_001", number="2a", name="Example", h1_image_path=str(image_path))

            profile = load_journal_profile(profile_path)
            model = build_si_document_model([compound], profile)

        self.assertEqual(profile["id"], "custom")
        self.assertEqual([section["id"] for section in model["sections"]], ["spectra_appendix", "compound_descriptions"])
        self.assertEqual(model["metadata"]["journal_profile"], "custom")

    def test_cli_args_accept_journal_profile(self) -> None:
        args = Namespace(
            word_input="input.docx",
            input=None,
            output="out.docx",
            template_docx=None,
            style_config=None,
            journal_profile="rsc",
            references=None,
            spectra_zip=None,
            mnova_exe=None,
            no_extract_nmr=True,
            extract_structure_metadata=False,
            only="",
            insert_chemdraw=False,
            no_check_support=True,
        )

        request = request_from_args(args)

        self.assertEqual(request.journal_profile, "rsc")


if __name__ == "__main__":
    unittest.main()
