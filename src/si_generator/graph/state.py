from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict

from ..models import Compound


InputKind = Literal["csv", "word"]


@dataclass(slots=True)
class GenerateSIRequest:
    input_path: Path
    input_kind: InputKind
    output_path: Path
    template_docx: Path | None = None
    style_config_path: Path | None = None
    spectra_zip: Path | None = None
    mnova_exe: Path | None = None
    no_extract_nmr: bool = False
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


class Issue(TypedDict, total=False):
    code: str
    severity: Literal["info", "warning", "error"]
    message: str
    compound_number: str
    path: str


class GenerateSIState(TypedDict, total=False):
    request: GenerateSIRequest
    style_config: dict[str, Any]
    compounds: list[Compound]
    output_path: Path
    artifacts: dict[str, str]
    issues: list[Issue]
