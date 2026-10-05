"""CDXML geometry, adapted from the author's ChemStyleGrid core/benchmark.

Keep native structures and Ring Fill objects; never reconstruct their chemistry.
RDKit supplies the MCS, and proper rigid rotations preserve wedge stereobonds.
"""
from __future__ import annotations

import copy
import math
import re
import textwrap
from dataclasses import dataclass

import numpy as np
from lxml import etree as ET
from rdkit import Chem
from rdkit.Chem import rdFMCS


COORDINATES = {"BoundingBox", "p", "Center3D", "MajorAxisEnd3D", "MinorAxisEnd3D", "Head3D", "Tail3D"}
REFERENCES = {"B", "E", "BasisObjects", "SupersededBy", "BondCircularOrdering", "Attachments"}


def parse(xml: str):
    root = ET.fromstring(xml.encode("utf-8"), ET.XMLParser(resolve_entities=False, load_dtd=False, no_network=True))
    # ChemStyleGrid's CDX converter uses lowercase; ChemDraw's CDXML reader
    # silently drops that spelling. Native exports use this case-sensitive tag.
    for area in root.iter("coloredmoleculararea"):
        area.tag = "ColoredMolecularArea"
    return root


def fmt(value):
    return f"{float(value):.4f}".rstrip("0").rstrip(".") or "0"


def values(text):
    return [float(x) for x in text.split()]


def bounds(element):
    boxes = []
    for child in element.iter():
        if child.tag in {"fragment", "group"}:
            continue
        if child.get("BoundingBox"):
            boxes.append(values(child.get("BoundingBox")))
        elif child.tag == "n" and child.get("p"):
            x, y = values(child.get("p"))[:2]
            boxes.append([x - 4, y - 4, x + 4, y + 4])
    if not boxes:
        raise ValueError("Scope structure has no coordinates.")
    return min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)


def transform(element, matrix, offset):
    for child in element.iter():
        for key in COORDINATES.intersection(child.attrib):
            coords = values(child.get(key))
            if key == "BoundingBox" and len(coords) == 4:
                x1, y1, x2, y2 = coords
                corners = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]]) @ matrix + offset
                coords = [*corners.min(axis=0), *corners.max(axis=0)]
            elif len(coords) >= 2:
                coords[:2] = np.array(coords[:2]) @ matrix + offset
            child.set(key, " ".join(fmt(v) for v in coords))


def translate(element, x, y):
    transform(element, np.eye(2), np.array([x, y]))


@dataclass
class Drawing:
    group: ET._Element
    mol: object
    nodes: list


def molecule(root):
    mols = Chem.MolsFromCDXML(ET.tostring(root, encoding="unicode"))
    mols = [m for m in mols if m is not None]
    if len(mols) != 1:
        raise ValueError("Each scope cell must contain exactly one readable molecular structure.")
    return mols[0]


def mapping(reference, target):
    result = rdFMCS.FindMCS([reference.mol, target.mol], timeout=10,
                           ringMatchesRingOnly=True, completeRingsOnly=True,
                           atomCompare=rdFMCS.AtomCompare.CompareElements,
                           bondCompare=rdFMCS.BondCompare.CompareOrder)
    if result.canceled or result.numAtoms < 3:
        return {}
    query = Chem.MolFromSmarts(result.smartsString)
    return dict(zip(reference.mol.GetSubstructMatch(query), target.mol.GetSubstructMatch(query)))


def align(reference, target):
    atom_map = mapping(reference, target)
    if len(atom_map) < 3:
        return atom_map
    source = np.array([values(target.nodes[i].get("p"))[:2] for i in atom_map.values()])
    dest = np.array([values(reference.nodes[i].get("p"))[:2] for i in atom_map])
    u, _, vt = np.linalg.svd((source - source.mean(axis=0)).T @ (dest - dest.mean(axis=0)))
    correction = np.diag([1.0, np.linalg.det(u @ vt)])
    rotation = u @ correction @ vt
    # Rotate around the common-core centroid; do not reflect chiral drawings.
    transform(target.group, rotation, dest.mean(axis=0) - source.mean(axis=0) @ rotation)
    return atom_map


