from __future__ import annotations

from pathlib import Path

from .word_ole_trace import trace_word_ole_event


def insert_chemdraw_placeholders(docx_path: str | Path, structure_map: dict[str, str]) -> None:
    """Replace [[STRUCTURE:number]] placeholders with ChemDraw OLE objects.

    This requires Windows, Microsoft Word and ChemDraw OLE support. The generator
    can run without this step; this function is the bridge to real ChemDraw
    objects once .cdx/.cdxml files are prepared.
    """
    import pythoncom
    import win32com.client as win32

    docx_path = Path(docx_path).resolve()
    trace_word_ole_event(docx_path, "chemdraw.insert.start", docx_path=docx_path, structure_count=len(structure_map))
    pythoncom.CoInitialize()
    word = win32.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = None

    try:
        trace_word_ole_event(docx_path, "chemdraw.word.open.start", docx_path=docx_path)
        doc = word.Documents.Open(str(docx_path), False, False, False)
        trace_word_ole_event(docx_path, "chemdraw.word.open.end", docx_path=docx_path)
        for number, structure_path in structure_map.items():
            marker = f"[[STRUCTURE:{number}]]"
            structure_path = str(Path(structure_path).resolve())
            if not Path(structure_path).exists():
                raise FileNotFoundError(structure_path)

            finder = doc.Content.Find
            finder.ClearFormatting()
            finder.Text = marker
            while finder.Execute():
                trace_word_ole_event(docx_path, "chemdraw.add_ole.start", marker=marker, structure_path=structure_path)
                rng = finder.Parent
                rng.Text = ""
                rng.InlineShapes.AddOLEObject(
                    ClassType="ChemDraw.Document",
                    FileName=structure_path,
                    LinkToFile=False,
                    DisplayAsIcon=False,
                )
                trace_word_ole_event(docx_path, "chemdraw.add_ole.end", marker=marker, structure_path=structure_path)
        doc.Save()
    except Exception as exc:
        trace_word_ole_event(docx_path, "chemdraw.insert.error", error=repr(exc))
        raise
    finally:
        if doc is not None:
            doc.Close(False)
        word.Quit(False)
        pythoncom.CoUninitialize()
        trace_word_ole_event(docx_path, "chemdraw.insert.end", docx_path=docx_path)

