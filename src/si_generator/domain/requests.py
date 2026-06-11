from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .types import SpectrumEmbedMode


InputKind = Literal["csv", "word"]


@dataclass(slots=True)
class GenerateSIRequest:
    input_path: Path
    input_kind: InputKind
    output_path: Path
    template_docx: Path | None = None
    style_config_path: Path | None = None
    journal_profile: str | Path | None = None
    references_path: Path | None = None
    spectra_zip: Path | None = None
    mnova_exe: Path | None = None
    no_extract_nmr: bool = False
    insert_spectra_as: SpectrumEmbedMode = "png"
    peak_threshold_fraction: float | None = None
    peak_threshold_fraction_1h: float | None = None
    peak_threshold_fraction_13c: float | None = None
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
        return self.output_path.parent


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
