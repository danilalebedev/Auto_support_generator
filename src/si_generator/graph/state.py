from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal, TypedDict

from ..domain.requests import CheckSIRequest, GenerateSIRequest, InputKind, PatchSIRequest
from ..domain.types import (
    GenerationConfig,
    Issue,
    JournalProfile,
    ReferenceStore,
    RuntimeConfig,
    SpectraProcessingConfig,
    SpectrumRenderSpec,
)
from ..domain.compound import Compound
from ..render.si_document import SIDocument


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
    patch_result: dict[str, Any]
    artifacts: dict[str, str]
    issues: list[Issue]
    status: Literal["pass", "fail"]


def make_run_id(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y%m%dT%H%M%S")
