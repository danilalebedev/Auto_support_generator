"""Keep cached crystallographic table numbers correct without running Word."""
from __future__ import annotations

from pathlib import Path
import re
from tempfile import NamedTemporaryFile
import zipfile

from lxml import etree


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SEQUENCE = "ASGCrystalTable"


def renumber_tables(root) -> int:
    count = 0
    for field in root.iter(f"{{{WORD_NS}}}fldSimple"):
        instruction = field.get(f"{{{WORD_NS}}}instr", "")
        if not re.match(r"^\s*SEQ\s+" + SEQUENCE + r"(?:\s|$)", instruction):
            continue
        texts = list(field.iter(f"{{{WORD_NS}}}t"))
        if not texts:
            raise ValueError("Crystallographic table number has no cached value")
        count += 1
        texts[0].text = str(count)
        for text in texts[1:]:
            text.text = ""
    return count


def renumber_docx_tables(path: Path) -> None:
    temporary = None
    try:
        with zipfile.ZipFile(path) as source:
            root = etree.fromstring(source.read("word/document.xml"))
            if not renumber_tables(root):
                return
            with NamedTemporaryFile(dir=path.parent, suffix=".docx", delete=False) as handle:
                temporary = Path(handle.name)
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as target:
                for item in source.infolist():
                    content = (etree.tostring(root, encoding="UTF-8", xml_declaration=True)
                               if item.filename == "word/document.xml" else source.read(item.filename))
                    target.writestr(item, content)
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