def copy_ring_fills(reference, target, atom_map, next_id):
    """ChemStyleGrid Ring Fill rule: BasisObjects belong to the target fragment."""
    ids = {reference.nodes[r].get("id"): target.nodes[t].get("id") for r, t in atom_map.items()}
    target_bonds = {frozenset((b.get("B"), b.get("E"))): b.get("id") for b in target.group.iter("b")}
    for bond in reference.group.iter("b"):
        endpoints = [ids.get(bond.get("B")), ids.get(bond.get("E"))]
        if all(endpoints):
            mapped = target_bonds.get(frozenset(endpoints))
            if mapped:
                ids[bond.get("id")] = mapped
    copied = 0
    existing = {frozenset(g.get("BasisObjects", "").split()) for g in target.group.iter("ColoredMolecularArea")}
    for fill in reference.group.iter("ColoredMolecularArea"):
        basis = fill.get("BasisObjects", "").split()
        if len(basis) < 3 or not all(i in ids for i in basis):
            continue
        mapped = [ids[i] for i in basis]
        if frozenset(mapped) in existing:
            continue
        clone = copy.deepcopy(fill)
        clone.set("id", str(next_id()))
        clone.set("BasisObjects", " ".join(mapped))
        fragment = target.group.find(".//fragment")
        fragment.append(clone)
        copied += 1
    return copied


