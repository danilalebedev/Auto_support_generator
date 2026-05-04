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
    return StructureMetadata(formula=formula, smiles=smiles, name=_generate_name(mol))


def _generate_name(mol: Chem.Mol) -> str:
    cinnamate_name = _methyl_cinnamate_name(mol)
    if cinnamate_name:
        return cinnamate_name
    return ""


def _methyl_cinnamate_name(mol: Chem.Mol) -> str:
    rings = [ring for ring in mol.GetRingInfo().AtomRings() if len(ring) == 6 and all(mol.GetAtomWithIdx(i).GetIsAromatic() for i in ring)]
    if len(rings) != 1:
        return ""

    ring = set(rings[0])
    acrylate_atom = _ring_atom_with_acrylate(mol, ring)
    bromomethyl_atom = _ring_atom_with_bromomethyl(mol, ring)
    if acrylate_atom is None or bromomethyl_atom is None:
        return ""

    paths = _ring_paths(mol, ring, acrylate_atom, bromomethyl_atom)
    if not paths:
        return ""
    # Use the numbering direction where the bromomethyl group is ortho when possible.
    main_path = min(paths, key=len)
    other_path = [acrylate_atom] + [idx for idx in paths[1] if idx != acrylate_atom] if paths[0] == main_path and len(paths) > 1 else paths[0]
    numbering = _ring_numbering(mol, ring, acrylate_atom, bromomethyl_atom, main_path, other_path)

    substituents = []
    for atom_idx, locant in numbering.items():
        if atom_idx == acrylate_atom:
            continue
        label = _substituent_label(mol, atom_idx, ring)
        if label:
            substituents.append((locant, label))

    substituents.sort()
    prefix = "-".join(f"{locant}-({label})" if label == "bromomethyl" else f"{locant}-{label}" for locant, label in substituents)
    return f"Methyl (E)-3-({prefix}phenyl)acrylate" if prefix else "Methyl (E)-3-phenylacrylate"


def _ring_atom_with_acrylate(mol: Chem.Mol, ring: set[int]) -> int | None:
    for atom_idx in ring:
        atom = mol.GetAtomWithIdx(atom_idx)
        for nbr in atom.GetNeighbors():
            if nbr.GetIdx() in ring or nbr.GetAtomicNum() != 6:
                continue
            if _has_ester_chain(mol, nbr.GetIdx(), atom_idx):
                return atom_idx
    return None


def _has_ester_chain(mol: Chem.Mol, start: int, ring_atom: int) -> bool:
    start_atom = mol.GetAtomWithIdx(start)
    for alkene_neighbor in start_atom.GetNeighbors():
        if alkene_neighbor.GetIdx() == ring_atom or alkene_neighbor.GetAtomicNum() != 6:
            continue
        bond = mol.GetBondBetweenAtoms(start, alkene_neighbor.GetIdx())
        if bond.GetBondTypeAsDouble() < 1.5:
            continue
        for carbonyl in alkene_neighbor.GetNeighbors():
            if carbonyl.GetIdx() == start or carbonyl.GetAtomicNum() != 6:
                continue
            carbonyl_bond = mol.GetBondBetweenAtoms(alkene_neighbor.GetIdx(), carbonyl.GetIdx())
            if carbonyl_bond.GetBondTypeAsDouble() < 1.5 and _is_ester_carbonyl(mol, carbonyl.GetIdx(), alkene_neighbor.GetIdx()):
                return True
    return False


def _is_ester_carbonyl(mol: Chem.Mol, carbon_idx: int, alkene_idx: int) -> bool:
    atom = mol.GetAtomWithIdx(carbon_idx)
    has_double_o = False
    has_single_o_c = False
    for nbr in atom.GetNeighbors():
        if nbr.GetIdx() == alkene_idx:
            continue
        bond = mol.GetBondBetweenAtoms(carbon_idx, nbr.GetIdx())
        if nbr.GetAtomicNum() == 8 and bond.GetBondTypeAsDouble() > 1.5:
            has_double_o = True
        if nbr.GetAtomicNum() == 8 and bond.GetBondTypeAsDouble() < 1.5:
            has_single_o_c = any(n.GetAtomicNum() == 6 for n in nbr.GetNeighbors() if n.GetIdx() != carbon_idx)
    return has_double_o and has_single_o_c


def _ring_atom_with_bromomethyl(mol: Chem.Mol, ring: set[int]) -> int | None:
    for atom_idx in ring:
        atom = mol.GetAtomWithIdx(atom_idx)
        for nbr in atom.GetNeighbors():
            if nbr.GetIdx() in ring or nbr.GetAtomicNum() != 6:
                continue
            if any(n.GetAtomicNum() == 35 for n in nbr.GetNeighbors()):
                return atom_idx
    return None


def _ring_paths(mol: Chem.Mol, ring: set[int], start: int, end: int) -> list[list[int]]:
    neighbors = {idx: [n.GetIdx() for n in mol.GetAtomWithIdx(idx).GetNeighbors() if n.GetIdx() in ring] for idx in ring}
    paths: list[list[int]] = []

    def walk(path: list[int]) -> None:
        current = path[-1]
        if current == end:
            paths.append(path[:])
            return
        for nxt in neighbors[current]:
            if nxt not in path:
                walk(path + [nxt])

    walk([start])
    return sorted(paths, key=len)[:2]


def _ring_numbering(
    mol: Chem.Mol,
    ring: set[int],
    acrylate_atom: int,
    bromomethyl_atom: int,
    short_path: list[int],
    fallback_path: list[int],
) -> dict[int, int]:
    if len(short_path) > 1 and short_path[1] == bromomethyl_atom:
        ordered = _complete_ring_order(mol, ring, acrylate_atom, short_path[1])
    else:
        ordered = _complete_ring_order(mol, ring, acrylate_atom, fallback_path[1])
    return {atom_idx: locant for locant, atom_idx in enumerate(ordered, start=1)}


def _complete_ring_order(mol: Chem.Mol, ring: set[int], start: int, second: int) -> list[int]:
    ordered = [start, second]
    while len(ordered) < len(ring):
        current = ordered[-1]
        previous = ordered[-2]
        candidates = [n.GetIdx() for n in mol.GetAtomWithIdx(current).GetNeighbors() if n.GetIdx() in ring and n.GetIdx() != previous]
        nxt = next((idx for idx in candidates if idx not in ordered), None)
        if nxt is None:
            break
        ordered.append(nxt)
    return ordered


def _substituent_label(mol: Chem.Mol, atom_idx: int, ring: set[int]) -> str:
    labels = []
    for nbr in mol.GetAtomWithIdx(atom_idx).GetNeighbors():
        if nbr.GetIdx() in ring:
            continue
        atomic_num = nbr.GetAtomicNum()
        if atomic_num == 9:
            labels.append("fluoro")
        elif atomic_num == 17:
            labels.append("chloro")
        elif atomic_num == 35:
            labels.append("bromo")
        elif atomic_num == 53:
            labels.append("iodo")
        elif atomic_num == 7 and _is_nitro(mol, nbr.GetIdx()):
            labels.append("nitro")
        elif atomic_num == 6 and any(n.GetAtomicNum() == 35 for n in nbr.GetNeighbors()):
            labels.append("bromomethyl")
    return labels[0] if labels else ""


def _is_nitro(mol: Chem.Mol, atom_idx: int) -> bool:
    atom = mol.GetAtomWithIdx(atom_idx)
    return atom.GetAtomicNum() == 7 and sum(1 for n in atom.GetNeighbors() if n.GetAtomicNum() == 8) >= 2
