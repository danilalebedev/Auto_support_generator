from __future__ import annotations

import locale
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .domain.compound import Compound
from .external_tools import find_mnova_executable, make_ascii_work_dir
from .runtime_paths import bundled_resource_path
from .word_ole_trace import trace_word_ole_event


SCRIPT_PATH = bundled_resource_path("scripts/copy_mnova_page.qs", package_file=__file__)
DEFAULT_COPY_ACTION = "action_Edit_Copy"


@dataclass(frozen=True)
class MnovaClipboardTarget:
    mnova_path: Path
    page_index: int
    nucleus: str


def mnova_clipboard_placeholder_map(compounds: list[Compound]) -> dict[str, MnovaClipboardTarget]:
    placeholders: dict[str, MnovaClipboardTarget] = {}
    for compound in compounds:
        if not compound.mnova_path:
            continue
        mnova_path = Path(compound.mnova_path)
        if not mnova_path.exists():
            continue
        for nucleus, page_index in _nucleus_page_indices(compound).items():
            if not _has_spectrum_source(compound, nucleus):
                continue
            placeholders[f"[[MNOVA_PAGE:{compound.number}:{nucleus}]]"] = MnovaClipboardTarget(
                mnova_path=mnova_path,
                page_index=page_index,
                nucleus=nucleus,
            )
    return placeholders


def paste_mnova_clipboard_pages(
    docx_path: str | Path,
    placeholders: Mapping[str, MnovaClipboardTarget],
    *,
    mnova_exe: str | Path | None = None,
    log_dir: str | Path | None = None,
    timeout: int = 120,
    copy_action: str = DEFAULT_COPY_ACTION,
) -> None:
    if not placeholders:
        return

    import pythoncom
    import win32com.client as win32

    docx_path = Path(docx_path).resolve()
    executable = find_mnova_executable(mnova_exe)
    logs = Path(log_dir).resolve() if log_dir else None
    if logs:
        logs.mkdir(parents=True, exist_ok=True)

    trace_word_ole_event(
        docx_path,
        "mnova.clipboard_paste.start",
        docx_path=docx_path,
        placeholder_count=len(placeholders),
        mnova_exe=executable,
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
            _copy_mnova_page_to_clipboard(
                executable,
                target,
                trace_anchor=docx_path,
                log_dir=logs,
                marker=marker,
                timeout=timeout,
                copy_action=copy_action,
            )
            _paste_clipboard_at_marker(word, doc, marker, target, docx_path)

        trace_word_ole_event(docx_path, "mnova.word.save.start", docx_path=docx_path)
        doc.Save()
        trace_word_ole_event(docx_path, "mnova.word.save.end", docx_path=docx_path)
    except Exception as exc:
        trace_word_ole_event(docx_path, "mnova.clipboard_paste.error", error=repr(exc))
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
        trace_word_ole_event(docx_path, "mnova.clipboard_paste.end", docx_path=docx_path)


def _copy_mnova_page_to_clipboard(
    executable: Path,
    target: MnovaClipboardTarget,
    *,
    trace_anchor: Path,
    log_dir: Path | None,
    marker: str,
    timeout: int,
    copy_action: str,
) -> None:
    run_dir = make_ascii_work_dir("mnova_clipboard")
    status_path = run_dir / "copy_mnova_page.status.txt"
    try:
        sf_arg = ",".join(
            [
                "copyMnovaPageToClipboard",
                _mnova_arg(target.mnova_path),
                str(target.page_index),
                _mnova_arg(status_path),
                copy_action,
            ]
        )
        trace_word_ole_event(
            trace_anchor,
            "mnova.copy_page.start",
            marker=marker,
            mnova_path=target.mnova_path,
            page_index=target.page_index,
            action=copy_action,
        )
        command = [str(executable), "-w", str(SCRIPT_PATH), "-sf", sf_arg]
        subprocess.run(command, cwd=run_dir, check=False, timeout=timeout)
        status = _read_text(status_path) if status_path.exists() else "ERROR no Mnova status file"
        if log_dir:
            log_path = log_dir / f"{_safe_token(marker)}.status.txt"
            log_path.write_text(status, encoding="utf-8")
        if "OK copied" not in status:
            raise RuntimeError(status.strip())
        trace_word_ole_event(
            trace_anchor,
            "mnova.copy_page.end",
            marker=marker,
            mnova_path=target.mnova_path,
            page_index=target.page_index,
        )
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def _paste_clipboard_at_marker(word, doc, marker: str, target: MnovaClipboardTarget, trace_anchor: Path) -> None:
    finder = doc.Content.Find
    finder.ClearFormatting()
    finder.Text = marker
    if not finder.Execute():
        raise RuntimeError(f"Mnova spectrum placeholder was not found in output DOCX: {marker}")

    trace_word_ole_event(
        trace_anchor,
        "mnova.word_paste.start",
        marker=marker,
        mnova_path=target.mnova_path,
        page_index=target.page_index,
    )
    rng = finder.Parent
    old_inline_count = doc.InlineShapes.Count
    old_shape_count = doc.Shapes.Count
    rng.Text = ""
    rng.Select()
    word.Selection.Paste()
    _fit_new_paste_to_page(doc, old_inline_count, old_shape_count)
    trace_word_ole_event(
        trace_anchor,
        "mnova.word_paste.end",
        marker=marker,
        inline_shapes_before=old_inline_count,
        inline_shapes_after=doc.InlineShapes.Count,
        shapes_before=old_shape_count,
        shapes_after=doc.Shapes.Count,
    )


def _fit_new_paste_to_page(doc, old_inline_count: int, old_shape_count: int) -> None:
    for index in range(old_inline_count + 1, doc.InlineShapes.Count + 1):
        _fit_shape_to_page(doc, doc.InlineShapes(index))
    for index in range(old_shape_count + 1, doc.Shapes.Count + 1):
        shape = doc.Shapes(index)
        try:
            inline_shape = shape.ConvertToInlineShape()
            _fit_shape_to_page(doc, inline_shape)
        except Exception:
            _fit_shape_to_page(doc, shape)


def _fit_shape_to_page(doc, shape) -> None:
    try:
        page_setup = doc.PageSetup
        max_width = page_setup.PageWidth - page_setup.LeftMargin - page_setup.RightMargin
        if shape.Width > max_width:
            shape.Width = max_width
    except Exception:
        return


def _nucleus_page_indices(compound: Compound) -> dict[str, int]:
    indices: dict[str, int] = {}
    next_index = 0
    if _has_spectrum_source(compound, "1H"):
        indices["1H"] = next_index
        next_index += 1
    if _has_spectrum_source(compound, "13C"):
        indices["13C"] = next_index
    return indices


def _has_spectrum_source(compound: Compound, nucleus: str) -> bool:
    if nucleus == "1H":
        return bool(compound.h1_spectrum_path or compound.h1_nmr or compound.h1_image_path)
    return bool(compound.c13_spectrum_path or compound.c13_nmr or compound.c13_image_path)


def _mnova_arg(path: Path) -> str:
    return str(Path(path).resolve()).replace("\\", "/")


def _safe_token(value: str) -> str:
    safe = "".join(char if char.isascii() and (char.isalnum() or char in "._-") else "_" for char in str(value))
    return safe.strip("._-") or "item"


def _read_text(path: Path) -> str:
    encodings = ["utf-8-sig", locale.getpreferredencoding(False), "mbcs", "cp1251"]
    seen: set[str] = set()
    for encoding in encodings:
        if not encoding or encoding in seen:
            continue
        seen.add(encoding)
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return path.read_text(encoding="utf-8", errors="replace")
