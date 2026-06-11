from __future__ import annotations

from typing import Literal, TypedDict


IssueSeverity = Literal["info", "warning", "error"]
ArtifactKind = Literal["docx", "png", "mnova", "txt", "zip", "cif", "json"]
PeakPickingPolicy = Literal["minimal", "normal", "dense", "manual"]
SpectrumEmbedMode = Literal["png", "mnova", "both", "none"]


class Issue(TypedDict, total=False):
    code: str
    severity: IssueSeverity
    message: str
    compound_id: str
    path: str


class Artifact(TypedDict, total=False):
    id: str
    kind: ArtifactKind
    path: str
    compound_id: str
    hash: str


class PhysicalBlock(TypedDict, total=False):
    color: str
    state: str
    melting_point: str
    rf: str
    yield_text: str


class StructureBlock(TypedDict, total=False):
    path: str
    has_word_structure: bool
    smiles: str
    formula: str


class SpectrumRenderSpec(TypedDict, total=False):
    nucleus: Literal["1H", "13C", "19F", "31P"]
    x_range_ppm: tuple[float, float]
    target_signal_height_fraction: float
    ignore_regions_ppm: list[tuple[float, float]]
    peak_picking: PeakPickingPolicy


class SpectrumAsset(TypedDict, total=False):
    source_path: str
    image_path: str
    mnova_path: str
    report_path: str
    render_spec: SpectrumRenderSpec
    embed_mode: SpectrumEmbedMode


class NMRSignal(TypedDict, total=False):
    shift: float
    shift_range: tuple[float, float]
    multiplicity: str
    j_values: list[float]
    integral: float
    assignment: str
    raw_peaks: list[float]


class NMRSpectrumBlock(TypedDict, total=False):
    nucleus: Literal["1H", "13C", "19F", "31P"]
    frequency_mhz: float
    solvent: str
    temperature: str
    signals: list[NMRSignal]
    formatted_text: str
    conditions: str
    peak_picking: PeakPickingPolicy


class NMRBlock(TypedDict, total=False):
    spectra: dict[str, NMRSpectrumBlock]
    extra_text: str
    warnings: list[str]


class HRMSBlock(TypedDict, total=False):
    method: str
    label: str
    adduct: str
    found_mz: float
    found_text: str
    calculated_mz: float
    ion_formula: str
    isotope_policy: Literal["monoisotopic", "auto_halogen", "explicit"]
    isotope_labels: dict[str, int]
    formatted_text: str


class IRBlock(TypedDict, total=False):
    method: str
    peaks_cm1: list[int]
    formatted_text: str


class ElementalAnalysisBlock(TypedDict, total=False):
    formula: str
    calculated: dict[str, float]
    found: dict[str, float]
    formatted_text: str


class ReagentAmount(TypedDict, total=False):
    role: Literal["limiting", "reagent", "catalyst", "solvent", "additive"]
    name: str
    formula: str
    mw: float
    equivalents: float
    mmol: float
    mass_mg: float
    volume_uL: float
    density_g_mL: float
    concentration_M: float


class ReactionBlock(TypedDict, total=False):
    scale_basis: Literal["product_amount", "limiting_reagent", "manual"]
    target_mmol: float
    limiting_reagent: str
    reagents: list[ReagentAmount]
    solvent: str
    temperature: str
    time: str
    preparation: str
    formatted_text: str


class Reference(TypedDict, total=False):
    key: str
    authors: list[str]
    title: str
    journal: str
    year: int
    volume: str
    pages: str
    doi: str


class ReferenceStore(TypedDict, total=False):
    references: dict[str, Reference]
    order: list[str]


class XRDBlock(TypedDict, total=False):
    cif_path: str
    checkcif_path: str
    crystal_data: dict[str, object]
    table_path: str
    figure_paths: list[str]
    ccdc_number: str
    formatted_text: str


class Compound(TypedDict, total=False):
    id: str
    number: str
    name: str
    formula: str
    smiles: str
    physical: PhysicalBlock
    structure: StructureBlock
    spectra: dict[str, SpectrumAsset]
    nmr: NMRBlock
    hrms: HRMSBlock
    ir: IRBlock
    elemental_analysis: ElementalAnalysisBlock
    reaction: ReactionBlock
    references: list[str]
    xrd: XRDBlock
    issues: list[Issue]


class SpectraProcessingConfig(TypedDict, total=False):
    extract_nmr: bool
    insert_spectra_as: SpectrumEmbedMode
    target_signal_height_fraction: float
    solvent_suppression: bool
    ignore_regions_ppm: dict[str, list[tuple[float, float]]]
    peak_picking: PeakPickingPolicy
    mnova_executable_path: str
    mnova_script_path: str
    keep_intermediate_reports: bool


class JournalProfile(TypedDict, total=False):
    id: str
    name: str
    docx_template_path: str
    section_order: list[str]
    nmr_format_style: str
    hrms_format_style: str
    reference_style: str
    use_subscripts_in_formulae: bool
    use_superscript_isotopes: bool
    use_italic_j: bool


class GenerationConfig(TypedDict, total=False):
    generate_loadings: bool
    include_ir: bool
    include_elemental_analysis: bool
    include_references: bool
    include_xrd: bool
    check_support: bool
    validate_only: bool
    patch_existing_support: bool


class RuntimeConfig(TypedDict, total=False):
    gui: bool
    debug: bool
    dry_run: bool


class ManifestCompound(TypedDict, total=False):
    id: str
    number: str
    source_row: int
    structure_placeholder: str
    docx_block_id: str
    docx_bookmark: str
    references: list[str]
    artifacts: dict[str, str]


class Manifest(TypedDict, total=False):
    run_id: str
    input_hashes: dict[str, str]
    configs: dict[str, object]
    order: list[str]
    compounds: dict[str, ManifestCompound]


class SIState(TypedDict, total=False):
    run_id: str
    compounds: dict[str, Compound]
    order: list[str]
    spectra_config: SpectraProcessingConfig
    generation_config: GenerationConfig
    runtime_config: RuntimeConfig
    journal_profile: JournalProfile
    reference_store: ReferenceStore
    input_paths: dict[str, str]
    output_paths: dict[str, str]
    artifacts: dict[str, Artifact]
    issues: list[Issue]
    logs: list[str]
    manifest: Manifest

