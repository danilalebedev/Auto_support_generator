from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from si_generator.unified_word_input import build_unified_input_docx


def main() -> int:
    examples_root = REPO_ROOT / "examples"
    generated = 0
    for example in sorted(path for path in examples_root.glob("example_*") if path.is_dir()):
        compound_table = example / "Compound_table.docx"
        if not compound_table.exists():
            continue
        build_unified_input_docx(
            compound_table,
            example / "All_in_one_input.docx",
            reaction_schema=_optional(example / "Reaction_schema.docx"),
            scope=_optional(example / "Scope.docx"),
            si_template=_optional(example / "SI_template.docx"),
        )
        print(example / "All_in_one_input.docx")
        generated += 1
    return 0 if generated else 1


def _optional(path: Path) -> Path | None:
    return path if path.exists() else None


if __name__ == "__main__":
    raise SystemExit(main())
