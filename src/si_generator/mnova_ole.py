from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .domain.compound import Compound
from .word_ole_trace import trace_word_ole_event


@dataclass(frozen=True)
class MnovaOleTarget:
    mnova_path: Path
    image_path: Path | None = None


def mnova_placeholder_map(compounds: list[Compound]) -> dict[str, MnovaOleTarget]:
    placeholders: dict[str, MnovaOleTarget] = {}
    for compound in compounds:
        if not compound.mnova_path:
            continue
        mnova_path = Path(compound.mnova_path)
        if not mnova_path.exists():
            continue
        for nucleus, image_value in [("1H", compound.h1_image_path), ("13C", compound.c13_image_path)]:
            image_path = Path(image_value) if image_value else None
            placeholders[f"[[MNOVA:{compound.number}:{nucleus}]]"] = MnovaOleTarget(
                mnova_path=mnova_path,
                image_path=image_path if image_path and image_path.exists() else None,
            )
    return placeholders


def insert_mnova_placeholders(docx_path: str | Path, placeholders: Mapping[str, MnovaOleTarget | Path]) -> None:
    if not placeholders:
        return

    import pythoncom
    import win32com.client as win32

    docx_path = Path(docx_path).resolve()
    ole_class_type = _registered_mnova_ole_class_type()
    trace_word_ole_event(
        docx_path,
        "mnova.insert.start",
        docx_path=docx_path,
        placeholder_count=len(placeholders),
        ole_class_type=ole_class_type or "",
    )
    pythoncom.CoInitialize()
    word = None
    doc = None

    try:
        trace_word_ole_event(docx_path, "mnova.word.dispatch.start")
        word = win32.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        trace_word_ole_event(docx_path, "mnova.word.open.start", docx_path=docx_path)
        doc = word.Documents.Open(str(docx_path), False, False, False)
        trace_word_ole_event(docx_path, "mnova.word.open.end", docx_path=docx_path)
        for marker, target in placeholders.items():
            _replace_marker_with_mnova_object(doc, marker, _coerce_target(target), ole_class_type, docx_path)
        trace_word_ole_event(docx_path, "mnova.word.save.start", docx_path=docx_path)
        doc.Save()
        trace_word_ole_event(docx_path, "mnova.word.save.end", docx_path=docx_path)
    except Exception as exc:
        trace_word_ole_event(docx_path, "mnova.insert.error", error=repr(exc))
        raise
    finally:
        if doc is not None:
            trace_word_ole_event(docx_path, "mnova.word.close.start", docx_path=docx_path)
            doc.Close(False)
            trace_word_ole_event(docx_path, "mnova.word.close.end", docx_path=docx_path)
        if word is not None:
            trace_word_ole_event(docx_path, "mnova.word.quit.start")
            word.Quit(False)
            trace_word_ole_event(docx_path, "mnova.word.quit.end")
        pythoncom.CoUninitialize()
        trace_word_ole_event(docx_path, "mnova.insert.end", docx_path=docx_path)


def _coerce_target(target: MnovaOleTarget | Path) -> MnovaOleTarget:
    if isinstance(target, MnovaOleTarget):
        return MnovaOleTarget(
            mnova_path=target.mnova_path.resolve(),
            image_path=target.image_path.resolve() if target.image_path else None,
        )
    return MnovaOleTarget(mnova_path=Path(target).resolve())


def _replace_marker_with_mnova_object(doc, marker: str, target: MnovaOleTarget, ole_class_type: str | None, trace_anchor: Path) -> None:
    finder = doc.Content.Find
    finder.ClearFormatting()
    finder.Text = marker
    while finder.Execute():
        trace_word_ole_event(trace_anchor, "mnova.marker.found", marker=marker, mnova_path=target.mnova_path, image_path=target.image_path or "")
        rng = finder.Parent
        rng.Text = ""
        if not ole_class_type:
            trace_word_ole_event(trace_anchor, "mnova.add_ole.skip_no_registered_server", marker=marker, mnova_path=target.mnova_path)
            _replace_range_with_clickable_preview(doc, rng, target, trace_anchor)
            continue
        try:
            trace_word_ole_event(
                trace_anchor,
                "mnova.add_ole.start",
                marker=marker,
                mnova_path=target.mnova_path,
                class_type=ole_class_type,
            )
            shape = doc.InlineShapes.AddOLEObject(
                ClassType=ole_class_type,
                FileName=str(target.mnova_path),
                LinkToFile=False,
                DisplayAsIcon=False,
                Range=rng,
            )
            _fit_inline_shape_to_page(doc, shape)
            trace_word_ole_event(trace_anchor, "mnova.add_ole.end", marker=marker, mnova_path=target.mnova_path, class_type=ole_class_type)
        except Exception:
            trace_word_ole_event(trace_anchor, "mnova.add_ole.error", marker=marker, mnova_path=target.mnova_path)
            _replace_range_with_clickable_preview(doc, rng, target, trace_anchor)


def _replace_range_with_clickable_preview(doc, rng, target: MnovaOleTarget, trace_anchor: Path) -> None:
    if target.image_path and target.image_path.exists():
        try:
            trace_word_ole_event(trace_anchor, "mnova.preview_picture.start", mnova_path=target.mnova_path, image_path=target.image_path)
            shape = doc.InlineShapes.AddPicture(
                FileName=str(target.image_path),
                LinkToFile=False,
                SaveWithDocument=True,
                Range=rng,
            )
            _fit_inline_shape_to_page(doc, shape)
            doc.Hyperlinks.Add(Anchor=shape.Range, Address=str(target.mnova_path))
            trace_word_ole_event(trace_anchor, "mnova.preview_picture.end", mnova_path=target.mnova_path, image_path=target.image_path)
            return
        except Exception:
            trace_word_ole_event(trace_anchor, "mnova.preview_picture.error", mnova_path=target.mnova_path, image_path=target.image_path)
            pass
    _replace_range_with_link(doc, rng, target.mnova_path, trace_anchor)


def _replace_range_with_link(doc, rng, mnova_path: Path, trace_anchor: Path) -> None:
    trace_word_ole_event(trace_anchor, "mnova.preview_link.start", mnova_path=mnova_path)
    label = f"Open {mnova_path.name}"
    rng.Text = label
    doc.Hyperlinks.Add(
        Anchor=rng,
        Address=str(mnova_path),
        TextToDisplay=label,
    )
    trace_word_ole_event(trace_anchor, "mnova.preview_link.end", mnova_path=mnova_path)


def _fit_inline_shape_to_page(doc, shape) -> None:
    try:
        page_setup = doc.PageSetup
        max_width = page_setup.PageWidth - page_setup.LeftMargin - page_setup.RightMargin
        if shape.Width > max_width:
            shape.Width = max_width
    except Exception:
        return


def _registered_mnova_ole_class_type() -> str | None:
    extension_prog_id = _hkcr_default(".mnova")
    if extension_prog_id and _hkcr_default(fr"{extension_prog_id}\CLSID"):
        return extension_prog_id

    if os.environ.get("AUTO_SUPPORT_FORCE_MNOVA_OLE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return _registered_mestrenova_class_type()
    return None


def _registered_mestrenova_class_type() -> str | None:
    for prog_id in ("MestReNova.Document", "MestReNova.Document.1"):
        if _hkcr_default(fr"{prog_id}\CLSID"):
            return prog_id
    return None


def _hkcr_default(subkey: str) -> str:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, subkey) as key:
            value, _ = winreg.QueryValueEx(key, "")
            return str(value or "").strip()
    except Exception:
        return ""
