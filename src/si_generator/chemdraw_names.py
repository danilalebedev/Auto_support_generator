from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import olefile
import pythoncom
import win32com.client as win32


NS = {
    "o": "urn:schemas-microsoft-com:office:office",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}


def extract_chemdraw_names_by_row(docx_path: str | Path, rows: list[int] | None = None) -> dict[int, str]:
    cdx_by_row = _extract_cdx_by_row(Path(docx_path), set(rows or []))
    if not cdx_by_row:
        return {}
    return _names_from_cdx_with_chemdraw(cdx_by_row)


def _extract_cdx_by_row(docx_path: Path, rows: set[int]) -> dict[int, bytes]:
    with zipfile.ZipFile(docx_path, "r") as archive:
        rels = _document_relationships(archive)
        document = ET.fromstring(archive.read("word/document.xml"))
        table = document.find(".//w:tbl", NS)
        if table is None:
            return {}

        result: dict[int, bytes] = {}
        for row_index, row in enumerate(table.findall("w:tr", NS), start=1):
            if rows and row_index not in rows:
                continue
            ole = row.find(".//o:OLEObject", NS)
            if ole is None:
                continue
            rel_id = ole.attrib.get(f"{{{NS['r']}}}id")
            target = rels.get(rel_id or "")
            if not target:
                continue
            try:
                with olefile.OleFileIO(io.BytesIO(archive.read(f"word/{target}"))) as ole_file:
                    result[row_index] = ole_file.openstream("CONTENTS").read()
            except Exception:
                continue
        return result


def _document_relationships(archive: zipfile.ZipFile) -> dict[str, str]:
    rels_xml = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
    rels: dict[str, str] = {}
    for rel in rels_xml:
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target", "")
        if rel_id and target.startswith("embeddings/"):
            rels[rel_id] = target
    return rels


def _names_from_cdx_with_chemdraw(cdx_by_row: dict[int, bytes]) -> dict[int, str]:
    pythoncom.CoInitialize()
    app = _dispatch_chemdraw()
    app.Visible = False
    result: dict[int, str] = {}
    try:
        for row, cdx in cdx_by_row.items():
            temp_path = _write_temp_cdx(row, cdx)
            doc = None
            try:
                doc = app.Documents.Open(str(temp_path))
                name = str(doc.Objects.GetData("chemical/x-name")).strip()
                if name:
                    result[row] = name
            except Exception:
                pass
            finally:
                if doc is not None:
                    try:
                        doc.Close(False)
                    except Exception:
                        pass
                temp_path.unlink(missing_ok=True)
        return result
    finally:
        try:
            app.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()


def _dispatch_chemdraw():
    last_error: Exception | None = None
    for prog_id in ["ChemDraw.Application", "ChemDraw.Application.22", "ChemDraw.Application.21", "ChemDraw.Application.20"]:
        try:
            return win32.DispatchEx(prog_id)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(
        "ChemDraw COM server was not found. Open ChemDraw once, check that it is activated, "
        "or reinstall ChemDraw/ChemOffice with OLE/COM support enabled."
    ) from last_error


def _write_temp_cdx(row: int, cdx: bytes) -> Path:
    path = Path(tempfile.gettempdir()) / f"auto_si_chemdraw_name_row_{row}.cdx"
    path.write_bytes(cdx)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract generated ChemDraw names from Word OLE structures.")
    parser.add_argument("docx")
    parser.add_argument("--rows", default="", help="Comma-separated 1-based Word table row numbers.")
    args = parser.parse_args(argv)

    rows = [int(item) for item in args.rows.split(",") if item.strip()]
    try:
        result = extract_chemdraw_names_by_row(args.docx, rows=rows)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
