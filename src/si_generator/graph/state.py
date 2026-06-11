from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
    compound_id: str
    path: str


class GenerateSIState(TypedDict, total=False):
    run_id: str
    request: GenerateSIRequest
    style_config: dict[str, Any]
    input_compounds: list[Compound]
    compounds: dict[str, Compound]
    order: list[str]
    output_path: Path
    artifacts: dict[str, str]
    issues: list[Issue]
    manifest: dict[str, Any]


def make_run_id(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y%m%dT%H%M%S")