class Canvas:
    def __init__(self):
        self.serial = 0
        self.root = ET.Element("CDXML", BondLength="14.4", LineWidth="0.6", BoldWidth="2",
                               LabelSize="10", LabelFace="96", CaptionSize="10", LabelFont="3", CaptionFont="3")
        self.colors = ET.SubElement(self.root, "colortable")
        ET.SubElement(self.colors, "color", r="1", g="1", b="1")
        ET.SubElement(self.colors, "color", r="0", g="0", b="0")
        self.fonts = ET.SubElement(self.root, "fonttable")
        ET.SubElement(self.fonts, "font", id="3", charset="iso-8859-1", name="Arial")
        self.page = ET.SubElement(self.root, "page", id=str(self.next_id()), BoundingBox="0 0 600 800")

    def next_id(self):
        self.serial += 1
        return self.serial

    def drawing(self, xml):
        source = parse(xml)
        mol = molecule(source)
        group = ET.SubElement(self.page, "group", id=str(self.next_id()))
        page = source.find("page")
        if page is None:
            raise ValueError("CDXML page is missing.")
        for element in page:
            if element.tag in {"fragment", "group", "graphic", "ColoredMolecularArea"}:
                group.append(copy.deepcopy(element))
        color_map = {"0": "0", "1": "1"}
        for i, color in enumerate(source.findall("colortable/color"), 2):
            attrs = dict(color.attrib)
            candidates = list(self.colors)
            match = next((j + 2 for j, c in enumerate(candidates) if dict(c.attrib) == attrs), None)
            if match is None:
                self.colors.append(copy.deepcopy(color))
                match = len(self.colors) + 1
            color_map[str(i)] = str(match)
        font_map = {}
        for font in source.findall("fonttable/font"):
            clone = copy.deepcopy(font)
            new = str(len(self.fonts) + 4)
            font_map[font.get("id")] = new
            clone.set("id", new)
            self.fonts.append(clone)
        id_map = {e.get("id"): str(self.next_id()) for e in group.iter() if e.get("id")}
        node_by_original = {n.get("id"): n for n in group.iter("n")}
        nodes = []
        for atom in mol.GetAtoms():
            original = str(atom.GetIntProp("_CDX_ATOM_ID")) if atom.HasProp("_CDX_ATOM_ID") else ""
            node = node_by_original.get(original)
            if node is None:
                # The Revvity-backed RDKit parser omits CDX IDs but retains
                # absolute drawing coordinates at 1.5 units per bond.
                point = mol.GetConformer().GetAtomPosition(atom.GetIdx())
                expected = np.array([point.x, -point.y]) * float(source.get("BondLength", "14.4")) / 1.5
                candidates = [n for n in node_by_original.values() if n.get("NodeType", "Element") == "Element" and n.get("p")]
                node = min(candidates, key=lambda n: np.linalg.norm(np.array(values(n.get("p"))[:2]) - expected))
                if np.linalg.norm(np.array(values(node.get("p"))[:2]) - expected) > 0.15:
                    raise ValueError("Cannot match ChemDraw coordinates to the molecular graph.")
            nodes.append(node)
        for element in group.iter():
            if element.get("id"):
                old_id = element.get("id")
                element.set("id", str(self.next_id()) if old_id == "0" else id_map[old_id])
            for key in REFERENCES.intersection(element.attrib):
                element.set(key, " ".join(id_map.get(i, i) for i in element.get(key).split()))
            for key in ("color", "bgcolor"):
                if element.get(key):
                    element.set(key, color_map.get(element.get(key), element.get(key)))
            if element.get("font") in font_map:
                element.set("font", font_map[element.get("font")])
        scale = 14.4 / float(source.get("BondLength", "14.4"))
        transform(group, np.eye(2) * scale, np.zeros(2))
        return Drawing(group, mol, nodes)

    def text(self, text, x, y, bold=False, size=10, chemical=False):
        element = ET.SubElement(self.page, "t", id=str(self.next_id()), p=f"{fmt(x)} {fmt(y)}",
                                Justification="Center", InterpretChemically="no")
        tokens = re.split(r"((?:[A-Z][a-z]?\d*){2,})", text) if chemical else [text]
        for token in tokens:
            formula = chemical and re.fullmatch(r"(?:[A-Z][a-z]?\d*){2,}", token)
            for part in re.findall(r"\d+|\D+", token) if formula else [token]:
                if part:
                    face = "32" if formula and part.isdigit() else "1" if bold else "0"
                    ET.SubElement(element, "s", font="3", size=str(size), face=face).text = part
        return element

    def rich_text(self, parts, x, y, size=10):
        element = ET.SubElement(self.page, "t", id=str(self.next_id()), p=f"{fmt(x)} {fmt(y)}",
                                Justification="Center", InterpretChemically="no")
        for text, bold in parts:
            ET.SubElement(element, "s", font="3", size=str(size), face="1" if bold else "0").text = text
        return element

    def line(self, left, right, y, arrow=False):
        graphic = ET.SubElement(self.page, "graphic", id=str(self.next_id()), GraphicType="Line",
                                BoundingBox=f"{fmt(right)} {fmt(y)} {fmt(left)} {fmt(y)}", LineWidth="0.6")
        if arrow:
            graphic.set("ArrowType", "FullHead")
            graphic.set("HeadSize", "1000")
        return graphic

    def xml(self, width, height):
        box = f"0 0 {fmt(width)} {fmt(height)}"
        self.root.set("BoundingBox", box)
        self.page.set("BoundingBox", box)
        return ET.tostring(self.root, encoding="unicode", pretty_print=True)


