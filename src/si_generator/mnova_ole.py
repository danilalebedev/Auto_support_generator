from __future__ import annotations

import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "o": "urn:schemas-microsoft-com:office:office",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "v": "urn:schemas-microsoft-com:vml",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}

MNOVA_DOCUMENT_CLSID = "{24279019-4929-4F35-A663-68EB78A1D139}"
MNOVA_PROG_ID = "MestReNova.Document.1"
MNOVA_COMP_OBJ = bytes.fromhex(
    "0100feff030a0000ffffffff199027242949354fa66368eb78a1d139"
    "140000004d65737452654e6f766120446f63756d656e7400"
    "120000006170706c69636174696f6e2f6d6e6f766100"
    "160000004d65737452654e6f76612e446f63756d656e742e3100"
    "f439b271000000000000000000000000"
)
MNOVA_OLE_STREAM = bytes.fromhex("0100000200000000000000000000000000000000")
MNOVA_OBJ_INFO = bytes.fromhex("000003000d00")
MNOVA_HEADER = bytes.fromhex("00000440000002f70000006000000060")

STGM_CREATE = 0x00001000
STGM_READWRITE = 0x00000002
STGM_SHARE_EXCLUSIVE = 0x00000010


@dataclass(frozen=True)
class MnovaOleTarget:
    marker: str
    mnova_path: Path
    preview_path: Path
    width_pt: float
    height_pt: float


def embed_mnova_ole_objects(docx_path: str | Path, targets: list[MnovaOleTarget]) -> None:
    if not targets:
        return

    docx_path = Path(docx_path)
    fd, tmp_name = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    Path(tmp_name).unlink(missing_ok=True)

    with zipfile.ZipFile(docx_path, "r") as source_zip:
        document = ET.fromstring(source_zip.read("word/document.xml"))
        rels = ET.fromstring(source_zip.read("word/_rels/document.xml.rels"))
        content_types = ET.fromstring(source_zip.read("[Content_Types].xml"))
        existing_names = set(source_zip.namelist())
        rel_counter = _next_rel_counter(rels)
        object_counter = _next_object_counter(existing_names)
        extra_files: dict[str, bytes] = {}

        for target in targets:
            run = _run_with_text(document, target.marker)
            if run is None:
                continue

            preview_ext = target.preview_path.suffix.lower().lstrip(".") or "png"
            preview_name = f"word/media/mnova_spectrum_{object_counter}.{preview_ext}"
            ole_name = f"word/embeddings/mnova_spectrum_{object_counter}.bin"
            shape_id = f"_x0000_i{12000 + object_counter}"
            object_id = f"_{1844350000 + object_counter}"
            object_counter += 1

            image_rid = f"rIdMnova{rel_counter}"
            rel_counter += 1
            ole_rid = f"rIdMnova{rel_counter}"
            rel_counter += 1

            extra_files[preview_name] = target.preview_path.read_bytes()
            extra_files[ole_name] = build_mnova_ole_storage(target.mnova_path.read_bytes())

            _add_relationship(
                rels,
                image_rid,
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
                preview_name.removeprefix("word/"),
            )
            _add_relationship(
                rels,
                ole_rid,
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject",
                ole_name.removeprefix("word/"),
            )
            _ensure_default_content_type(content_types, preview_ext, _image_content_type(preview_ext))
            _ensure_default_content_type(
                content_types,
                "bin",
                "application/vnd.openxmlformats-officedocument.oleObject",
            )

            object_xml = _mnova_object_xml(
                image_rid=image_rid,
                ole_rid=ole_rid,
                shape_id=shape_id,
                object_id=object_id,
                width_pt=target.width_pt,
                height_pt=target.height_pt,
            )
            _replace_run_text_with_object(run, object_xml)

        with zipfile.ZipFile(tmp_name, "w", zipfile.ZIP_DEFLATED) as out_zip:
            for item in source_zip.infolist():
                if item.filename in {"word/document.xml", "word/_rels/document.xml.rels", "[Content_Types].xml"}:
                    continue
                out_zip.writestr(item, source_zip.read(item.filename))
            _drop_stale_ignorable_prefixes(document)
            out_zip.writestr("word/document.xml", ET.tostring(document, encoding="utf-8", xml_declaration=True))
            out_zip.writestr("word/_rels/document.xml.rels", ET.tostring(rels, encoding="utf-8", xml_declaration=True))
            out_zip.writestr("[Content_Types].xml", ET.tostring(content_types, encoding="utf-8", xml_declaration=True))
            for name, data in extra_files.items():
                out_zip.writestr(name, data)

    Path(tmp_name).replace(docx_path)


def build_mnova_ole_storage(mnova_contents: bytes) -> bytes:
    import pythoncom
    import pywintypes

    fd, tmp_name = tempfile.mkstemp(suffix=".bin")
    os.close(fd)
    tmp_path = Path(tmp_name)
    tmp_path.unlink(missing_ok=True)
    try:
        flags = STGM_CREATE | STGM_READWRITE | STGM_SHARE_EXCLUSIVE
        storage = pythoncom.StgCreateDocfile(str(tmp_path), flags, 0)
        try:
            pythoncom.WriteClassStg(storage, pywintypes.IID(MNOVA_DOCUMENT_CLSID))
            _write_storage_stream(storage, "\x01CompObj", MNOVA_COMP_OBJ)
            _write_storage_stream(storage, "\x01Ole", MNOVA_OLE_STREAM)
            _write_storage_stream(storage, "\x03ObjInfo", MNOVA_OBJ_INFO)
            _write_storage_stream(storage, "MNOVA-CONTENTS", mnova_contents)
            _write_storage_stream(storage, "MNOVA-HEADER", MNOVA_HEADER)
            storage.Commit(0)
        finally:
            storage = None
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)


