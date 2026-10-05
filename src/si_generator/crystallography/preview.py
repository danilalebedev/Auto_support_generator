from __future__ import annotations

from collections import deque
from pathlib import Path
import math
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .fields import field_value
from .model import CifRecord, cif_number, clean_cif_value


COVALENT_RADII = {
    "H": 0.31, "B": 0.84, "C": 0.76, "N": 0.71, "O": 0.66, "F": 0.57,
    "P": 1.07, "S": 1.05, "Cl": 1.02, "Br": 1.20, "I": 1.39,
    "Li": 1.28, "Na": 1.66, "K": 2.03, "Mg": 1.41, "Ca": 1.76,
    "Ti": 1.60, "V": 1.53, "Cr": 1.39, "Mn": 1.39, "Fe": 1.32, "Co": 1.26,
    "Ni": 1.24, "Cu": 1.32, "Zn": 1.22, "Zr": 1.75, "Mo": 1.54, "Ru": 1.46,
    "Rh": 1.42, "Pd": 1.39, "Ag": 1.45, "Cd": 1.44, "Pt": 1.36, "Au": 1.36,
    "Hg": 1.32, "Al": 1.21, "Si": 1.11, "Sn": 1.39, "Pb": 1.46,
}

COLORS = {
    "H": "#f5f5f5", "C": "#60656b", "N": "#3155c6", "O": "#d83232", "F": "#45a853",
    "P": "#e58b28", "S": "#e2c329", "Cl": "#3baa54", "Br": "#8c3429", "I": "#6a3c96",
    "Cu": "#b87333", "Zn": "#7a86a0", "Fe": "#b24b2c", "Co": "#2a62ad", "Ni": "#4b9b66",
    "Pd": "#9aa4ad", "Pt": "#949ca8", "Au": "#d3a51f", "Ag": "#b7bdc7", "Hg": "#8790a5",
}