def make_page(products, reaction, conditions, title, columns=4):
    canvas = Canvas()
    drawings = [canvas.drawing(p["cdxml"]) for p in products]
    reference = max(drawings, key=lambda d: (len(d.group.findall(".//ColoredMolecularArea")),
                                           sum("color" in e.attrib for e in d.group.iter())))
    mappings = []
    for drawing in drawings:
        atom_map = {} if drawing is reference else align(reference, drawing)
        for r, t in atom_map.items():
            if reference.nodes[r].get("color"):
                drawing.nodes[t].set("color", reference.nodes[r].get("color"))
        node_map = {reference.nodes[r].get("id"): drawing.nodes[t].get("id") for r, t in atom_map.items()}
        bonds = {frozenset((b.get("B"), b.get("E"))): b for b in drawing.group.iter("b")}
        for bond in reference.group.iter("b"):
            target_bond = bonds.get(frozenset((node_map.get(bond.get("B")), node_map.get(bond.get("E")))))
            if target_bond is not None and bond.get("color"):
                target_bond.set("color", bond.get("color"))
        copy_ring_fills(reference, drawing, atom_map, canvas.next_id)
        mappings.append(atom_map)
    boxes = [bounds(d.group) for d in drawings]
    reference_box = bounds(reference.group)
    anchor_y = (reference_box[1] + reference_box[3]) / 2
    above_core = max(anchor_y - b[1] for b in boxes)
    below_core = max(b[3] - anchor_y for b in boxes)
    columns = min(columns, len(products))
    cell_width = max(125.0, max(b[2] - b[0] for b in boxes) + 24)
    cell_height = above_core + below_core + 46
    width = max(520, columns * cell_width + 32)
    reactants = [canvas.drawing(xml) for xml in reaction["reactants"]]
    product = canvas.drawing(reaction["product"])
    participants = reactants + [product]
    rb = [bounds(d.group) for d in participants]
    condition_lines = [line for text in conditions.splitlines() for line in textwrap.wrap(text, 38)]
    reagent_lines = [line for text in reaction["reagents"] for line in textwrap.wrap(text, 38)]
    title_lines = textwrap.wrap(title, 72) or ["Reaction and compound scope"]
    arrow_width = max(130, 5 * max([len(t) for t in condition_lines + reagent_lines] or [0]))
    rw = sum(b[2] - b[0] for b in rb) + 28 * max(0, len(reactants) - 1) + arrow_width + 28
    width = max(width, rw + 32)
    heading_height = 18 + 15 * (len(title_lines) - 1)
    y = heading_height + max(36 + max(b[3] - b[1] for b in rb) / 2, 28 + 12 * len(reagent_lines))
    x = (width - rw) / 2
    for i, (drawing, box) in enumerate(zip(participants, rb)):
        if i == len(reactants):
            canvas.line(x, x + arrow_width, y, arrow=True)
            above = reagent_lines
            for j, line in enumerate(above):
                canvas.text(line, x + arrow_width / 2, y - 9 - 12 * (len(above) - j - 1), size=9, chemical=True)
            for j, line in enumerate(condition_lines):
                canvas.text(line, x + arrow_width / 2, y + 16 + 12 * j, size=9, chemical=True)
            x += arrow_width + 14
        translate(drawing.group, x - box[0], y - (box[1] + box[3]) / 2)
        x += box[2] - box[0]
        if i < len(reactants) - 1:
            canvas.text("+", x + 14, y + 3, size=12)
            x += 28
        elif i == len(reactants) - 1:
            x += 14
    bottom = max(bounds(d.group)[3] for d in participants)
    divider = max(bottom + 24, y + 30 + 12 * len(condition_lines))
    for i, line in enumerate(title_lines):
        canvas.text(line, width / 2, 18 + 15 * i, bold=True, size=12)
    canvas.line(16, width - 16, divider)
    top = divider + 24
    for i, (p, drawing, box) in enumerate(zip(products, drawings, boxes)):
        row, col = divmod(i, columns)
        count = min(columns, len(products) - row * columns)
        cx = width / 2 + (col - (count - 1) / 2) * cell_width
        # All labels share a baseline, independent of substituent height.
        cy = top + row * cell_height + above_core
        translate(drawing.group, cx - (box[0] + box[2]) / 2, cy - anchor_y)
        label_y = top + row * cell_height + cell_height - 25
        canvas.rich_text(((p["number"], True), (f", {p['yield']}", False)), cx, label_y)
    height = top + math.ceil(len(products) / columns) * cell_height
    return canvas.xml(width, height), {"width": width, "height": height, "columns": columns,
                                      "mapped_atoms": [len(m) for m in mappings]}