def _write_storage_stream(storage, name: str, data: bytes) -> None:
    flags = STGM_CREATE | STGM_READWRITE | STGM_SHARE_EXCLUSIVE
    stream = storage.CreateStream(name, flags, 0, 0)
    try:
        stream.Write(data)
        stream.Commit(0)
    finally:
        stream = None


def _mnova_object_xml(
    *,
    image_rid: str,
    ole_rid: str,
    shape_id: str,
    object_id: str,
    width_pt: float,
    height_pt: float,
) -> ET.Element:
    width_text = f"{width_pt:.2f}".rstrip("0").rstrip(".")
    height_text = f"{height_pt:.2f}".rstrip("0").rstrip(".")
    dxa_orig = str(round(width_pt * 20))
    dya_orig = str(round(height_pt * 20))
    xml = f"""
<w:object xmlns:w="{NS['w']}" xmlns:v="{NS['v']}" xmlns:o="{NS['o']}" xmlns:r="{NS['r']}" w:dxaOrig="{dxa_orig}" w:dyaOrig="{dya_orig}">
  <v:shapetype id="_x0000_t75" coordsize="21600,21600" o:spt="75" o:preferrelative="t" path="m@4@5l@4@11@9@11@9@5xe" filled="f" stroked="f">
    <v:stroke joinstyle="miter"/>
    <v:formulas>
      <v:f eqn="if lineDrawn pixelLineWidth 0"/>
      <v:f eqn="sum @0 1 0"/>
      <v:f eqn="sum 0 0 @1"/>
      <v:f eqn="prod @2 1 2"/>
      <v:f eqn="prod @3 21600 pixelWidth"/>
      <v:f eqn="prod @3 21600 pixelHeight"/>
      <v:f eqn="sum @0 0 1"/>
      <v:f eqn="prod @6 1 2"/>
      <v:f eqn="prod @7 21600 pixelWidth"/>
      <v:f eqn="sum @8 21600 0"/>
      <v:f eqn="prod @7 21600 pixelHeight"/>
      <v:f eqn="sum @10 21600 0"/>
    </v:formulas>
    <v:path o:extrusionok="f" gradientshapeok="t" o:connecttype="rect"/>
    <o:lock v:ext="edit" aspectratio="t"/>
  </v:shapetype>
  <v:shape id="{shape_id}" type="#_x0000_t75" style="width:{width_text}pt;height:{height_text}pt" o:ole="">
    <v:imagedata r:id="{image_rid}" o:title=""/>
  </v:shape>
  <o:OLEObject Type="Embed" ProgID="{MNOVA_PROG_ID}" ShapeID="{shape_id}" DrawAspect="Content" ObjectID="{object_id}" r:id="{ole_rid}"/>
</w:object>
"""
    return ET.fromstring(xml)


def preview_size_pt(preview_path: str | Path, width_pt: float) -> tuple[float, float]:
    width_px, height_px = _image_dimensions_px(Path(preview_path))
    if width_px <= 0 or height_px <= 0:
        return width_pt, width_pt * 0.70
    return width_pt, width_pt * height_px / width_px


def _image_dimensions_px(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data.startswith(b"\xff\xd8"):
        return _jpeg_dimensions_px(data)
    return 0, 0


def _jpeg_dimensions_px(data: bytes) -> tuple[int, int]:
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(data):
            break
        length = int.from_bytes(data[index : index + 2], "big")
        if length < 2 or index + length > len(data):
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            height = int.from_bytes(data[index + 3 : index + 5], "big")
            width = int.from_bytes(data[index + 5 : index + 7], "big")
            return width, height
        index += length
    return 0, 0


def _run_with_text(document: ET.Element, text: str) -> ET.Element | None:
    for run in document.findall(".//w:r", NS):
        if text in "".join(run.itertext()):
            return run
    return None


def _replace_run_text_with_object(run: ET.Element, object_xml: ET.Element) -> None:
    for child in list(run):
        run.remove(child)
    run.append(object_xml)


def _next_rel_counter(rels: ET.Element) -> int:
    max_id = 0
    for rel in rels:
        rel_id = rel.attrib.get("Id", "")
        match = re.fullmatch(r"rId(?:Mnova|SI)?(\d+)", rel_id)
        if match:
            max_id = max(max_id, int(match.group(1)))
    return max_id + 1


def _next_object_counter(names: set[str]) -> int:
    counter = 1
    while f"word/embeddings/mnova_spectrum_{counter}.bin" in names or any(
        f"word/media/mnova_spectrum_{counter}.{ext}" in names for ext in ("png", "jpg", "jpeg", "emf")
    ):
        counter += 1
    return counter


def _add_relationship(rels: ET.Element, rel_id: str, rel_type: str, target: str) -> None:
    rel = ET.SubElement(rels, f"{{{NS['rel']}}}Relationship")
    rel.set("Id", rel_id)
    rel.set("Type", rel_type)
    rel.set("Target", target)


def _ensure_default_content_type(content_types: ET.Element, extension: str, content_type: str) -> None:
    for item in content_types.findall("ct:Default", NS):
        if item.attrib.get("Extension", "").lower() == extension.lower():
            return
    default = ET.SubElement(content_types, f"{{{NS['ct']}}}Default")
    default.set("Extension", extension)
    default.set("ContentType", content_type)


def _drop_stale_ignorable_prefixes(document: ET.Element) -> None:
    ignorable_attr = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Ignorable"
    document.attrib.pop(ignorable_attr, None)


def _image_content_type(extension: str) -> str:
    normalized = extension.lower()
    if normalized == "png":
        return "image/png"
    if normalized in {"jpg", "jpeg"}:
        return "image/jpeg"
    if normalized == "emf":
        return "image/x-emf"
    return f"image/{normalized}"