METALS = {"Li", "Na", "K", "Mg", "Ca", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Zr", "Mo", "Ru", "Rh", "Pd", "Ag", "Cd", "Pt", "Au", "Hg", "Al", "Sn", "Pb"}


def _element(value: str | None, label: str) -> str:
    candidate = clean_cif_value(value) or re.sub(r"[^A-Za-z]", "", label)
    match = re.match(r"([A-Z][a-z]?)", candidate)
    return match.group(1) if match else "C"


def _cell_matrix(record: CifRecord) -> np.ndarray:
    a, b, c, alpha, beta, gamma = [cif_number(field_value(record, key)) for key in ("a", "b", "c", "alpha", "beta", "gamma")]
    if any(value is None for value in (a, b, c, alpha, beta, gamma)):
        raise ValueError(f"{record.display_label}: incomplete unit-cell parameters")
    ca, cb, cg = [math.cos(math.radians(value)) for value in (alpha, beta, gamma)]
    sg = math.sin(math.radians(gamma))
    if abs(sg) < 1e-9:
        raise ValueError(f"{record.display_label}: invalid gamma angle")
    c_x = c * cb
    c_y = c * (ca - cb * cg) / sg
    c_z = math.sqrt(max(c * c - c_x * c_x - c_y * c_y, 0))
    return np.array([[a, b * cg, c_x], [0, b * sg, c_y], [0, 0, c_z]], dtype=float)


def _atoms(record: CifRecord) -> tuple[list[str], list[str], np.ndarray]:
    rows = record.rows_with("_atom_site_fract_x", "_atom_site.fract_x")
    labels: list[str] = []
    elements: list[str] = []
    positions: list[list[float]] = []
    for row in rows:
        label = clean_cif_value(row.get("_atom_site_label") or row.get("_atom_site.label"))
        x = cif_number(row.get("_atom_site_fract_x") or row.get("_atom_site.fract_x"))
        y = cif_number(row.get("_atom_site_fract_y") or row.get("_atom_site.fract_y"))
        z = cif_number(row.get("_atom_site_fract_z") or row.get("_atom_site.fract_z"))
        occupancy = cif_number(row.get("_atom_site_occupancy") or row.get("_atom_site.occupancy"))
        if label and None not in (x, y, z) and (occupancy is None or occupancy > 0):
            labels.append(label)
            elements.append(_element(row.get("_atom_site_type_symbol") or row.get("_atom_site.type_symbol"), label))
            positions.append([x, y, z])
    if not positions:
        raise ValueError(f"{record.display_label}: no atom-site coordinates")
    return labels, elements, np.asarray(positions, dtype=float)


def _bond_graph(elements: list[str], fractions: np.ndarray, matrix: np.ndarray) -> tuple[list[tuple[int, int, np.ndarray]], list[list[int]]]:
    edges: list[tuple[int, int, np.ndarray]] = []
    adjacency = [[] for _ in elements]
    for left in range(len(elements)):
        for right in range(left + 1, len(elements)):
            delta = fractions[right] - fractions[left]
            translation = -np.rint(delta)
            distance = np.linalg.norm(matrix @ (delta + translation))
            r_left = COVALENT_RADII.get(elements[left], 0.85)
            r_right = COVALENT_RADII.get(elements[right], 0.85)
            scale = 1.35 if elements[left] in METALS or elements[right] in METALS else 1.22
            cutoff = scale * (r_left + r_right) + 0.12
            if 0.45 < distance <= cutoff:
                edges.append((left, right, translation.astype(int)))
                adjacency[left].append(right)
                adjacency[right].append(left)
    return edges, adjacency


def _largest_component(adjacency: list[list[int]], elements: list[str]) -> list[int]:
    seen: set[int] = set()
    components: list[list[int]] = []
    for start in range(len(adjacency)):
        if start in seen:
            continue
        queue = [start]
        seen.add(start)
        component = []
        while queue:
            node = queue.pop()
            component.append(node)
            for neighbour in adjacency[node]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    queue.append(neighbour)
        components.append(component)
    return max(components, key=lambda component: (sum(elements[index] != "H" for index in component), len(component)))


def generate_preview(record: CifRecord, path: str | Path, include_hydrogen: bool = False) -> Path:
    """Create a projected ball-and-stick preview, not a thermal-ellipsoid drawing."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    labels, elements, fractions = _atoms(record)
    matrix = _cell_matrix(record)
    edges, adjacency = _bond_graph(elements, fractions, matrix)
    selected = set(range(len(elements)))
    if not include_hydrogen:
        selected = {index for index in selected if elements[index] != "H"}
    selected_edges = [(a, b, t) for a, b, t in edges if a in selected and b in selected]

    if not selected:
        raise ValueError(f"{record.display_label}: no non-hydrogen coordinates")
    translations: dict[int, np.ndarray] = {min(selected): np.zeros(3, dtype=int)}
    queue: deque[int] = deque(translations)
    edge_lookup: dict[tuple[int, int], np.ndarray] = {}
    for left, right, translation in selected_edges:
        edge_lookup[(left, right)] = translation
        edge_lookup[(right, left)] = -translation
    while queue or len(translations) < len(selected):
        if not queue:
            root = min(selected - translations.keys())
            translations[root] = np.zeros(3, dtype=int)
            queue.append(root)
        left = queue.popleft()
        for right in adjacency[left]:
            if right not in selected or right in translations or (left, right) not in edge_lookup:
                continue
            translations[right] = translations[left] + edge_lookup[(left, right)]
            queue.append(right)
    for index in selected:
        translations.setdefault(index, np.zeros(3, dtype=int))

    ordered = sorted(selected)
    cartesian = np.asarray([matrix @ (fractions[index] + translations[index]) for index in ordered])
    cartesian -= cartesian.mean(axis=0)
    _, _, axes = np.linalg.svd(cartesian, full_matrices=False)
    if len(ordered) < 3:
        axes = np.eye(3)
    projected = cartesian @ axes[:2].T
    lookup = {atom: position for atom, position in zip(ordered, projected, strict=True)}

    fig, ax = plt.subplots(figsize=(8, 5.6), dpi=300)
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")
    for left, right, _ in selected_edges:
        p1, p2 = lookup[left], lookup[right]
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color="#4a4a4a", linewidth=1.8, zorder=1)
    depth = cartesian @ axes[2] if axes.shape[0] > 2 else np.zeros(len(ordered))
    for atom, z_depth in sorted(zip(ordered, depth, strict=True), key=lambda pair: pair[1]):
        x, y = lookup[atom]
        element = elements[atom]
        size = 220 if element in METALS else (145 if element != "H" else 65)
        ax.scatter([x], [y], s=size, color=COLORS.get(element, "#b07cc6"), edgecolor="#222222", linewidth=0.6, zorder=2)
        if element != "C" or len(ordered) <= 45:
            ax.text(x + 0.07, y + 0.07, labels[atom], fontsize=6.3, color="#181818", zorder=3)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.margins(0.12)
    fig.savefig(target, transparent=True, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return target
