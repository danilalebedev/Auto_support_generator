from __future__ import annotations

from dataclasses import dataclass
import math
import re

from .model import CifRecord, cif_number


@dataclass(frozen=True, slots=True)
class Field:
    key: str
    en: str
    ru: str


ORGANIC_FIELDS = [
    Field("formula", "Empirical formula", "Брутто-формула"),
    Field("weight", "Formula weight", "Молекулярная масса"),
    Field("temperature", "Temperature / K", "Температура / K"),
    Field("crystal_system", "Crystal system", "Сингония"),
    Field("space_group", "Space group", "Пространственная группа"),
    Field("a", "a / Å", "a / Å"),
    Field("b", "b / Å", "b / Å"),
    Field("c", "c / Å", "c / Å"),
    Field("alpha", "α / °", "α / °"),
    Field("beta", "β / °", "β / °"),
    Field("gamma", "γ / °", "γ / °"),
    Field("volume", "V / Å³", "V / Å³"),
    Field("z", "Z", "Z"),
    Field("density", "Calculated density / Mg m⁻³", "Расчётная плотность / Mg м⁻³"),
    Field("mu", "Absorption coefficient / mm⁻¹", "Коэффициент поглощения / мм⁻¹"),
    Field("f000", "F(000)", "F(000)"),
    Field("crystal_size", "Crystal size / mm", "Размер кристалла / мм"),
    Field("radiation", "Radiation (wavelength / Å)", "Излучение (длина волны / Å)"),
    Field("instrument", "Diffractometer", "Дифрактометр"),
    Field("theta_range", "θ range for data collection / °", "Диапазон θ / °"),
    Field("index_ranges", "Index ranges", "Диапазоны индексов"),
    Field("reflections", "Reflections collected / independent / observed", "Измерено / независимо / наблюдаемо"),
    Field("rint", "Rint", "Rint"),
    Field("data_restraints_parameters", "Data / restraints / parameters", "Данные / ограничения / параметры"),
    Field("gof", "Goodness-of-fit on F²", "Фактор добротности по F²"),
    Field("r_gt", "Final R indices [I > 2σ(I)]", "R-факторы [I > 2σ(I)]"),
    Field("r_all", "R indices (all data)", "R-факторы (все данные)"),
    Field("diff", "Largest diff. peak and hole / e Å⁻³", "Макс. и мин. остаточной плотности / e Å⁻³"),
    Field("flack", "Absolute-structure parameter", "Параметр абсолютной структуры"),
]


COORDINATION_FIELDS = [
    Field("formula", "Formula", "Формула"),
    Field("weight", "M", "M"),
    Field("temperature", "T / K", "T / K"),
    Field("crystal_system", "Crystal system", "Сингония"),
    Field("space_group", "Space group", "Пространственная группа"),
    Field("a", "a / Å", "a / Å"),
    Field("b", "b / Å", "b / Å"),
    Field("c", "c / Å", "c / Å"),
    Field("alpha", "α / °", "α / °"),
    Field("beta", "β / °", "β / °"),
    Field("gamma", "γ / °", "γ / °"),
    Field("volume", "V / Å³", "V / Å³"),
    Field("z", "Z", "Z"),
    Field("density", "dcalc / g cm⁻³", "d(calc) / г см⁻³"),
    Field("crystal_size", "Crystal size / mm", "Размер кристалла / мм"),
    Field("mu", "μ / mm⁻¹", "μ / мм⁻¹"),
    Field("transmission", "Tmin / Tmax", "Tmin / Tmax"),
    Field("f000", "F(000)", "F(000)"),
    Field("theta_range", "θmin / θmax / °", "θmin / θmax / °"),
    Field("index_ranges", "h; k; l ranges", "Пределы h; k; l"),
    Field("reflections", "Measured / independent / observed", "Измерено / независимо / наблюдаемо"),
    Field("parameters", "Refined parameters", "Число уточняемых параметров"),
    Field("rint", "Rint", "Rint"),
    Field("gof", "GOF", "GOF"),
    Field("r_gt", "R1 / wR2 [I > 2σ(I)]", "R1 / wR2 [I > 2σ(I)]"),
    Field("r_all", "R1 / wR2 (all data)", "R1 / wR2 (все отражения)"),
    Field("diff", "Δρmax / Δρmin / e Å⁻³", "Δρmax / Δρmin / e Å⁻³"),
    Field("shift", "Max shift/s.u.", "Макс. сдвиг/с.о."),
]


