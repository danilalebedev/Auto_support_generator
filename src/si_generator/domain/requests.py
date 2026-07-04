from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .types import BaselineMode, SpectrumEmbedMode
from ..output_layout import output_root_for


InputKind = Literal["csv", "word"]


@dataclass(slots=True)
class GenerateSIRequest:
    input_path: Path
    input_kind: InputKind
    output_path: Path
    template_docx: Path | None = None
    references_path: Path | None = None
    spectra_source: Path | None = None
    spectra_zip: Path | None = None
    loadings_schema_docx: Path | None = None
    loadings_scope_docx: Path | None = None
    mnova_exe: Path | None = None
    mnova_graphics_profile: Path | None = None
    no_extract_nmr: bool = False
    insert_spectra_as: SpectrumEmbedMode = "png"
    peak_threshold_fraction: float | None = None
    peak_threshold_fraction_1h: float | None = None
    peak_threshold_fraction_13c: float | None = None
    baseline_mode: BaselineMode = "auto"
    baseline_apply_1h: bool = False
    baseline_apply_13c: bool = True
    baseline_poly_order: int = 3
    whittaker_lambda: float = 100000.0
    whittaker_asymmetry: float = 0.001
    generate_loadings: bool = False
    extract_structure_metadata: bool = False
    only: tuple[str, ...] = ()
    insert_chemdraw: bool = False
    no_check_support: bool = False

    @property
    def input_base_dir(self) -> Path:
        return self.input_path.parent

    @property
    def output_dir(self) -> Path:
        return output_root_for(self.output_path)

    @property
    def resolved_spectra_source(self) -> Path | None:
        return self.spectra_source or self.spectra_zip


@dataclass(slots=True)
class CheckSIRequest:
    manifest_path: Path
    support_docx: Path | None = None
    strict_artifacts: bool = True


@dataclass(slots=True)
class PatchSIRequest:
    manifest_path: Path
    renumber: dict[str, str]
    remove: tuple[str, ...] = ()
    reorder: tuple[str, ...] = ()
    support_docx: Path | None = None
    output_docx: Path | None = None
    output_manifest: Path | None = None
    strict_artifacts: bool = True


@dataclass(slots=True)
class AddCompoundsRequest:
    manifest_path: Path
    input_path: Path
    input_kind: InputKind
    output_docx: Path
    support_docx: Path | None = None
    template_docx: Path | None = None
    references_path: Path | None = None
    spectra_source: Path | None = None
    spectra_zip: Path | None = None
    mnova_exe: Path | None = None
    mnova_graphics_profile: Path | None = None
    no_extract_nmr: bool = False
    insert_spectra_as: SpectrumEmbedMode = "png"
    peak_threshold_fraction: float | None = None
    peak_threshold_fraction_1h: float | None = None
    peak_threshold_fraction_13c: float | None = None
    baseline_mode: BaselineMode = "auto"
    baseline_apply_1h: bool = False
    baseline_apply_13c: bool = True
    baseline_poly_order: int = 3
    whittaker_lambda: float = 100000.0
    whittaker_asymmetry: float = 0.001
    generate_loadings: bool = False
    no_check_support: bool = False
    strict_artifacts: bool = True

    @property
    def resolved_spectra_source(self) -> Path | None:
        return self.spectra_source or self.spectra_zip
