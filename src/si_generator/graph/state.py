from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, TypedDict

from ..domain.types import GenerationConfig, JournalProfile, ReferenceStore, RuntimeConfig, SpectraProcessingConfig, SpectrumEmbedMode, SpectrumRenderSpec
from ..models import Compound
from ..render.si_document import SIDocument


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
    journal_profile: JournalProfile
    reference_store: ReferenceStore
    spectra_config: SpectraProcessingConfig
    generation_config: GenerationConfig
    runtime_config: RuntimeConfig
    input_compounds: list[Compound]
    compounds: dict[str, Compound]
    order: list[str]
    spectra_plan: dict[str, dict[str, SpectrumRenderSpec]]
    document_model: SIDocument
    output_path: Path
    artifacts: dict[str, str]
    issues: list[Issue]
    manifest: dict[str, Any]


class CheckSIState(TypedDict, total=False):
    run_id: str
    request: CheckSIRequest
    manifest: dict[str, Any]
    artifacts: dict[str, str]
    issues: list[Issue]
    status: Literal["pass", "fail"]


class PatchSIState(TypedDict, total=False):
    run_id: str
    request: PatchSIRequest
    manifest: dict[str, Any]
    artifacts: dict[str, str]
    issues: list[Issue]
    status: Literal["pass", "fail"]


def make_run_id(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y%m%dT%H%M%S")
