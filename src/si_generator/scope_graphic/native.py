from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory


@contextmanager
def chemdraw():
    import pythoncom
    from ..chemdraw_names import _dispatch_chemdraw

    pythoncom.CoInitialize()
    app = None
    try:
        app = _dispatch_chemdraw()
        yield app
    finally:
        if app is not None:
            # Only close the documents opened by this module. ChemDraw can reuse
            # an existing application even for DispatchEx.
            if app.Documents.Count == 0:
                app.Quit()
        pythoncom.CoUninitialize()


def cdx_to_xml(app, cdx: bytes) -> str:
    with TemporaryDirectory(prefix="asg_scope_") as tmp:
        path = Path(tmp) / "structure.cdx"
        path.write_bytes(cdx)
        doc = app.Documents.Open(str(path))
        try:
            xml = str(doc.Objects.GetData("chemical/x-cdxml"))
            if "<CDXML" not in xml:
                raise ValueError("ChemDraw did not return a CDXML structure.")
            return xml
        finally:
            doc.Close(False)


def render_png(app, cdxml: Path, output: Path) -> None:
    doc = app.Documents.Open(str(cdxml.resolve()))
    try:
        data = bytes(doc.Objects.GetData("image/png"))
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("ChemDraw did not return a PNG preview.")
        output.write_bytes(data)
    finally:
        doc.Close(False)


def save_cdx(app, cdxml: Path, output: Path) -> None:
    doc = app.Documents.Open(str(cdxml.resolve()))
    try:
        doc.SaveAs(str(output.resolve()))
    finally:
        doc.Close(False)
