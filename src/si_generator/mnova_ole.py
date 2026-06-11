from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .domain.compound import Compound


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

    docx_path = str(Path(docx_path).resolve())
    pythoncom.CoInitialize()
    word = None
    doc = None

    try:
        word = win32.DispatchEx("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(docx_path, False, False, False)
        for marker, target in placeholders.items():
            _replace_marker_with_mnova_object(doc, marker, _coerce_target(target))
        doc.Save()
    finally:
        if doc is not None:
            doc.Close(False)
        if word is not None:
            word.Quit(False)
        pythoncom.CoUninitialize()


def _coerce_target(target: MnovaOleTarget | Path) -> MnovaOleTarget:
    if isinstance(target, MnovaOleTarget):
        return MnovaOleTarget(
            mnova_path=target.mnova_path.resolve(),
            image_path=target.image_path.resolve() if target.image_path else None,
        )
    return MnovaOleTarget(mnova_path=Path(target).resolve())


def _replace_marker_with_mnova_object(doc, marker: str, target: MnovaOleTarget) -> None:
    finder = doc.Content.Find
    finder.ClearFormatting()
    finder.Text = marker
    while finder.Execute():
        rng = finder.Parent
        rng.Text = ""
        try:
            shape = doc.InlineShapes.AddOLEObject(
                FileName=str(target.mnova_path),
                LinkToFile=False,
                DisplayAsIcon=False,
                Range=rng,
            )
            _fit_inline_shape_to_page(doc, shape)
        except Exception:
            _replace_range_with_clickable_preview(doc, rng, target)


def _replace_range_with_clickable_preview(doc, rng, target: MnovaOleTarget) -> None:
    if target.image_path and target.image_path.exists():
        try:
            shape = doc.InlineShapes.AddPicture(
                FileName=str(target.image_path),
                LinkToFile=False,
                SaveWithDocument=True,
                Range=rng,
            )
            _fit_inline_shape_to_page(doc, shape)
            doc.Hyperlinks.Add(Anchor=shape.Range, Address=str(target.mnova_path))
            return
        except Exception:
            pass
    _replace_range_with_link(doc, rng, target.mnova_path)


def _replace_range_with_link(doc, rng, mnova_path: Path) -> None:
    label = f"Open {mnova_path.name}"
    rng.Text = label
    doc.Hyperlinks.Add(
        Anchor=rng,
        Address=str(mnova_path),
        TextToDisplay=label,
    )


def _fit_inline_shape_to_page(doc, shape) -> None:
    try:
        page_setup = doc.PageSetup
        max_width = page_setup.PageWidth - page_setup.LeftMargin - page_setup.RightMargin
        if shape.Width > max_width:
            shape.Width = max_width
    except Exception:
        return