ALIASES: dict[str, tuple[str, ...]] = {
    "formula": ("_chemical_formula_sum", "_chemical_formula_moiety", "_chemical.formula_sum"),
    "weight": ("_chemical_formula_weight", "_chemical.formula_weight"),
    "temperature": ("_diffrn_ambient_temperature", "_cell_measurement_temperature", "_diffrn.ambient_temperature"),
    "crystal_system": ("_space_group_crystal_system", "_symmetry_cell_setting", "_space_group.crystal_system"),
    "space_group": ("_space_group_name_H-M_alt", "_symmetry_space_group_name_H-M", "_space_group.name_H-M_alt"),
    "a": ("_cell_length_a", "_cell.length_a"),
    "b": ("_cell_length_b", "_cell.length_b"),
    "c": ("_cell_length_c", "_cell.length_c"),
    "alpha": ("_cell_angle_alpha", "_cell.angle_alpha"),
    "beta": ("_cell_angle_beta", "_cell.angle_beta"),
    "gamma": ("_cell_angle_gamma", "_cell.angle_gamma"),
    "volume": ("_cell_volume", "_cell.volume"),
    "z": ("_cell_formula_units_Z", "_cell.formula_units_Z"),
    "density": ("_exptl_crystal_density_diffrn", "_exptl_crystal.density_diffrn"),
    "mu": ("_exptl_absorpt_coefficient_mu", "_exptl_absorpt.coefficient_mu"),
    "f000": ("_exptl_crystal_F_000", "_exptl_crystal.F_000"),
    "rint": ("_diffrn_reflns_av_R_equivalents", "_diffrn_reflns.av_R_equivalents"),
    "gof": ("_refine_ls_goodness_of_fit_ref", "_refine_ls.goodness_of_fit_ref"),
    "parameters": ("_refine_ls_number_parameters", "_refine_ls.number_parameters"),
    "shift": ("_refine_ls_shift/su_max", "_refine_ls.shift/su_max"),
    "flack": ("_refine_ls_abs_structure_Flack", "_refine_ls_abs_structure_flack", "_refine_ls.abs_structure_Flack"),
}


def _get(record: CifRecord, key: str) -> str | None:
    return record.get(*ALIASES[key])


def _join(values: list[str | None], separator: str = " / ") -> str | None:
    return separator.join(value if value is not None else "—" for value in values) if any(values) else None


def field_value(record: CifRecord, key: str) -> str | None:
    if key == "temperature":
        candidates = [
            record.get("_diffrn_ambient_temperature", "_diffrn.ambient_temperature"),
            record.get("_cell_measurement_temperature", "_cell.measurement_temperature"),
        ]
        available = [value for value in candidates if value is not None]
        if not available:
            return None
        return available[0]
    if key in ALIASES:
        return _get(record, key)
    if key == "crystal_size":
        return _join([
            record.get("_exptl_crystal_size_max"),
            record.get("_exptl_crystal_size_mid"),
            record.get("_exptl_crystal_size_min"),
        ], " × ")
    if key == "radiation":
        radiation = record.get("_diffrn_radiation_type")
        if radiation:
            radiation = radiation.replace("\\a", "α").replace("\\b", "β").replace("\\g", "γ")
        wavelength = record.get("_diffrn_radiation_wavelength")
        return f"{radiation} (λ = {wavelength})" if radiation and wavelength else radiation or wavelength
    if key == "instrument":
        return record.get("_diffrn_measurement_device_type", "_diffrn_measurement_device")
    if key == "theta_range":
        return _join([
            record.get("_diffrn_reflns_theta_min", "_diffrn_reflns.theta_min"),
            record.get("_diffrn_reflns_theta_max", "_diffrn_reflns.theta_max"),
        ], "–")
    if key == "index_ranges":
        parts = []
        for axis in "hkl":
            lo = record.get(f"_diffrn_reflns_limit_{axis}_min")
            hi = record.get(f"_diffrn_reflns_limit_{axis}_max")
            parts.append(f"{lo or '—'} ≤ {axis} ≤ {hi or '—'}")
        return "; ".join(parts) if any("—" not in part for part in parts) else None
    if key == "reflections":
        return _join([
            record.get("_diffrn_reflns_number"),
            record.get("_reflns_number_total"),
            record.get("_reflns_number_gt"),
        ])
    if key == "data_restraints_parameters":
        return _join([
            record.get("_refine_ls_number_reflns", "_reflns_number_total"),
            record.get("_refine_ls_number_restraints"),
            record.get("_refine_ls_number_parameters"),
        ])
    if key == "r_gt":
        r1 = record.get("_refine_ls_R_factor_gt")
        wr2 = record.get("_refine_ls_wR_factor_gt")
        return _join([f"R1 = {r1}" if r1 else None, f"wR2 = {wr2}" if wr2 else None], ", ")
    if key == "r_all":
        r1 = record.get("_refine_ls_R_factor_all")
        wr2 = record.get("_refine_ls_wR_factor_ref", "_refine_ls_wR_factor_all")
        return _join([f"R1 = {r1}" if r1 else None, f"wR2 = {wr2}" if wr2 else None], ", ")
    if key == "diff":
        return _join([record.get("_refine_diff_density_max"), record.get("_refine_diff_density_min")])
    if key == "transmission":
        return _join([record.get("_exptl_absorpt_correction_T_min"), record.get("_exptl_absorpt_correction_T_max")])
    raise KeyError(key)


def cell_volume_from_parameters(record: CifRecord) -> float | None:
    numbers = [cif_number(field_value(record, key)) for key in ("a", "b", "c", "alpha", "beta", "gamma")]
    if any(value is None for value in numbers):
        return None
    a, b, c, alpha, beta, gamma = numbers
    ca, cb, cg = (math.cos(math.radians(angle)) for angle in (alpha, beta, gamma))
    determinant = 1 + 2 * ca * cb * cg - ca * ca - cb * cb - cg * cg
    return a * b * c * math.sqrt(max(determinant, 0.0))


def chemical_formula_runs(formula: str) -> list[tuple[str, bool]]:
    """Split formula into (text, subscript) chunks without changing CIF content."""
    chunks: list[tuple[str, bool]] = []
    for part in re.split(r"(\d+(?:\.\d+)?)", formula):
        if part:
            chunks.append((part, bool(re.fullmatch(r"\d+(?:\.\d+)?", part))))
    return chunks
