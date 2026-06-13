from __future__ import annotations

from pathlib import Path


def insert_chemdraw_placeholders(docx_path: str | Path, structure_map: dict[str, str]) -> None:
    """Replace [[STRUCTURE:number]] placeholders with ChemDraw OLE objects.

    This requires Windows, Microsoft Word and ChemDraw OLE support. The generator
    can run without this step; this function is the bridge to real ChemDraw
    objects once .cdx/.cdxml files are prepared.
    """
    import pythoncom
    import win32com.client as win32

    docx_path = str(Path(docx_path).resolve())
    pythoncom.CoInitialize()
    word = win32.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    doc = None

    try:
        doc = word.Documents.Open(docx_path, False, False, False)
        for number, structure_path in structure_map.items():
            marker = f"[[STRUCTURE:{number}]]"
            structure_path = str(Path(structure_path).resolve())
            if not Path(structure_path).exists():
                raise FileNotFoundError(structure_path)

            finder = doc.Content.Find
            finder.ClearFormatting()
            finder.Text = marker
            while finder.Execute():
                rng = finder.Parent
                rng.Text = ""
                rng.InlineShapes.AddOLEObject(
                    ClassType="ChemDraw.Document",
                    FileName=structure_path,
                    LinkToFile=False,
                    DisplayAsIcon=False,
                )
        doc.Save()
    finally:
        if doc is not None:
            doc.Close(False)
        word.Quit(False)
        pythoncom.CoUninitialize()

