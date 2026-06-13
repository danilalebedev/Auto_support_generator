from __future__ import annotations

from pathlib import Path

from .domain.compound import Compound
from .domain.types import ReferenceStore
from .render.document_model import build_si_document_model
from .render.si_document import SIDocument
from .template_renderer import render_document_from_template


def build_document(
    compounds: list[Compound],
    output_path: str | Path,
    template_path: str | Path | None = None,
    reference_store: ReferenceStore | None = None,
) -> Path:
    return build_document_from_model(
        build_si_document_model(compounds, reference_store=reference_store),
        output_path,
        template_path=template_path,
    )


def build_document_from_model(
    document_model: SIDocument,
    output_path: str | Path,
    template_path: str | Path | None = None,
) -> Path:
    return render_document_from_template(document_model, output_path, template_path)
