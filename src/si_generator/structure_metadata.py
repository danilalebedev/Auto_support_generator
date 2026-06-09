from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

import olefile
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors


NS = {
    "o": "urn:schemas-microsoft-com:office:office",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}


@dataclass(frozen=True)
class StructureMetadata:
    formula: str = ""
    smiles: str = ""
    name: str = ""


def extract_structure_metadata_by_row(docx_path: str | Path) -> dict[int, StructureMetadata]:
    docx_path = Path(docx_path)
    with zipfile.ZipFile(docx_path, "r") as archive:
        rels = _document_relationships(archive)
        document = ET.fromstring(archive.read("word/document.xml"))
        table = document.find(".//w:tbl", NS)
        if table is None:
            return {}

        result: dict[int, StructureMetadata] = {}
        for row_index, row in enumerate(table.findall("w:tr", NS), start=1):
            ole = row.find(".//o:OLEObject", NS)
            if ole is None:
                continue
            rel_id = ole.attrib.get(f"{{{NS['r']}}}id")
            target = rels.get(rel_id or "")
            if not target:
                continue
            metadata = _metadata_from_embedding(archive.read(f"word/{target}"))
            if metadata.formula or metadata.smiles:
                result[row_index] = metadata
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


def _metadata_from_embedding(data: bytes) -> StructureMetadata:
    with olefile.OleFileIO(io.BytesIO(data)) as ole:
        cdx = ole.openstream("CONTENTS").read()

    params = Chem.CDXMLParserParams()
    params.format = Chem.CDXMLFormat.CDX
    params.sanitize = True
    params.removeHs = True
    mols = tuple(mol for mol in Chem.MolsFromCDXML(io.BytesIO(cdx).read(), params) if mol)
    if not mols:
        return StructureMetadata()

    mol = mols[0]
    formula = rdMolDescriptors.CalcMolFormula(mol)
    smiles = Chem.MolToSmiles(mol, isomericSmiles=True)
    return StructureMetadata(formula=formula, smiles=smiles)
