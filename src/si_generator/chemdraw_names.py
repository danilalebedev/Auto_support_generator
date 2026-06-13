from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import TypeVar
from xml.etree import ElementTree as ET

import olefile
import pythoncom
import win32com.client as win32

from .external_tools import make_ascii_work_dir


NS = {
    "o": "urn:schemas-microsoft-com:office:office",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}


T = TypeVar("T")


def extract_chemdraw_names_by_row(docx_path: str | Path, rows: list[int] | None = None) -> dict[int, str]:
    cdx_by_row = _extract_cdx_by_row(Path(docx_path), set(rows or []))
    if not cdx_by_row:
        return {}
    return _names_from_cdx_with_chemdraw(cdx_by_row)


def extract_chemdraw_names_by_cell(
    docx_path: str | Path,
    cells: list[tuple[int, int, int]] | None = None,
) -> dict[tuple[int, int, int], str]:
    cdx_by_cell = _extract_cdx_by_cell(Path(docx_path), set(cells or []))
    if not cdx_by_cell:
        return {}
    return _names_from_cdx_with_chemdraw(cdx_by_cell)


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


def _extract_cdx_by_cell(docx_path: Path, cells: set[tuple[int, int, int]]) -> dict[tuple[int, int, int], bytes]:
    with zipfile.ZipFile(docx_path, "r") as archive:
        rels = _document_relationships(archive)
        document = ET.fromstring(archive.read("word/document.xml"))

        result: dict[tuple[int, int, int], bytes] = {}
        for table_index, table in enumerate(document.findall(".//w:tbl", NS), start=1):
            for row_index, row in enumerate(table.findall("w:tr", NS), start=1):
                for cell_index, cell in enumerate(row.findall("w:tc", NS), start=1):
                    key = (table_index, row_index, cell_index)
                    if cells and key not in cells:
                        continue
                    ole = cell.find(".//o:OLEObject", NS)
                    if ole is None:
                        continue
                    rel_id = ole.attrib.get(f"{{{NS['r']}}}id")
                    target = rels.get(rel_id or "")
                    if not target:
                        continue
                    try:
                        with olefile.OleFileIO(io.BytesIO(archive.read(f"word/{target}"))) as ole_file:
                            result[key] = ole_file.openstream("CONTENTS").read()
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


def _names_from_cdx_with_chemdraw(cdx_by_key: dict[T, bytes]) -> dict[T, str]:
    pythoncom.CoInitialize()
    app = _dispatch_chemdraw()
    app.Visible = False
    result: dict[T, str] = {}
    temp_root = make_ascii_work_dir("chemdraw")
    try:
        for index, (key, cdx) in enumerate(cdx_by_key.items(), start=1):
            temp_path = _write_temp_cdx(temp_root, index, cdx)
            doc = None
            try:
                doc = app.Documents.Open(str(temp_path))
                name = str(doc.Objects.GetData("chemical/x-name")).strip()
                if name:
                    result[key] = name
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
        shutil.rmtree(temp_root, ignore_errors=True)
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


def _write_temp_cdx(root: Path, row: int, cdx: bytes) -> Path:
    path = root / f"row_{row}.cdx"
    path.write_bytes(cdx)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract generated ChemDraw names from Word OLE structures.")
    parser.add_argument("docx")
    parser.add_argument("--rows", default="", help="Comma-separated 1-based Word table row numbers.")
    parser.add_argument("--cells", default="", help="Comma-separated 1-based table:row:cell coordinates.")
    args = parser.parse_args(argv)

    try:
        if args.cells.strip():
            cells = [_parse_cell_coordinate(item) for item in args.cells.split(",") if item.strip()]
            cell_result = extract_chemdraw_names_by_cell(args.docx, cells=cells)
            result = {_format_cell_coordinate(cell): name for cell, name in cell_result.items()}
        else:
            rows = [int(item) for item in args.rows.split(",") if item.strip()]
            result = extract_chemdraw_names_by_row(args.docx, rows=rows)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, ensure_ascii=False)
    return 0


def _parse_cell_coordinate(value: str) -> tuple[int, int, int]:
    parts = [int(part.strip()) for part in value.split(":")]
    if len(parts) != 3:
        raise ValueError(f"Invalid cell coordinate: {value}")
    return parts[0], parts[1], parts[2]


def _format_cell_coordinate(cell: tuple[int, int, int]) -> str:
    return f"{cell[0]}:{cell[1]}:{cell[2]}"


if __name__ == "__main__":
    raise SystemExit(main())
