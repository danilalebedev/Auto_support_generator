from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import time

from .chemdraw_names import _dispatch_chemdraw
from .word_ole_trace import trace_word_ole_event


def insert_chemdraw_placeholders(docx_path: str | Path, structure_map: dict[str, str]) -> None:
    """Replace [[STRUCTURE:number]] placeholders with ChemDraw OLE objects.

    This requires Windows, Microsoft Word and ChemDraw OLE support. The generator
    can run without this step; this function is the bridge to real ChemDraw
    objects once .cdx/.cdxml files are prepared.
    """
    marker_map = {f"[[STRUCTURE:{number}]]": path for number, path in structure_map.items()}
    insert_chemdraw_marker_objects(docx_path, marker_map)


def insert_chemdraw_marker_objects(
    docx_path: str | Path,
    marker_map: Mapping[str, str | Path],
    *,
    size_points: Mapping[str, tuple[float, float]] | None = None,
) -> None:
    """Replace arbitrary text markers with embedded ChemDraw OLE objects."""
    import pythoncom
    import win32com.client as win32

    docx_path = Path(docx_path).resolve()
    trace_word_ole_event(docx_path, "chemdraw.insert.start", docx_path=docx_path, structure_count=len(marker_map))
    pythoncom.CoInitialize()
    word = win32.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    chem_draw = doc = None

    try:
        chem_draw = _dispatch_chemdraw()
        chem_draw.Visible = False
        trace_word_ole_event(docx_path, "chemdraw.word.open.start", docx_path=docx_path)
        doc = word.Documents.Open(str(docx_path), False, False, False)
        trace_word_ole_event(docx_path, "chemdraw.word.open.end", docx_path=docx_path)
        for marker, structure_path in marker_map.items():
            structure_path = str(Path(structure_path).resolve())
            if not Path(structure_path).exists():
                raise FileNotFoundError(structure_path)
            chemical_document = chem_draw.Documents.Open(structure_path)
            try:
                finder = doc.Content.Find
                finder.ClearFormatting()
                finder.Text = marker
                while finder.Execute():
                    trace_word_ole_event(docx_path, "chemdraw.add_ole.start", marker=marker, structure_path=structure_path)
                    rng = finder.Parent
                    rng.Text = ""
                    shape_count = doc.InlineShapes.Count
                    for attempt in range(5):
                        chemical_document.Objects.Copy()
                        time.sleep(0.15 + attempt * 0.15)
                        try:
                            rng.PasteSpecial(DataType=0)
                            break
                        except Exception:
                            if attempt == 4:
                                raise
                    if doc.InlineShapes.Count > shape_count and size_points and marker in size_points:
                        shape = doc.InlineShapes(doc.InlineShapes.Count)
                        width, height = size_points[marker]
                        shape.LockAspectRatio = False
                        shape.Width = float(width)
                        shape.Height = float(height)
                    trace_word_ole_event(docx_path, "chemdraw.add_ole.end", marker=marker, structure_path=structure_path)
            finally:
                chemical_document.Close(False)
        doc.Save()
    except Exception as exc:
        trace_word_ole_event(docx_path, "chemdraw.insert.error", error=repr(exc))
        raise
    finally:
        if doc is not None:
            doc.Close(False)
        word.Quit(False)
        if chem_draw is not None:
            try:
                if chem_draw.Documents.Count == 0:
                    chem_draw.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()
        trace_word_ole_event(docx_path, "chemdraw.insert.end", docx_path=docx_path)

