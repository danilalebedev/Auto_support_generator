from __future__ import annotations

import json
import os
import queue
import shutil
import tkinter as tk
import threading
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox
from tkinter import ttk
from typing import Any

from .domain.manifest import manifest_has_errors
from .domain.patching import parse_remove_list, parse_renumber_map, parse_reorder_list, parse_swap_pairs
from .domain.requests import AddCompoundsRequest, CheckSIRequest, GenerateSIRequest, PatchSIRequest
from .domain.spectra_config import (
    DEFAULT_BASELINE_APPLY_13C,
    DEFAULT_BASELINE_APPLY_1H,
    DEFAULT_BASELINE_MODE,
    DEFAULT_BASELINE_POLY_ORDER,
    DEFAULT_C13_PEAK_THRESHOLD_FRACTION,
    DEFAULT_H1_PEAK_THRESHOLD_FRACTION,
    DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION,
    DEFAULT_WHITTAKER_ASYMMETRY,
    DEFAULT_WHITTAKER_LAMBDA,
    DEFAULT_X_RANGES,
)
from .domain.types import SpectrumEmbedMode
from .external_tools import find_mnova_executable
from .gui_settings import load_gui_settings, save_gui_settings
from .runtime_diagnostics import format_preflight_issues, issue_has_errors, preflight_generate_request
from .runtime_paths import bundled_resource_path, default_output_path, examples_dir
from .workflows.check_si import run_check_si
from .workflows.generate_si import output_path_from_state, run_generate_si
from .workflows.patch_si import run_patch_si


INSTRUCTION_TEMPLATE_FILES = (
    ("Example 1 - Compound table", Path("example_1") / "Compound_table.docx", "Four compounds for the first synthetic series."),
    ("Example 1 - Spectra source", Path("example_1") / "Spectra_source", "Matching raw 1H and 13C spectra as a folder."),
    ("Example 1 - SI template", Path("example_1") / "SI_template.docx", "Word template controlling text and appendix formatting."),
    ("Example 1 - Reaction schema", Path("example_1") / "Reaction_schema.docx", "Reagent rules used to calculate reaction loadings."),
    ("Example 1 - Scope", Path("example_1") / "Scope.docx", "Per-compound reaction and product data."),
    ("Example 2", Path("example_2"), "Complete second-series input set with the same five upload-field names."),
    ("Example 3", Path("example_3"), "Complete new-method input set; includes Spectra_source as both folder and zip."),
)
STARTER_EXAMPLE_DIRS = (Path("example_1"), Path("example_2"), Path("example_3"))


THEME_PALETTES = {
    "light": {
        "app_bg": "#f5f7fb",
        "sidebar_bg": "#eef3fb",
        "sidebar_hover": "#dde8f8",
        "sidebar_selected": "#d4e6ff",
        "card_bg": "#ffffff",
        "border": "#d8dee9",
        "text": "#18202c",
        "muted": "#607086",
        "accent": "#1668dc",
        "accent_hover": "#0f5cc6",
        "success": "#0f7b4f",
        "input_bg": "#ffffff",
        "log_bg": "#ffffff",
        "log_fg": "#172033",
        "disabled_bg": "#e7ebf2",
    },
    "dark": {
        "app_bg": "#111827",
        "sidebar_bg": "#0b1220",
        "sidebar_hover": "#1b2a41",
        "sidebar_selected": "#17345f",
        "card_bg": "#182235",
        "border": "#314057",
        "text": "#edf2f7",
        "muted": "#aab6c8",
        "accent": "#4f9cff",
        "accent_hover": "#78b5ff",
        "success": "#4dd4a3",
        "input_bg": "#0f172a",
        "log_bg": "#0b1020",
        "log_fg": "#dbeafe",
        "disabled_bg": "#263246",
    },
}


class SIGeneratorApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Auto Support Generator")
        self.root.geometry("1120x720")
        self.root.minsize(860, 560)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.input_path = StringVar()
        self.spectra_source = StringVar()
        self.spectra_zip = self.spectra_source
        self.template_docx = StringVar()
        self.loadings_schema_docx = StringVar()
        self.loadings_scope_docx = StringVar()
        self.mnova_exe = StringVar()
        self.mnova_graphics_profile = StringVar()
        self.mnova_graphics_profile_1h = StringVar()
        self.mnova_graphics_profile_13c = StringVar()
        self.output_docx = StringVar(value=str(default_output_path()))
        self.output_folder = StringVar(value=str(default_output_path().parent))
        self.theme_mode = StringVar(value="light")
        self.dark_theme = BooleanVar(value=False)
        self.input_kind = StringVar(value="word")
        self.insert_spectra_as = StringVar(value="png")
        self.target_signal_height_percent = StringVar(value=_format_fraction_percent(DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION))
        self.h1_ppm_min = StringVar(value=f"{DEFAULT_X_RANGES['1H'][0]:g}")
        self.h1_ppm_max = StringVar(value=f"{DEFAULT_X_RANGES['1H'][1]:g}")
        self.c13_ppm_min = StringVar(value=f"{DEFAULT_X_RANGES['13C'][0]:g}")
        self.c13_ppm_max = StringVar(value=f"{DEFAULT_X_RANGES['13C'][1]:g}")
        self.peak_threshold_1h_percent = StringVar(value=_format_peak_threshold_percent(DEFAULT_H1_PEAK_THRESHOLD_FRACTION))
        self.peak_threshold_13c_percent = StringVar(value=_format_peak_threshold_percent(DEFAULT_C13_PEAK_THRESHOLD_FRACTION))
        self.baseline_mode = StringVar(value=DEFAULT_BASELINE_MODE)
        self.baseline_apply_1h = BooleanVar(value=DEFAULT_BASELINE_APPLY_1H)
        self.baseline_apply_13c = BooleanVar(value=DEFAULT_BASELINE_APPLY_13C)
        self.baseline_poly_order = StringVar(value=str(DEFAULT_BASELINE_POLY_ORDER))
        self.whittaker_lambda = StringVar(value=f"{DEFAULT_WHITTAKER_LAMBDA:g}")
        self.whittaker_asymmetry = StringVar(value=f"{DEFAULT_WHITTAKER_ASYMMETRY:g}")
        self.highlight_solvent_peaks = BooleanVar(value=False)
        self.check_support = BooleanVar(value=True)
        self.generate_loadings = BooleanVar(value=False)
        self.calculate_elemental_analysis = BooleanVar(value=False)
        self.status_text = StringVar(value="Ready")
        self.result_support = StringVar(value="")
        self.result_output_folder = StringVar(value="")
        self.result_manifest = StringVar(value="")
        self.result_report = StringVar(value="")
        self.result_logs = StringVar(value="")
        self.result_overview = StringVar(value="")
        self.existing_manifest = StringVar(value="")
        self.check_support_docx = StringVar(value="")
        self.patch_source_output_dir = StringVar(value="")
        self.patch_operation = StringVar(value="renumber")
        self.patch_instruction = StringVar(value="")
        self.patch_instruction_label = StringVar(value="Number mapping")
        self.patch_instruction_example = StringVar(value="Example: 2a=3a,2b=3b")
        self.add_previous_output_dir = StringVar(value="")
        self.add_manifest = StringVar(value="")
        self.add_support_docx = StringVar(value="")
        self.add_template_docx = StringVar(value="")
        self.add_loadings_schema_docx = StringVar(value="")
        self.add_loadings_scope_docx = StringVar(value="")
        self.add_input_path = StringVar(value="")
        self.add_spectra_source = StringVar(value="")
        self.add_output_docx = StringVar(value="")
        self.add_output_folder = StringVar(value=str(default_output_path().parent))
        self.add_input_kind = StringVar(value="word")
        self.add_method_mode = StringVar(value="same_series")
        self.page_title = StringVar(value="Generate SI")
        self.page_subtitle = StringVar(value="Create formatted Supporting Information from a compound table and spectra.")
        self._current_page = "generate"

        self._is_running = False
        self._last_output_folder: Path | None = None
        self._log_queue: queue.Queue[Any] = queue.Queue()
        self.log = _RunLogBuffer()
        self._poll_after_id: str | None = None
        self._theme = THEME_PALETTES["light"]
        self._nav_buttons: dict[str, _PillButton] = {}
        self._sidebar_buttons: list[_PillButton] = []
        self._instruction_blocks: list[_CollapsibleInstructionBlock] = []
        self._page_frames: dict[str, ttk.Frame] = {}
        self._scrollable_frames: list[_ScrollableFrame] = []
        self._theme_switch: _ThemeSwitch | None = None
        self._logo_mark_source: tk.PhotoImage | None = None
        self._logo_mark_image: tk.PhotoImage | None = None

        self._load_saved_settings()
        self._on_patch_operation_changed(clear_instruction=False)
        self._set_default_mngp_profiles_if_empty()
        if self.theme_mode.get() not in THEME_PALETTES:
            self.theme_mode.set("light")
        self.dark_theme.set(self.theme_mode.get() == "dark")
        self._configure_style()
        self._load_logo_assets()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_log_queue()

    def _configure_style(self) -> None:
        self._theme = THEME_PALETTES.get(self.theme_mode.get(), THEME_PALETTES["light"])
        theme = self._theme
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        self.root.configure(bg=theme["app_bg"])
        style.configure(".", font=("Segoe UI", 10), background=theme["app_bg"], foreground=theme["text"])
        style.configure("TFrame", background=theme["app_bg"])
        style.configure("App.TFrame", background=theme["app_bg"])
        style.configure("Sidebar.TFrame", background=theme["sidebar_bg"])
        style.configure("Card.TFrame", background=theme["card_bg"])
        style.configure("TLabel", background=theme["card_bg"], foreground=theme["text"])
        style.configure("Sidebar.TLabel", background=theme["sidebar_bg"], foreground=theme["text"])
        style.configure("SidebarMuted.TLabel", background=theme["sidebar_bg"], foreground=theme["muted"])
        style.configure("Title.TLabel", background=theme["app_bg"], foreground=theme["text"], font=("Segoe UI", 20, "bold"))
        style.configure("SectionTitle.TLabel", background=theme["app_bg"], foreground=theme["text"], font=("Segoe UI", 13, "bold"))
        style.configure("Muted.TLabel", background=theme["app_bg"], foreground=theme["muted"])
        style.configure("Status.TLabel", background=theme["app_bg"], foreground=theme["success"])
        style.configure("TCheckbutton", background=theme["app_bg"], foreground=theme["text"])
        style.map("TCheckbutton", background=[("active", theme["app_bg"])], foreground=[("disabled", theme["muted"])])
        style.configure("TRadiobutton", background=theme["app_bg"], foreground=theme["text"])
        style.map("TRadiobutton", background=[("active", theme["app_bg"])], foreground=[("disabled", theme["muted"])])
        style.configure("TEntry", fieldbackground=theme["input_bg"], foreground=theme["text"], insertcolor=theme["text"])
        style.map("TEntry", fieldbackground=[("readonly", theme["input_bg"]), ("disabled", theme["disabled_bg"])])
        style.configure("TCombobox", fieldbackground=theme["input_bg"], foreground=theme["text"], arrowcolor=theme["muted"])
        style.map("TCombobox", fieldbackground=[("readonly", theme["input_bg"])], foreground=[("readonly", theme["text"])])
        style.configure(
            "Card.TLabelframe",
            background=theme["card_bg"],
            bordercolor=theme["border"],
            lightcolor=theme["border"],
            darkcolor=theme["border"],
            relief="solid",
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=theme["app_bg"],
            foreground=theme["text"],
            font=("Segoe UI", 10, "bold"),
        )
        style.configure("TLabelframe.Label", background=theme["app_bg"], foreground=theme["text"], font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8), background=theme["accent"], foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", theme["accent_hover"]), ("disabled", theme["disabled_bg"])], foreground=[("disabled", theme["muted"])])
        style.configure("TButton", padding=(10, 6))
        style.configure("Sidebar.TButton", anchor="w", padding=(14, 10), background=theme["sidebar_bg"], foreground=theme["text"], borderwidth=0)
        style.map("Sidebar.TButton", background=[("active", theme["sidebar_hover"])], foreground=[("disabled", theme["muted"])])
        style.configure("ActiveSidebar.TButton", anchor="w", padding=(14, 10), background=theme["sidebar_selected"], foreground=theme["text"], borderwidth=0)
        style.map("ActiveSidebar.TButton", background=[("active", theme["sidebar_selected"])])
        style.configure("SidebarAction.TButton", anchor="center", padding=(10, 7), background=theme["sidebar_hover"], foreground=theme["text"], borderwidth=0)
        style.map("SidebarAction.TButton", background=[("active", theme["sidebar_selected"])])
        self._apply_theme_to_non_ttk_widgets()

    def _load_logo_assets(self) -> None:
        logo_path = bundled_resource_path("assets/auto_support_generator_mark.png", package_file=__file__)
        if not logo_path.exists():
            return
        try:
            self._logo_mark_source = tk.PhotoImage(file=str(logo_path))
            self._logo_mark_image = self._logo_mark_source
            self.root.iconphoto(True, self._logo_mark_source)
        except tk.TclError:
            self._logo_mark_source = None
            self._logo_mark_image = None

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, style="App.TFrame")
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=0, minsize=260)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(0, weight=1)

        self._build_sidebar(outer)
        self._build_content_shell(outer)
        self._show_page("generate")
        self._apply_theme_to_non_ttk_widgets()

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        sidebar = ttk.Frame(parent, style="Sidebar.TFrame", padding=(18, 16, 16, 18))
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(8, weight=1)

        brand = ttk.Frame(sidebar, style="Sidebar.TFrame")
        brand.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        brand.columnconfigure(0, weight=1)
        if self._logo_mark_image is not None:
            ttk.Label(brand, image=self._logo_mark_image, style="Sidebar.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Label(brand, text="Auto Support", style="Sidebar.TLabel", font=("Segoe UI", 15, "bold")).grid(row=1, column=0, sticky="w")
        ttk.Label(brand, text="Generator", style="SidebarMuted.TLabel", font=("Segoe UI", 12, "bold")).grid(row=2, column=0, sticky="w")

        self._theme_switch = _ThemeSwitch(
            sidebar,
            mode=self.theme_mode.get(),
            command=self._set_theme_mode,
            theme=self._theme,
        )
        self._theme_switch.grid(row=1, column=0, sticky="w", pady=(0, 16))

        nav_items = (
            ("generate", "Generate"),
            ("advanced", "Processing"),
            ("check", "Check"),
            ("patch", "Patch"),
            ("add", "Add"),
            ("instructions", "Instructions"),
        )
        for index, (page, text) in enumerate(nav_items, start=2):
            button = _PillButton(sidebar, text=text, command=lambda page=page: self._show_page(page), theme=self._theme)
            button.grid(row=index, column=0, sticky="ew", pady=4)
            self._nav_buttons[page] = button
            self._sidebar_buttons.append(button)

    def _build_content_shell(self, parent: ttk.Frame) -> None:
        main = ttk.Frame(parent, style="App.TFrame", padding=(18, 18, 18, 14))
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        header = ttk.Frame(main, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, textvariable=self.page_title, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.page_subtitle, style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 0))

        page_host = ttk.Frame(main, style="App.TFrame")
        page_host.grid(row=1, column=0, sticky="nsew")
        page_host.columnconfigure(0, weight=1)
        page_host.rowconfigure(0, weight=1)
        self._build_generate_page(page_host)
        self._build_advanced_page(page_host)
        self._build_check_page(page_host)
        self._build_patch_page(page_host)
        self._build_add_page(page_host)
        self._build_instructions_page(page_host)

        footer = ttk.Frame(main, style="App.TFrame")
        footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status_text, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=150)
        self.progress.grid(row=0, column=1, sticky="e", padx=(12, 0))
        ttk.Button(footer, text="Open last output", command=self._open_output_folder).grid(row=0, column=2, sticky="e", padx=(8, 0))
        self.run_button = ttk.Button(footer, text="Generate SI", command=self._start_generation, style="Accent.TButton")
        self.run_button.grid(row=0, column=3, sticky="e", padx=(8, 0))

    def _make_page(self, parent: ttk.Frame, key: str) -> ttk.Frame:
        page = ttk.Frame(parent, style="App.TFrame")
        page.grid(row=0, column=0, sticky="nsew")
        page.grid_remove()
        page.columnconfigure(0, weight=1)
        self._page_frames[key] = page
        return page

    def _build_generate_page(self, parent: ttk.Frame) -> None:
        page = self._make_page(parent, "generate")
        page.rowconfigure(0, weight=1)
        generate_scroll = _ScrollableFrame(page, padding=2)
        self._scrollable_frames.append(generate_scroll)
        generate_scroll.grid(row=0, column=0, sticky="nsew")
        content = generate_scroll.content
        content.columnconfigure(0, weight=1)

        simple = ttk.LabelFrame(content, text="Simple", padding=12, style="Card.TLabelframe")
        simple.grid(row=0, column=0, sticky="ew")
        simple.columnconfigure(1, weight=1)
        self._file_row(simple, 0, "Compound table", self.input_path, self._browse_input)
        self._source_row(simple, 1, "Spectra source", self.spectra_source, self._browse_spectra_source, self._browse_spectra_folder)
        self._folder_row(simple, 2, "Output folder", self.output_folder, self._browse_output_folder)

        self._build_optional_inputs_block(content, 1)
        self._build_loadings_block(content, 2)

        results = ttk.LabelFrame(content, text="Results", padding=12, style="Card.TLabelframe")
        results.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        results.columnconfigure(1, weight=1)
        self._result_row(results, 0, "Support .docx", self.result_support, lambda: self._open_result_path(self.result_support, "Support .docx"), "Open support")
        self._result_row(results, 1, "Output folder", self.result_output_folder, lambda: self._open_result_path(self.result_output_folder, "Output folder"), "Open output folder")
        self._result_row(results, 2, "Logs", self.result_logs, lambda: self._open_result_path(self.result_logs, "Logs"), "Open logs")
        self._result_row(results, 3, "Report", self.result_report, lambda: self._open_result_path(self.result_report, "Report"), "Open report")
        ttk.Label(results, textvariable=self.result_overview, style="Muted.TLabel").grid(row=4, column=0, columnspan=3, sticky="ew", pady=(6, 0))

    def _build_optional_inputs_block(self, parent: ttk.Frame, row: int) -> None:
        files = ttk.LabelFrame(parent, text="Optional inputs", padding=12, style="Card.TLabelframe")
        files.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        files.columnconfigure(1, weight=1)
        self._file_row(files, 0, "SI template .docx", self.template_docx, lambda: self._browse_file(self.template_docx, [("Word documents", "*.docx"), ("All files", "*.*")]), optional=True)
        self._file_row(
            files,
            1,
            "MestReNova .exe",
            self.mnova_exe,
            lambda: self._browse_file(self.mnova_exe, [("MestReNova", "*.exe"), ("All files", "*.*")]),
            optional=True,
            extra_button=("Detect", self._detect_mnova),
        )
        self._file_row(
            files,
            2,
            "1H .mngp",
            self.mnova_graphics_profile_1h,
            lambda: self._browse_file(
                self.mnova_graphics_profile_1h,
                [("MestReNova graphic properties", "*.mngp"), ("All files", "*.*")],
            ),
            optional=True,
        )
        self._file_row(
            files,
            3,
            "13C .mngp",
            self.mnova_graphics_profile_13c,
            lambda: self._browse_file(
                self.mnova_graphics_profile_13c,
                [("MestReNova graphic properties", "*.mngp"), ("All files", "*.*")],
            ),
            optional=True,
        )

    def _build_loadings_block(self, parent: ttk.Frame, row: int) -> None:
        loadings = ttk.LabelFrame(parent, text="Reagent Loadings", padding=12, style="Card.TLabelframe")
        loadings.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        loadings.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            loadings,
            text="Calculate reagent loadings",
            variable=self.generate_loadings,
        ).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self._file_row(
            loadings,
            1,
            "Reaction schema .docx",
            self.loadings_schema_docx,
            lambda: self._browse_file(self.loadings_schema_docx, [("Word documents", "*.docx"), ("All files", "*.*")]),
            optional=True,
        )
        self._file_row(
            loadings,
            2,
            "Scope .docx",
            self.loadings_scope_docx,
            lambda: self._browse_file(self.loadings_scope_docx, [("Word documents", "*.docx"), ("All files", "*.*")]),
            optional=True,
        )

    def _build_advanced_page(self, parent: ttk.Frame) -> None:
        page = self._make_page(parent, "advanced")
        page.rowconfigure(0, weight=1)
        advanced_scroll = _ScrollableFrame(page, padding=2)
        self._scrollable_frames.append(advanced_scroll)
        advanced_scroll.grid(row=0, column=0, sticky="nsew")
        advanced = advanced_scroll.content
        advanced.columnconfigure(0, weight=1)

        options = ttk.LabelFrame(advanced, text="Processing", padding=12, style="Card.TLabelframe")
        options.grid(row=0, column=0, sticky="ew")
        ttk.Label(options, text="Compound table").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Label(options, text="Word table with ChemDraw OLE structures (.docx)", style="Muted.TLabel").grid(
            row=0,
            column=1,
            columnspan=3,
            sticky="w",
            pady=4,
        )
        ttk.Checkbutton(
            options,
            text="Check support (NMR, HRMS, elemental analysis)",
            variable=self.check_support,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Checkbutton(
            options,
            text="Calculate elemental analysis",
            variable=self.calculate_elemental_analysis,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Label(options, text="Spectra appendix").grid(row=1, column=2, sticky="e", padx=(12, 8), pady=4)
        ttk.Combobox(
            options,
            textvariable=self.insert_spectra_as,
            values=("png", "mnova", "none"),
            state="readonly",
            width=8,
        ).grid(row=1, column=3, sticky="w", pady=4)
        ttk.Label(options, text="1H threshold (%)").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(options, textvariable=self.peak_threshold_1h_percent, width=8).grid(row=3, column=1, sticky="w", pady=4)
        ttk.Label(options, text="13C threshold (%)").grid(row=3, column=2, sticky="e", padx=(12, 8), pady=4)
        ttk.Entry(options, textvariable=self.peak_threshold_13c_percent, width=8).grid(row=3, column=3, sticky="w", pady=4)
        ttk.Label(options, text="Signal height (%)").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(options, textvariable=self.target_signal_height_percent, width=8).grid(row=4, column=1, sticky="w", pady=4)
        ttk.Label(options, text="1H ppm range").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=4)
        h1_range = ttk.Frame(options)
        h1_range.grid(row=5, column=1, sticky="w", pady=4)
        ttk.Entry(h1_range, textvariable=self.h1_ppm_min, width=8).pack(side="left")
        ttk.Label(h1_range, text=" to ").pack(side="left")
        ttk.Entry(h1_range, textvariable=self.h1_ppm_max, width=8).pack(side="left")
        ttk.Label(options, text="13C ppm range").grid(row=5, column=2, sticky="e", padx=(12, 8), pady=4)
        c13_range = ttk.Frame(options)
        c13_range.grid(row=5, column=3, sticky="w", pady=4)
        ttk.Entry(c13_range, textvariable=self.c13_ppm_min, width=8).pack(side="left")
        ttk.Label(c13_range, text=" to ").pack(side="left")
        ttk.Entry(c13_range, textvariable=self.c13_ppm_max, width=8).pack(side="left")
        ttk.Checkbutton(
            options,
            text="Highlight solvent peaks",
            variable=self.highlight_solvent_peaks,
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=4)

        baseline = ttk.LabelFrame(advanced, text="Baseline correction", padding=12, style="Card.TLabelframe")
        baseline.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(baseline, text="Mode").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(
            baseline,
            textvariable=self.baseline_mode,
            values=("auto", "off", "bernstein", "whittaker"),
            state="readonly",
            width=12,
        ).grid(row=0, column=1, sticky="w", pady=4)
        ttk.Checkbutton(baseline, text="Apply to 1H", variable=self.baseline_apply_1h).grid(row=0, column=2, sticky="w", padx=(12, 0), pady=4)
        ttk.Checkbutton(baseline, text="Apply to 13C", variable=self.baseline_apply_13c).grid(row=0, column=3, sticky="w", padx=(12, 0), pady=4)
        ttk.Label(baseline, text="Bernstein order").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(baseline, textvariable=self.baseline_poly_order, width=8).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(baseline, text="Whittaker lambda").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(baseline, textvariable=self.whittaker_lambda, width=12).grid(row=2, column=1, sticky="w", pady=4)
        ttk.Label(baseline, text="Whittaker asymmetry").grid(row=2, column=2, sticky="e", padx=(12, 8), pady=4)
        ttk.Entry(baseline, textvariable=self.whittaker_asymmetry, width=10).grid(row=2, column=3, sticky="w", pady=4)

    def _build_check_page(self, parent: ttk.Frame) -> None:
        page = self._make_page(parent, "check")
        page.rowconfigure(0, weight=1)
        check_scroll = _ScrollableFrame(page, padding=2)
        self._scrollable_frames.append(check_scroll)
        check_scroll.grid(row=0, column=0, sticky="nsew")
        check_tab = check_scroll.content
        check_tab.columnconfigure(0, weight=1)

        check_box = ttk.LabelFrame(check_tab, text="Check existing support", padding=12, style="Card.TLabelframe")
        check_box.grid(row=0, column=0, sticky="ew")
        check_box.columnconfigure(1, weight=1)
        self._file_row(
            check_box,
            0,
            "Manifest",
            self.existing_manifest,
            lambda: self._browse_file(self.existing_manifest, [("Manifest JSON", "*.json"), ("All files", "*.*")]),
            optional=True,
            extra_button=("Check", self._start_manifest_check),
        )
        self._file_row(
            check_box,
            1,
            "Support .docx override",
            self.check_support_docx,
            lambda: self._browse_file(self.check_support_docx, [("Word documents", "*.docx"), ("All files", "*.*")]),
            optional=True,
        )

    def _build_patch_page(self, parent: ttk.Frame) -> None:
        page = self._make_page(parent, "patch")
        page.rowconfigure(0, weight=1)
        patch_scroll = _ScrollableFrame(page, padding=2)
        self._scrollable_frames.append(patch_scroll)
        patch_scroll.grid(row=0, column=0, sticky="nsew")
        patch_tab = patch_scroll.content
        patch_tab.columnconfigure(0, weight=1)

        patch_box = ttk.LabelFrame(patch_tab, text="Patch existing support", padding=12, style="Card.TLabelframe")
        patch_box.grid(row=0, column=0, sticky="ew")
        patch_box.columnconfigure(1, weight=1)
        self._folder_row(
            patch_box,
            0,
            "Existing output folder",
            self.patch_source_output_dir,
            self._browse_patch_source_output,
        )
        self._file_row(
            patch_box,
            1,
            "Existing support .docx override",
            self.check_support_docx,
            lambda: self._browse_file(self.check_support_docx, [("Word documents", "*.docx"), ("All files", "*.*")]),
            optional=True,
        )
        ttk.Label(patch_box, text="Operation").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        operation_frame = ttk.Frame(patch_box)
        operation_frame.grid(row=2, column=1, columnspan=2, sticky="w", pady=4)
        for value, label in (
            ("renumber", "Renumber"),
            ("remove", "Remove"),
            ("reorder", "Reorder"),
            ("swap", "Swap compounds"),
        ):
            ttk.Radiobutton(
                operation_frame,
                text=label,
                variable=self.patch_operation,
                value=value,
                command=self._on_patch_operation_changed,
            ).pack(side="left", padx=(0, 14))
        ttk.Label(patch_box, textvariable=self.patch_instruction_label).grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(patch_box, textvariable=self.patch_instruction).grid(row=3, column=1, sticky="ew", pady=4)
        ttk.Label(patch_box, textvariable=self.patch_instruction_example, style="Muted.TLabel").grid(
            row=3, column=2, sticky="w", padx=(8, 0), pady=4
        )

    def _build_add_page(self, parent: ttk.Frame) -> None:
        page = self._make_page(parent, "add")
        page.rowconfigure(0, weight=1)
        add_scroll = _ScrollableFrame(page, padding=2)
        self._scrollable_frames.append(add_scroll)
        add_scroll.grid(row=0, column=0, sticky="nsew")
        add_tab = add_scroll.content
        add_tab.columnconfigure(0, weight=1)

        add_box = ttk.LabelFrame(add_tab, text="Add compounds", padding=12, style="Card.TLabelframe")
        add_box.grid(row=0, column=0, sticky="ew")
        add_box.columnconfigure(1, weight=1)
        self._folder_row(add_box, 0, "Previous output folder", self.add_previous_output_dir, self._browse_add_previous_output, optional=True)
        self._file_row(add_box, 1, "Existing manifest", self.add_manifest, lambda: self._browse_file(self.add_manifest, [("Manifest JSON", "*.json"), ("All files", "*.*")]), optional=True)
        self._file_row(add_box, 2, "Existing support .docx", self.add_support_docx, lambda: self._browse_file(self.add_support_docx, [("Word documents", "*.docx"), ("All files", "*.*")]), optional=True)
        ttk.Label(add_box, text="Add mode").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        add_mode = ttk.Frame(add_box)
        add_mode.grid(row=3, column=1, columnspan=2, sticky="w", pady=4)
        ttk.Radiobutton(add_mode, text="Same series", variable=self.add_method_mode, value="same_series").pack(side="left")
        ttk.Radiobutton(add_mode, text="New method", variable=self.add_method_mode, value="new_method").pack(side="left", padx=(16, 0))
        ttk.Label(
            add_box,
            text="Same series reuses old template/reaction schema. New method can use new template/schema/scope; spectra settings stay from Processing.",
            foreground=self._theme["muted"],
        ).grid(row=4, column=1, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Label(add_box, text="New compound table").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Label(add_box, text="Word table with ChemDraw OLE structures (.docx)", style="Muted.TLabel").grid(
            row=5,
            column=1,
            columnspan=2,
            sticky="w",
            pady=4,
        )
        self._file_row(add_box, 6, "New compound table", self.add_input_path, self._browse_add_input, optional=True)
        self._source_row(
            add_box,
            7,
            "New spectra source",
            self.add_spectra_source,
            lambda: self._browse_file(self.add_spectra_source, [("Zip archives", "*.zip"), ("All files", "*.*")]),
            lambda: self._browse_folder(self.add_spectra_source),
            optional=True,
        )
        self._file_row(add_box, 8, "New SI template .docx", self.add_template_docx, lambda: self._browse_file(self.add_template_docx, [("Word documents", "*.docx"), ("All files", "*.*")]), optional=True)
        self._file_row(add_box, 9, "New Reaction_schema.docx", self.add_loadings_schema_docx, lambda: self._browse_file(self.add_loadings_schema_docx, [("Word documents", "*.docx"), ("All files", "*.*")]), optional=True)
        self._file_row(add_box, 10, "New Scope.docx", self.add_loadings_scope_docx, lambda: self._browse_file(self.add_loadings_scope_docx, [("Word documents", "*.docx"), ("All files", "*.*")]), optional=True)
        self._folder_row(add_box, 11, "Output folder", self.add_output_folder, self._browse_add_output_folder, optional=True)

    def _build_instructions_page(self, parent: ttk.Frame) -> None:
        page = self._make_page(parent, "instructions")
        page.rowconfigure(0, weight=1)
        instructions_scroll = _ScrollableFrame(page, padding=2)
        self._scrollable_frames.append(instructions_scroll)
        instructions_scroll.grid(row=0, column=0, sticky="nsew")
        content = instructions_scroll.content
        content.columnconfigure(0, weight=1)

        quick = self._instruction_block(content, 0, "Quick start", "Minimal path for a normal SI run.", expanded=True)
        ttk.Label(
            quick,
            text=(
                "1. Copy an example\n"
                "   - Click Copy all examples.\n"
                "   - Start with example_1 and edit copies of its Word files.\n"
                "2. Fill Generate\n"
                "   - Compound table: Compound_table.docx.\n"
                "   - Spectra source: Spectra_source folder or Spectra_source.zip.\n"
                "   - Output folder: choose where a separate run folder will be created.\n"
                "3. Optional settings\n"
                "   - In Generate, add an SI template, MestReNova path/styles, or reagent-loading files if needed.\n"
                "   - Open Processing for spectra mode, peak thresholds, ppm ranges, baseline correction, and checks.\n"
                "4. Run\n"
                "   - Click Generate SI.\n"
                "   - Open Results when the run finishes."
            ),
            wraplength=760,
            justify="left",
        ).grid(row=0, column=0, sticky="ew")

        generate = self._instruction_block(content, 1, "Generate", "Main inputs needed to build a new SI.", expanded=True)
        ttk.Label(
            generate,
            text=(
                "Required fields\n"
                "- Compound table: upload Compound_table.docx with compound data and ChemDraw OLE structures.\n"
                "- Spectra source: upload a .zip archive or choose a folder with raw spectra.\n"
                "- Output folder: choose where the run folder will be created.\n"
                "- Optional inputs: add SI_template.docx, MestReNova.exe, and separate 1H/13C .mngp files when defaults are not enough.\n"
                "- Reagent Loadings: enable this block and provide Reaction_schema.docx plus Scope.docx to calculate amounts.\n"
                "- Generate SI: starts SI generation.\n\n"
                "Important rules\n"
                "- Compound numbers in the table must match spectra folder names, for example 3a, 3b, 3c.\n"
                "- The Word table should contain editable ChemDraw OLE structures in the structure column.\n"
                "- Every run writes a separate output folder with docx, input copies, spectra, Mnova files, logs and reports."
            ),
            wraplength=760,
            justify="left",
        ).grid(row=0, column=0, sticky="ew")

        processing = self._instruction_block(content, 2, "Processing", "Spectra controls, preprocessing, and validation options.")
        ttk.Label(
            processing,
            text=(
                "Spectra rendering\n"
                "- Spectra appendix: choose png, mnova or none.\n"
                "- png: inserts static pictures.\n"
                "- mnova: inserts clickable Mnova spectrum objects.\n"
                "- none: skips spectra appendix.\n"
                "- PPM ranges: control exported image windows for 1H and 13C.\n"
                "- Target signal height: controls vertical scaling of the highest signal.\n\n"
                "Peak picking and baseline\n"
                "- 1H threshold / 13C threshold: minimum relative peak height. Increase if noise or impurities are picked.\n"
                "- Baseline mode: auto/off/Bernstein/Whittaker.\n"
                "- Whittaker settings: advanced baseline parameters for difficult 13C spectra.\n"
                "- Highlight solvent peaks: keep off for normal reports unless you explicitly want solvent peaks marked.\n\n"
                "Chemistry options\n"
                "- Check support: validates NMR, HRMS and elemental analysis when enough data are available.\n"
                "- Calculate elemental analysis: generates calculated elemental-analysis values for rows where this block is not explicitly disabled."
            ),
            wraplength=760,
            justify="left",
        ).grid(row=0, column=0, sticky="ew")

        results = self._instruction_block(content, 3, "Results", "Where generated files are stored.")
        ttk.Label(
            results,
            text=(
                "Buttons\n"
                "- Open support: opens generated support_information.docx.\n"
                "- Open output folder: opens the full run folder.\n"
                "- Open logs: opens diagnostic logs for Word, ChemDraw and Mnova automation.\n"
                "- Open report: opens the readable run report.\n\n"
                "Output folder structure\n"
                "- docx: final support and manifest.\n"
                "- input: copied input files used for this run.\n"
                "- spectra: exported spectrum pictures.\n"
                "- mnova: processed Mnova files.\n"
                "- logs: automation diagnostics.\n"
                "- reports: NMR text reports and validation summaries."
            ),
            wraplength=760,
            justify="left",
        ).grid(row=0, column=0, sticky="ew")

        templates = self._instruction_block(content, 4, "Example files", "Open or copy editable starter files.", expanded=True)
        templates.columnconfigure(1, weight=1)
        ttk.Button(templates, text="Copy all examples", command=self._copy_starter_files).grid(row=0, column=2, sticky="e", padx=(8, 0), pady=(0, 8))
        for row, (label, relative_path, description) in enumerate(INSTRUCTION_TEMPLATE_FILES, start=1):
            ttk.Label(templates, text=label, font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=3)
            ttk.Label(templates, text=description, wraplength=560, justify="left").grid(row=row, column=1, sticky="ew", pady=3)
            ttk.Button(
                templates,
                text="Open",
                command=lambda relative_path=relative_path: self._open_example_file(relative_path),
            ).grid(row=row, column=2, sticky="e", padx=(8, 0), pady=3)

        spectra = self._instruction_block(content, 5, "Spectra source", "How raw spectra should be organized.")
        ttk.Label(
            spectra,
            text=(
                "Accepted input\n"
                "- A .zip archive, for example Spectra_source.zip.\n"
                "- Or a normal folder with the same internal layout.\n\n"
                "Required layout\n"
                "- Top level: one folder per compound number, for example 3a, 3b, 3c.\n"
                "- Inside each compound folder: raw Bruker experiment folders containing fid files.\n"
                "- Folder names inside each compound can be arbitrary.\n\n"
                "Detection\n"
                "- The program searches for fid files.\n"
                "- Acquisition metadata is used to decide whether a spectrum is 1H or 13C.\n"
                "- Compound numbers in spectra source and compound table must be identical."
            ),
            wraplength=760,
            justify="left",
        ).grid(row=0, column=0, sticky="ew")

        aliases = self._instruction_block(content, 6, "Template aliases", "Placeholders available inside SI_template.docx.")
        self._build_alias_reference(aliases)

        check = self._instruction_block(content, 7, "Check", "Validate an existing generated SI.")
        ttk.Label(
            check,
            text=(
                "Fields\n"
                "- Existing manifest: upload support_information.manifest.json from a previous run.\n"
                "- Support .docx override: optional. Use only if the support file was moved or renamed.\n\n"
                "What it checks\n"
                "- Manifest structure and compound order.\n"
                "- Support file, bookmarks, linked artifacts and unresolved template aliases.\n"
                "- Analytical NMR/HRMS/elemental-analysis warnings are calculated during Generate and saved in its reports.\n\n"
                "Output\n"
                "- JSON check report.\n"
                "- Short readable summary in the GUI."
            ),
            wraplength=760,
            justify="left",
        ).grid(row=0, column=0, sticky="ew")

        patch = self._instruction_block(content, 8, "Patch", "Create a modified copy of an existing SI.")
        ttk.Label(
            patch,
            text=(
                "Fields\n"
                "- Existing output folder: select the complete folder from the run you want to modify. "
                "The app finds the manifest and support document automatically.\n"
                "- Existing support .docx override: optional path if the old support was moved.\n"
                "- The new patch run is created automatically next to the selected run.\n\n"
                "Choose exactly one operation\n"
                "- Renumber: comma-separated map, for example 2a=3a,2b=3b.\n"
                "- Remove: compound numbers to remove, for example 2a,2c.\n"
                "- Reorder: complete final compound order.\n"
                "- Swap compounds: exchange complete compound assignments while preserving the visible number order. "
                "Any number of non-overlapping pairs is allowed, for example 2a=3a,2b=3b.\n\n"
                "Output\n"
                "- Every patch writes a new run folder with docx, manifest, report, and logs.\n"
                "- The old support is not edited in place."
            ),
            wraplength=760,
            justify="left",
        ).grid(row=0, column=0, sticky="ew")

        add = self._instruction_block(content, 9, "Add", "Append new compounds to an old SI.")
        ttk.Label(
            add,
            text=(
                "Fields\n"
                "- Previous output folder: choose the old run folder; the app fills manifest and support automatically when possible.\n"
                "- Existing manifest: upload manifest from the old run when no previous output folder is selected.\n"
                "- Existing support .docx: optional override if the old support file was moved.\n"
                "- Add mode: choose how formatting and processing settings are selected.\n"
                "- New compound table: upload a Word table containing only new compounds.\n"
                "- New spectra source: optional folder or zip with spectra only for the new compounds.\n"
                "- New SI template: optional. In Same series it overrides the old template; in New method it defines the new method layout.\n"
                "- New Reaction_schema: optional in Same series if the old schema should be reused; required for new loadings in New method.\n"
                "- New Scope: new scope table for the added compounds. Required when loadings are enabled.\n"
                "- Output folder: folder where the app creates a new run folder and combined support file.\n\n"
                "Add modes\n"
                "- Same series: reuses old template, Reaction_schema, Mnova styles, ppm ranges, thresholds, baseline, checks and loadings mode.\n"
                "- Same series never reuses old Scope, compound table or spectra source. These must come from this Add page.\n"
                "- New method: can use new template, Reaction_schema and Scope. Spectra display/preprocessing settings stay unified with Processing.\n"
                "- Both modes stop if a new compound number already exists in the old manifest.\n\n"
                "Current workflow\n"
                "- Loads the old manifest and old support.\n"
                "- Reads new compounds from the new table.\n"
                "- Stops if any new compound number already exists in the old manifest.\n"
                "- Generates a temporary support for the new compounds using the normal Generate pipeline.\n"
                "- Copies bookmarked new compound blocks into the old support.\n"
                "- Copies new spectra appendix entries after the old appendix.\n"
                "- Writes a merged manifest and an add_report JSON into the new run folder.\n\n"
                "Limitations\n"
                "- Old compound blocks are not regenerated.\n"
                "- The old support file is never edited in place."
            ),
            wraplength=760,
            justify="left",
        ).grid(row=0, column=0, sticky="ew")

    def _build_alias_reference(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        row = 0
        ttk.Label(
            parent,
            text=(
                "Use aliases in Word as {Object.attribute}. Formatting is inherited from the placeholder: "
                "if the placeholder is bold or italic, the inserted value keeps that style."
            ),
            wraplength=760,
            justify="left",
        ).grid(row=row, column=0, sticky="ew", pady=(0, 10))
        row += 1

        row = self._alias_table(
            parent,
            row,
            "Product aliases",
            (
                ("{Product.name}", "ChemDraw structure / compound table", "Generated nomenclature name of the product."),
                ("{Product.number}", "Compound table", "Product number used in the SI, spectra folders, and captions."),
                ("{Product.mg}", "Scope.docx or yield text", "Product mass in milligrams."),
                ("{Product.g}", "Calculated from Product.mg", "Product mass in grams: mg / 1000."),
                ("{Product.kg}", "Calculated from Product.mg", "Product mass in kilograms: mg / 1,000,000."),
                ("{Product.mmol}", "Scope.docx + product structure/MW", "Product amount in mmol: product mass / molecular weight."),
                ("{Product.mol}", "Calculated from Product.mmol", "Product amount in mol: mmol / 1000."),
                ("{Product.structure}", "Word compound table", "Editable product structure inserted as the ChemDraw OLE object."),
                ("{Product.nmr.1h.picture}", "Processed spectra", "1H spectrum appendix object: PNG or clickable Mnova object, depending on GUI choice."),
                ("{Product.nmr.13c.picture}", "Processed spectra", "13C spectrum appendix object: PNG or clickable Mnova object, depending on GUI choice."),
                ("{Product.yield.percent}", "Scope.docx + limiting scale", "Product yield percent calculated from product mmol and reaction scale."),
                ("{Product.appearance}", "Compound table", "Color and physical state, for example white solid."),
                ("{Product.mp}", "Compound table", "Melting point without the °C suffix."),
                ("{Product.rf.value}", "Compound table Rf field", "Rf value only."),
                ("{Product.rf.system}", "Compound table Rf field", "TLC eluent system from parentheses."),
                ("{Product.preparation}", "Template/loadings workflow", "Prepared synthetic description paragraph for the product."),
                ("{Product.support.warning}", "Support check", "Red warning text if NMR/HRMS/elemental-analysis validation found a mismatch."),
            ),
        )
        row = self._alias_table(
            parent,
            row,
            "Reagent aliases",
            (
                ("{Reagent_1.name}", "Scope.docx structure / Reaction_schema.docx", "Generated or fallback name of reagent 1."),
                ("{Reagent_1.mg}", "Scope.docx / calculated from eq and MW", "Reagent mass in milligrams."),
                ("{Reagent_1.g}", "Calculated from Reagent_1.mg", "Reagent mass in grams: mg / 1000."),
                ("{Reagent_1.kg}", "Calculated from Reagent_1.mg", "Reagent mass in kilograms: mg / 1,000,000."),
                ("{Reagent_1.mmol}", "Reaction_schema.docx + reaction scale", "Reagent amount in mmol."),
                ("{Reagent_1.mol}", "Calculated from Reagent_1.mmol", "Reagent amount in mol: mmol / 1000."),
                ("{Reagent_1.mcl}", "Density or concentration calculation", "Reagent volume in microliters."),
                ("{Reagent_1.ml}", "Calculated from mcl or concentration", "Reagent volume in milliliters."),
                ("{Reagent_1.l}", "Calculated from ml", "Reagent volume in liters."),
                ("{Reagent_1.eq}", "Reaction_schema.docx", "Equivalents of the reagent relative to the limiting scale."),
                ("{K2CO3.mg}", "Named row in Reaction_schema.docx", "Same attributes work for named common reagents."),
                ("{AcOH.mcl}", "Named row + density", "Example of a named liquid reagent volume in microliters."),
                ("{AcOH.mmol}", "Named row + equivalents", "Example of a named reagent amount in mmol."),
            ),
        )
        row = self._alias_table(
            parent,
            row,
            "Solvent aliases",
            (
                ("{Solvent_MeCN.name}", "Reaction_schema.docx", "Displayed solvent name. Solvent_MeCN is shown as MeCN."),
                ("{Solvent_MeCN.mcl}", "Reaction scale / concentration", "Solvent volume in microliters."),
                ("{Solvent_MeCN.ml}", "Reaction scale / concentration", "Solvent volume in milliliters."),
                ("{Solvent_MeCN.l}", "Calculated from ml", "Solvent volume in liters."),
            ),
        )
        row = self._alias_table(
            parent,
            row,
            "NMR aliases",
            (
                ("{nmr.1h.label}", "Mnova report / input table", "1H NMR label, usually 1H NMR."),
                ("{nmr.1h.conditions}", "Mnova report / input table", "1H NMR solvent and frequency, for example CDCl3, 600 MHz."),
                ("{nmr.1h.peaks}", "Mnova report / input table", "1H NMR peak list after delta =."),
                ("{nmr.13c.label}", "Mnova report / input table", "13C NMR label, usually 13C{1H} NMR."),
                ("{nmr.13c.conditions}", "Mnova report / input table", "13C NMR solvent and frequency."),
                ("{nmr.13c.peaks}", "Mnova report / input table", "13C NMR peak list after delta =."),
                ("{nmr.extra}", "Input table", "Additional NMR lines, for example 19F NMR."),
            ),
        )
        row = self._alias_table(
            parent,
            row,
            "HRMS, elemental analysis, IR",
            (
                ("{hrms.label}", "Input table / HRMS settings", "HRMS method label."),
                ("{hrms.adduct}", "Input table / default adduct", "Ion adduct, for example [M+H]+."),
                ("{hrms.formula}", "Structure formula + adduct", "Calculated ion formula with isotope labels when applicable."),
                ("{hrms.calculated}", "Formula calculation", "Calculated m/z value."),
                ("{hrms.found}", "Input table", "Experimental found m/z value."),
                ("{anal.label}", "Elemental-analysis block", "Elemental analysis label, usually Anal."),
                ("{anal.formula}", "Product formula", "Formula used for elemental analysis."),
                ("{anal.calculated}", "Formula calculation", "Calculated C/H/N/etc percentages."),
                ("{anal.found}", "Input table", "Experimental elemental analysis values."),
                ("{ir.label}", "IR parser", "IR label."),
                ("{ir.method}", "IR parser / default", "IR method, for example KBr."),
                ("{ir.peaks}", "Input table", "IR peak list in cm-1."),
                ("{reaction.loadings}", "Reaction loading block", "Fallback full loading line if the template uses automatic loading text."),
            ),
        )

    def _alias_table(self, parent: ttk.Frame, row: int, title: str, rows: tuple[tuple[str, str, str], ...]) -> int:
        ttk.Label(parent, text=title, font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="w", pady=(8, 4))
        row += 1
        table = ttk.Frame(parent)
        table.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        table.columnconfigure(0, weight=0)
        table.columnconfigure(1, weight=1)
        table.columnconfigure(2, weight=2)
        headers = ("Alias", "Source", "Meaning")
        for col, header in enumerate(headers):
            ttk.Label(table, text=header, font=("Segoe UI", 9, "bold"), padding=(6, 4), relief="solid").grid(
                row=0,
                column=col,
                sticky="nsew",
            )
        for item_row, (alias, source, meaning) in enumerate(rows, start=1):
            ttk.Label(table, text=alias, font=("Consolas", 9), padding=(6, 3), relief="solid").grid(row=item_row, column=0, sticky="nsew")
            ttk.Label(table, text=source, wraplength=190, padding=(6, 3), relief="solid", justify="left").grid(row=item_row, column=1, sticky="nsew")
            ttk.Label(table, text=meaning, wraplength=330, padding=(6, 3), relief="solid", justify="left").grid(row=item_row, column=2, sticky="nsew")
        return row + 1

    def _instruction_block(self, parent: ttk.Frame, row: int, title: str, summary: str, *, expanded: bool = False) -> ttk.Frame:
        block = _CollapsibleInstructionBlock(parent, title=title, summary=summary, theme=self._theme, expanded=expanded)
        block.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        block.columnconfigure(0, weight=1)
        self._instruction_blocks.append(block)
        return block.body

    def _show_page(self, page: str) -> None:
        page_text = {
            "generate": ("Generate SI", "Create formatted Supporting Information from a compound table and spectra."),
            "advanced": ("Processing", "Spectra rendering, peak picking, baseline correction, and validation."),
            "check": ("Check support", "Run validation from an existing manifest and optional support document."),
            "patch": ("Patch SI", "Modify an existing generated output without reprocessing spectra."),
            "add": ("Add compounds", "Append new compound blocks and spectra to an existing support document."),
            "instructions": ("Instructions", "Short guide for everyday use of Auto Support Generator."),
        }
        for key, frame in self._page_frames.items():
            if key == page:
                frame.grid()
            else:
                frame.grid_remove()
        for key, button in self._nav_buttons.items():
            button.set_selected(key == page)
        title, subtitle = page_text.get(page, page_text["generate"])
        self.page_title.set(title)
        self.page_subtitle.set(subtitle)
        self._current_page = page
        actions = {
            "generate": ("Generate SI", self._start_generation),
            "advanced": ("Generate SI", self._start_generation),
            "check": ("Check support", self._start_manifest_check),
            "patch": ("Apply patch", self._start_patch),
            "add": ("Add compounds", self._start_add_compounds),
        }
        action = actions.get(page)
        if action is None:
            self.run_button.grid_remove()
        else:
            label, command = action
            self.run_button.configure(text=label, command=command)
            self.run_button.grid()

    def _set_theme_mode(self, mode: str) -> None:
        if mode not in THEME_PALETTES:
            mode = "light"
        self.theme_mode.set(mode)
        self.dark_theme.set(mode == "dark")
        self._configure_style()
        self._save_settings()

    def _toggle_theme(self) -> None:
        self._set_theme_mode("dark" if self.dark_theme.get() else "light")

    def _apply_theme_to_non_ttk_widgets(self) -> None:
        theme = getattr(self, "_theme", THEME_PALETTES["light"])
        if hasattr(self, "log"):
            self.log.configure(background=theme["log_bg"], foreground=theme["log_fg"], insertbackground=theme["log_fg"])
        for scrollable in getattr(self, "_scrollable_frames", []):
            try:
                scrollable.canvas.configure(background=theme["app_bg"])
            except tk.TclError:
                pass
        for button in getattr(self, "_sidebar_buttons", []):
            button.set_theme(theme)
        for block in getattr(self, "_instruction_blocks", []):
            block.set_theme(theme)
        if self._theme_switch is not None:
            self._theme_switch.set_theme(theme)
            self._theme_switch.set_mode(self.theme_mode.get())

    def _source_row(self, parent, row: int, label: str, variable: StringVar, file_command, folder_command, optional: bool = False) -> None:
        ttk.Label(parent, text=f"{label}{' (optional)' if optional else ''}").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        button_box = ttk.Frame(parent)
        button_box.grid(row=row, column=2, sticky="e", padx=(8, 0), pady=4)
        ttk.Button(button_box, text="Zip...", command=file_command).pack(side="left", padx=(0, 6))
        ttk.Button(button_box, text="Folder...", command=folder_command).pack(side="left")

    def _file_row(self, parent, row: int, label: str, variable: StringVar, command, optional: bool = False, extra_button=None) -> None:
        ttk.Label(parent, text=f"{label}{' (optional)' if optional else ''}").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        button_box = ttk.Frame(parent)
        button_box.grid(row=row, column=2, sticky="e", padx=(8, 0), pady=4)
        if extra_button:
            text, extra_command = extra_button
            ttk.Button(button_box, text=text, command=extra_command).pack(side="left", padx=(0, 6))
        ttk.Button(button_box, text="Browse...", command=command).pack(side="left")

    def _folder_row(self, parent, row: int, label: str, variable: StringVar, command, optional: bool = False) -> None:
        ttk.Label(parent, text=f"{label}{' (optional)' if optional else ''}").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(parent, text="Browse...", command=command).grid(row=row, column=2, sticky="e", padx=(8, 0), pady=4)

    def _result_row(self, parent, row: int, label: str, variable: StringVar, open_command=None, button_text: str = "Open") -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        entry = ttk.Entry(parent, textvariable=variable, state="readonly")
        entry.grid(row=row, column=1, sticky="ew", pady=3)
        if open_command:
            ttk.Button(parent, text=button_text, command=open_command).grid(row=row, column=2, sticky="e", padx=(8, 0), pady=3)

    def _browse_input(self) -> None:
        self.input_kind.set("word")
        self._browse_file(self.input_path, [("Word documents", "*.docx"), ("All files", "*.*")])
        if self.input_path.get() and not self.output_folder.get():
            self._set_output_folder(str(Path(self.input_path.get()).parent), save=False)

    def _browse_file(self, variable: StringVar, filetypes) -> None:
        kwargs: dict[str, object] = {"filetypes": filetypes}
        initialdir = _dialog_initialdir(variable.get(), self.input_path.get(), self.output_folder.get(), self.output_docx.get(), self._last_output_folder)
        if initialdir:
            kwargs["initialdir"] = initialdir
        path = filedialog.askopenfilename(**kwargs)
        if path:
            variable.set(path)
            self._save_settings()

    def _browse_folder(self, variable: StringVar) -> None:
        kwargs: dict[str, object] = {}
        initialdir = _dialog_initialdir(variable.get(), self.input_path.get(), self.output_folder.get(), self.output_docx.get(), self._last_output_folder)
        if initialdir:
            kwargs["initialdir"] = initialdir
        path = filedialog.askdirectory(**kwargs)
        if path:
            variable.set(path)
            self._save_settings()

    def _browse_spectra_source(self) -> None:
        self._browse_file(self.spectra_source, [("Zip archives", "*.zip"), ("All files", "*.*")])

    def _browse_spectra_folder(self) -> None:
        self._browse_folder(self.spectra_source)

    def _browse_output(self) -> None:
        kwargs: dict[str, object] = {
            "defaultextension": ".docx",
            "filetypes": [("Word documents", "*.docx"), ("All files", "*.*")],
            "initialfile": Path(self.output_docx.get()).name if self.output_docx.get() else "support_information.docx",
        }
        initialdir = _dialog_initialdir(self.output_folder.get(), self.output_docx.get(), self.input_path.get(), self._last_output_folder)
        if initialdir:
            kwargs["initialdir"] = initialdir
        path = filedialog.asksaveasfilename(**kwargs)
        if path:
            variable_path = Path(path)
            self.output_docx.set(str(variable_path))
            self.output_folder.set(str(variable_path.parent))
            self._save_settings()

    def _browse_output_folder(self) -> None:
        kwargs: dict[str, object] = {}
        initialdir = _dialog_initialdir(self.output_folder.get(), self.output_docx.get(), self.input_path.get(), self._last_output_folder)
        if initialdir:
            kwargs["initialdir"] = initialdir
        path = filedialog.askdirectory(**kwargs)
        if path:
            self._set_output_folder(path)

    def _browse_patch_source_output(self) -> None:
        before = self.patch_source_output_dir.get()
        self._browse_folder(self.patch_source_output_dir)
        selected = self.patch_source_output_dir.get()
        if selected and selected != before:
            try:
                _validate_patch_source_output_folder(Path(selected), require_support=False)
            except ValueError as exc:
                self.patch_source_output_dir.set(before)
                self._save_settings()
                messagebox.showerror("SI Generator", str(exc))

    def _on_patch_operation_changed(self, *, clear_instruction: bool = True) -> None:
        labels = {
            "renumber": ("Number mapping", "Example: 2a=3a,2b=3b"),
            "remove": ("Compounds", "Example: 2a,2c"),
            "reorder": ("Final order", "Example: 2b,2a,2c"),
            "swap": ("Swap pairs", "Example: 2a=3a,2b=3b"),
        }
        label, example = labels.get(self.patch_operation.get(), labels["renumber"])
        self.patch_instruction_label.set(label)
        self.patch_instruction_example.set(example)
        if clear_instruction:
            self.patch_instruction.set("")

    def _browse_add_input(self) -> None:
        self.add_input_kind.set("word")
        self._browse_file(self.add_input_path, [("Word documents", "*.docx"), ("All files", "*.*")])

    def _browse_add_previous_output(self) -> None:
        before = self.add_previous_output_dir.get()
        self._browse_folder(self.add_previous_output_dir)
        selected = self.add_previous_output_dir.get()
        if selected and selected != before:
            manifest, support = _previous_output_defaults(Path(selected))
            if manifest:
                self.add_manifest.set(str(manifest))
            if support:
                self.add_support_docx.set(str(support))
            self._save_settings()

    def _browse_add_output_folder(self) -> None:
        kwargs: dict[str, object] = {}
        initialdir = _dialog_initialdir(self.add_output_folder.get(), self.output_folder.get(), self.add_input_path.get(), self._last_output_folder)
        if initialdir:
            kwargs["initialdir"] = initialdir
        path = filedialog.askdirectory(**kwargs)
        if path:
            self.add_output_folder.set(path)
            self._save_settings()

    def _load_examples(self) -> None:
        examples = examples_dir()
        example = examples / "example_1"
        table = example / "Compound_table.docx"
        spectra = example / "Spectra_source"
        if not table.exists() or not spectra.exists():
            messagebox.showerror("Auto Support Generator", f"Example files were not found in:\n{examples}")
            return
        for field, value in _example_field_updates(table, spectra, default_output_path()).items():
            getattr(self, field).set(value)
        self._sync_output_docx_from_folder()
        self.status_text.set("Example loaded")
        self._save_settings()

    def _open_examples_folder(self) -> None:
        examples = examples_dir()
        examples.mkdir(parents=True, exist_ok=True)
        os.startfile(str(examples))

    def _open_example_file(self, relative_path: Path) -> None:
        path = examples_dir() / relative_path
        if not path.exists():
            messagebox.showerror("Auto Support Generator", f"Example file was not found:\n{path}")
            return
        os.startfile(str(path))

    def _copy_starter_files(self) -> None:
        kwargs: dict[str, object] = {"title": "Choose a folder for starter files"}
        initialdir = _dialog_initialdir(self.output_folder.get(), self.input_path.get(), self._last_output_folder)
        if initialdir:
            kwargs["initialdir"] = initialdir
        parent = filedialog.askdirectory(**kwargs)
        if not parent:
            return
        try:
            copied_to = copy_starter_files_to(parent)
        except Exception as exc:
            messagebox.showerror("Auto Support Generator", f"Could not copy starter files:\n{exc}")
            return
        self.status_text.set(f"Starter files copied: {copied_to}")
        os.startfile(str(copied_to))

    def _detect_mnova(self) -> None:
        try:
            path = find_mnova_executable()
        except Exception as exc:
            messagebox.showwarning("Auto Support Generator", str(exc))
            self.status_text.set("MestReNova not found")
            return
        self.mnova_exe.set(str(path))
        self.status_text.set("MestReNova detected")
        self._save_settings()

    def _start_generation(self) -> None:
        if self._is_running:
            messagebox.showinfo("SI Generator", "Generation is already running.")
            return

        try:
            request = self._build_request()
        except ValueError as exc:
            messagebox.showerror("SI Generator", str(exc))
            return

        self.log.clear()
        preflight_issues = preflight_generate_request(request)
        if _has_preflight_code(preflight_issues, "PREFLIGHT_OUTPUT_LOCKED"):
            original_output = request.output_path
            request.output_path = _next_available_docx_path(original_output)
            self.output_docx.set(str(request.output_path))
            self.log.write(
                "\n> Output file is open in Word\n"
                f"Locked: {original_output}\n"
                f"Using:  {request.output_path}\n"
            )
            preflight_issues = preflight_generate_request(request)
        if preflight_issues:
            self.log.write("\n> Preflight checks\n" + format_preflight_issues(preflight_issues) + "\n")
        if issue_has_errors(preflight_issues):
            self.status_text.set("Ready")
            messagebox.showerror("SI Generator", "Preflight checks failed:\n\n" + format_preflight_issues(preflight_issues))
            return

        self._save_settings()
        self._is_running = True
        self.run_button.configure(state="disabled")
        self.status_text.set("Running")
        self._clear_results()
        self.progress.start(12)
        self.log.write(
            "\n> Generate SI\n"
            f"Input: {request.input_path}\n"
            f"Output: {request.output_path}\n\n"
        )
        thread = threading.Thread(target=self._run_workflow, args=(request,), daemon=True)
        thread.start()

    def _start_manifest_check(self) -> None:
        if self._is_running:
            messagebox.showinfo("SI Generator", "Another operation is already running.")
            return
        try:
            request = _build_check_request(self.existing_manifest.get(), support_docx_text=self.check_support_docx.get())
        except ValueError as exc:
            messagebox.showerror("SI Generator", str(exc))
            return
        self._save_settings()
        self._start_background_operation(
            "Check manifest",
            f"Manifest: {request.manifest_path}\n",
            self._run_check_workflow,
            request,
        )

    def _start_patch(self) -> None:
        if self._is_running:
            messagebox.showinfo("SI Generator", "Another operation is already running.")
            return
        try:
            request = _build_patch_request(
                source_output_folder_text=self.patch_source_output_dir.get(),
                support_docx_text=self.check_support_docx.get(),
                operation_text=self.patch_operation.get(),
                instruction_text=self.patch_instruction.get(),
            )
        except ValueError as exc:
            messagebox.showerror("SI Generator", str(exc))
            return
        self._save_settings()
        self._start_background_operation(
            "Patch SI",
            f"Source output: {self.patch_source_output_dir.get()}\nNew patch run: auto\n",
            self._run_patch_workflow,
            request,
        )

    def _start_add_compounds(self) -> None:
        if self._is_running:
            messagebox.showinfo("SI Generator", "Another operation is already running.")
            return
        try:
            request = _build_add_compounds_request(
                manifest_text=self.add_manifest.get() or self.existing_manifest.get(),
                support_docx_text=self.add_support_docx.get(),
                previous_output_dir_text=self.add_previous_output_dir.get(),
                input_kind=self.add_input_kind.get(),
                method_mode_text=self.add_method_mode.get(),
                input_path_text=self.add_input_path.get(),
                output_folder_text=self.add_output_folder.get() or self.output_folder.get(),
                output_docx_text="",
                spectra_source_text=self.add_spectra_source.get(),
                template_docx_text=self.add_template_docx.get(),
                references_text="",
                loadings_schema_docx_text=self.add_loadings_schema_docx.get(),
                loadings_scope_docx_text=self.add_loadings_scope_docx.get(),
                mnova_exe_text=self.mnova_exe.get(),
                mnova_graphics_profile_text="",
                mnova_graphics_profile_1h_text=self.mnova_graphics_profile_1h.get(),
                mnova_graphics_profile_13c_text=self.mnova_graphics_profile_13c.get(),
                insert_spectra_as=self.insert_spectra_as.get(),
                target_signal_height_percent_text=self.target_signal_height_percent.get(),
                h1_ppm_min_text=self.h1_ppm_min.get(),
                h1_ppm_max_text=self.h1_ppm_max.get(),
                c13_ppm_min_text=self.c13_ppm_min.get(),
                c13_ppm_max_text=self.c13_ppm_max.get(),
                peak_threshold_1h_percent_text=self.peak_threshold_1h_percent.get(),
                peak_threshold_13c_percent_text=self.peak_threshold_13c_percent.get(),
                baseline_mode_text=self.baseline_mode.get(),
                baseline_apply_1h=self.baseline_apply_1h.get(),
                baseline_apply_13c=self.baseline_apply_13c.get(),
                baseline_poly_order_text=self.baseline_poly_order.get(),
                whittaker_lambda_text=self.whittaker_lambda.get(),
                whittaker_asymmetry_text=self.whittaker_asymmetry.get(),
                highlight_solvent_peaks=self.highlight_solvent_peaks.get(),
                generate_loadings=self.generate_loadings.get(),
                calculate_elemental_analysis=self.calculate_elemental_analysis.get(),
                check_support=self.check_support.get(),
            )
        except ValueError as exc:
            messagebox.showerror("SI Generator", str(exc))
            return
        self._save_settings()
        try:
            from .workflows.add_compounds import run_add_compounds
        except ImportError:
            self.log.write(
                "\n> Add compounds\n"
                "The Add compounds backend workflow is not available in this build yet.\n"
            )
            messagebox.showinfo("SI Generator", "Add compounds workflow is not available in this build yet.")
            return
        self._start_background_operation(
            "Add compounds",
            f"Manifest: {request.manifest_path}\nNew table: {request.input_path}\nOutput folder: {request.output_folder or request.output_docx}\n",
            self._run_add_compounds_workflow,
            (run_add_compounds, request),
        )

    def _start_background_operation(self, title: str, details: str, target, request) -> None:
        self._is_running = True
        self.run_button.configure(state="disabled")
        self.status_text.set("Running")
        self.progress.start(12)
        self.log.clear()
        self.log.write(f"\n> {title}\n{details}\n")
        thread = threading.Thread(target=target, args=(request,), daemon=True)
        thread.start()

    def _build_request(self) -> GenerateSIRequest:
        return _build_generate_request(
            input_kind=self.input_kind.get(),
            input_path_text=self.input_path.get(),
            output_docx_text=_output_docx_from_folder(self.output_folder.get(), self.output_docx.get()),
            spectra_source_text=self.spectra_source.get(),
            template_docx_text=self.template_docx.get(),
            references_text="",
            loadings_schema_text=self.loadings_schema_docx.get(),
            loadings_scope_text=self.loadings_scope_docx.get(),
            mnova_exe_text=self.mnova_exe.get(),
            mnova_graphics_profile_text="",
            mnova_graphics_profile_1h_text=self.mnova_graphics_profile_1h.get(),
            mnova_graphics_profile_13c_text=self.mnova_graphics_profile_13c.get(),
            insert_spectra_as=self.insert_spectra_as.get(),
            target_signal_height_percent_text=self.target_signal_height_percent.get(),
            h1_ppm_min_text=self.h1_ppm_min.get(),
            h1_ppm_max_text=self.h1_ppm_max.get(),
            c13_ppm_min_text=self.c13_ppm_min.get(),
            c13_ppm_max_text=self.c13_ppm_max.get(),
            peak_threshold_1h_percent_text=self.peak_threshold_1h_percent.get(),
            peak_threshold_13c_percent_text=self.peak_threshold_13c_percent.get(),
            baseline_mode_text=self.baseline_mode.get(),
            baseline_apply_1h=self.baseline_apply_1h.get(),
            baseline_apply_13c=self.baseline_apply_13c.get(),
            baseline_poly_order_text=self.baseline_poly_order.get(),
            whittaker_lambda_text=self.whittaker_lambda.get(),
            whittaker_asymmetry_text=self.whittaker_asymmetry.get(),
            highlight_solvent_peaks=self.highlight_solvent_peaks.get(),
            generate_loadings=self.generate_loadings.get(),
            calculate_elemental_analysis=self.calculate_elemental_analysis.get(),
            check_support=self.check_support.get(),
        )

    def _run_workflow(self, request: GenerateSIRequest) -> None:
        writer = _QueueWriter(self._log_queue)
        try:
            with redirect_stdout(writer), redirect_stderr(writer):
                result = run_generate_si(request)
            for issue in result.get("issues", []):
                self._log_queue.put(f"[{issue.get('severity', 'warning').upper()}] {issue.get('code', 'GENERATE')}: {issue.get('message', '')}\n")
            summary = _build_result_summary(result)
            if manifest_has_errors(result.get("issues", [])):
                self._log_queue.put(f"\nGeneration failed. Intended DOCX path: {summary.get('support_docx', '')}\n")
            else:
                self._log_queue.put(f"\nGenerated {summary['support_docx']}\n")
            if summary.get("processed_spectra_zip"):
                self._log_queue.put(f"Spectra package: {summary['processed_spectra_zip']}\n")
            if summary.get("manifest"):
                self._log_queue.put(f"Manifest: {summary['manifest']}\n")
            if summary.get("run_summary"):
                self._log_queue.put(f"Run summary: {summary['run_summary']}\n")
            if summary.get("input_warnings"):
                self._log_queue.put(f"Input warnings: {summary['input_warnings']}\n")
            if summary.get("support_warnings"):
                self._log_queue.put(f"Support warnings: {summary['support_warnings']}\n")
            if manifest_has_errors(result.get("issues", [])):
                self._log_queue.put("\nGeneration failed.\n")
                self._log_queue.put({"type": "run_failed", "error": "Generation failed", "summary": summary, "issues": result.get("issues", [])})
            else:
                self._log_queue.put("\nDone.\n")
                self._log_queue.put({"type": "run_succeeded", "summary": summary})
        except Exception as exc:
            self._log_queue.put(f"\nERROR: {exc}\n")
            self._log_queue.put({"type": "run_failed", "error": str(exc)})
        finally:
            self._log_queue.put("__RUN_FINISHED__")

    def _run_check_workflow(self, request: CheckSIRequest) -> None:
        try:
            result = run_check_si(request)
            for issue in result.get("issues", []):
                self._log_queue.put(f"[{issue.get('severity', 'warning').upper()}] {issue.get('code', 'CHECK')}: {issue.get('message', '')}\n")
            summary = _build_check_summary(result, request)
            if summary.get("run_summary"):
                self._log_queue.put(f"Check report: {summary['run_summary']}\n")
            if manifest_has_errors(result.get("issues", [])):
                self._log_queue.put("\nManifest check failed.\n")
                self._log_queue.put({"type": "run_failed", "error": "Manifest check failed", "summary": summary, "issues": result.get("issues", [])})
            else:
                self._log_queue.put("\nManifest check passed.\n")
                self._log_queue.put({"type": "run_succeeded", "summary": summary})
        except Exception as exc:
            self._log_queue.put(f"\nERROR: {exc}\n")
            self._log_queue.put({"type": "run_failed", "error": str(exc)})
        finally:
            self._log_queue.put("__RUN_FINISHED__")

    def _run_patch_workflow(self, request: PatchSIRequest) -> None:
        try:
            result = run_patch_si(request)
            for issue in result.get("issues", []):
                self._log_queue.put(f"[{issue.get('severity', 'warning').upper()}] {issue.get('code', 'PATCH')}: {issue.get('message', '')}\n")
            summary = _build_patch_summary(result)
            if summary.get("run_summary"):
                self._log_queue.put(f"Patch report: {summary['run_summary']}\n")
            if manifest_has_errors(result.get("issues", [])):
                self._log_queue.put("\nPatch check failed.\n")
                self._log_queue.put({"type": "run_failed", "error": "Patch check failed", "summary": summary, "issues": result.get("issues", [])})
            else:
                self._log_queue.put(f"\nPatched {summary.get('support_docx', '')}\n")
                if summary.get("manifest"):
                    self._log_queue.put(f"Manifest: {summary['manifest']}\n")
                self._log_queue.put("\nDone.\n")
                self._log_queue.put({"type": "run_succeeded", "summary": summary})
        except Exception as exc:
            self._log_queue.put(f"\nERROR: {exc}\n")
            self._log_queue.put({"type": "run_failed", "error": str(exc)})
        finally:
            self._log_queue.put("__RUN_FINISHED__")

    def _run_add_compounds_workflow(self, payload) -> None:
        run_add_compounds, request = payload
        try:
            result = run_add_compounds(request)
            for issue in result.get("issues", []):
                self._log_queue.put(f"[{issue.get('severity', 'warning').upper()}] {issue.get('code', 'ADD')}: {issue.get('message', '')}\n")
            summary = _build_add_compounds_summary(result)
            if summary.get("run_summary"):
                self._log_queue.put(f"Add compounds report: {summary['run_summary']}\n")
            if manifest_has_errors(result.get("issues", [])):
                self._log_queue.put("\nAdd compounds failed.\n")
                self._log_queue.put({"type": "run_failed", "error": "Add compounds failed", "summary": summary, "issues": result.get("issues", [])})
            else:
                self._log_queue.put(f"\nGenerated {summary.get('support_docx', '')}\n")
                self._log_queue.put({"type": "run_succeeded", "summary": summary})
        except Exception as exc:
            self._log_queue.put(f"\nERROR: {exc}\n")
            self._log_queue.put({"type": "run_failed", "error": str(exc)})
        finally:
            self._log_queue.put("__RUN_FINISHED__")

    def _poll_log_queue(self) -> None:
        try:
            while True:
                item = self._log_queue.get_nowait()
                if item == "__RUN_FINISHED__":
                    self._is_running = False
                    self.run_button.configure(state="normal")
                    self.progress.stop()
                elif isinstance(item, dict) and item.get("type") == "run_succeeded":
                    self.status_text.set("Done")
                    self._apply_result_summary(item.get("summary", {}))
                elif isinstance(item, dict) and item.get("type") == "run_failed":
                    self.status_text.set("Failed")
                    if isinstance(item.get("summary"), dict):
                        self._apply_result_summary(item.get("summary", {}))
                    messagebox.showerror("SI Generator", _failure_dialog_message(item))
                else:
                    self.log.write(item)
        except queue.Empty:
            pass
        self._poll_after_id = self.root.after(100, self._poll_log_queue)

    def _open_output_folder(self) -> None:
        path = self._last_output_folder or Path(self.output_folder.get() or self.output_docx.get() or ".").expanduser()
        folder = path if path.is_dir() else path.parent
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))

    def _open_result_path(self, variable: StringVar, label: str) -> None:
        try:
            path = _existing_result_path(variable.get(), label)
        except ValueError as exc:
            messagebox.showinfo("Auto Support Generator", str(exc))
            return
        os.startfile(str(path))

    def _clear_results(self) -> None:
        self.result_support.set("")
        self.result_output_folder.set("")
        self.result_manifest.set("")
        self.result_report.set("")
        self.result_logs.set("")
        self.result_overview.set("")

    def _apply_result_summary(self, summary: dict[str, str]) -> None:
        self.result_support.set(summary.get("support_docx", ""))
        self.result_manifest.set(summary.get("manifest", ""))
        self.result_report.set(summary.get("run_summary", ""))
        self.result_logs.set(summary.get("logs_dir", ""))
        self.result_overview.set(summary.get("overview", ""))
        output_folder = summary.get("output_folder") or _summary_output_folder(summary)
        self.result_output_folder.set(output_folder)
        if output_folder:
            self._last_output_folder = Path(output_folder).expanduser()
            self.patch_source_output_dir.set(output_folder)
        if summary.get("manifest"):
            self.existing_manifest.set(summary["manifest"])
        self.log.save_to_logs_dir(summary.get("logs_dir", ""))
        self._save_settings()

    def _load_saved_settings(self) -> None:
        settings = load_gui_settings()
        for key, variable in self._string_settings_variables().items():
            value = settings.get(key)
            if isinstance(value, str):
                variable.set(value)
        self.input_kind.set("word")
        self.add_input_kind.set("word")
        if not self.spectra_source.get() and isinstance(settings.get("spectra_zip"), str):
            self.spectra_source.set(str(settings["spectra_zip"]))
        if not self.patch_source_output_dir.get() and self.existing_manifest.get():
            manifest_path = Path(self.existing_manifest.get()).expanduser()
            candidate = manifest_path.parent.parent if manifest_path.parent.name.lower() == "docx" else manifest_path.parent
            if candidate.exists() and _previous_output_defaults(candidate)[0] is not None:
                self.patch_source_output_dir.set(str(candidate))
        if isinstance(settings.get("output_folder"), str) and self.output_folder.get():
            self._sync_output_docx_from_folder()
        elif isinstance(settings.get("output_docx"), str) and self.output_docx.get():
            self._sync_output_folder_from_docx()
        else:
            self._sync_output_docx_from_folder()
        saved_shared_threshold = settings.get("peak_threshold_percent")
        if isinstance(saved_shared_threshold, str):
            if not isinstance(settings.get("peak_threshold_1h_percent"), str):
                self.peak_threshold_1h_percent.set(saved_shared_threshold)
            if not isinstance(settings.get("peak_threshold_13c_percent"), str):
                self.peak_threshold_13c_percent.set(saved_shared_threshold)
        for key, variable in self._bool_settings_variables().items():
            value = settings.get(key)
            if isinstance(value, bool):
                variable.set(value)

    def _set_default_mngp_profiles_if_empty(self) -> None:
        if not self.mnova_graphics_profile_1h.get().strip():
            self.mnova_graphics_profile_1h.set(_default_mngp_profile_text("1H"))
        if not self.mnova_graphics_profile_13c.get().strip():
            self.mnova_graphics_profile_13c.set(_default_mngp_profile_text("13C"))

    def _save_settings(self) -> None:
        self._sync_output_docx_from_folder()
        values: dict[str, str | bool] = {}
        for key, variable in self._string_settings_variables().items():
            values[key] = variable.get()
        for key, variable in self._bool_settings_variables().items():
            values[key] = bool(variable.get())
        try:
            save_gui_settings(values)
        except OSError:
            return

    def _string_settings_variables(self) -> dict[str, StringVar]:
        return {
            "input_path": self.input_path,
            "spectra_source": self.spectra_source,
            "spectra_zip": self.spectra_source,
            "template_docx": self.template_docx,
            "loadings_schema_docx": self.loadings_schema_docx,
            "loadings_scope_docx": self.loadings_scope_docx,
            "mnova_exe": self.mnova_exe,
            "mnova_graphics_profile_1h": self.mnova_graphics_profile_1h,
            "mnova_graphics_profile_13c": self.mnova_graphics_profile_13c,
            "output_docx": self.output_docx,
            "output_folder": self.output_folder,
            "theme_mode": self.theme_mode,
            "peak_threshold_1h_percent": self.peak_threshold_1h_percent,
            "peak_threshold_13c_percent": self.peak_threshold_13c_percent,
            "target_signal_height_percent": self.target_signal_height_percent,
            "h1_ppm_min": self.h1_ppm_min,
            "h1_ppm_max": self.h1_ppm_max,
            "c13_ppm_min": self.c13_ppm_min,
            "c13_ppm_max": self.c13_ppm_max,
            "baseline_mode": self.baseline_mode,
            "baseline_poly_order": self.baseline_poly_order,
            "whittaker_lambda": self.whittaker_lambda,
            "whittaker_asymmetry": self.whittaker_asymmetry,
            "input_kind": self.input_kind,
            "insert_spectra_as": self.insert_spectra_as,
            "existing_manifest": self.existing_manifest,
            "check_support_docx": self.check_support_docx,
            "patch_source_output_dir": self.patch_source_output_dir,
            "patch_operation": self.patch_operation,
            "patch_instruction": self.patch_instruction,
            "add_previous_output_dir": self.add_previous_output_dir,
            "add_manifest": self.add_manifest,
            "add_support_docx": self.add_support_docx,
            "add_template_docx": self.add_template_docx,
            "add_loadings_schema_docx": self.add_loadings_schema_docx,
            "add_loadings_scope_docx": self.add_loadings_scope_docx,
            "add_input_path": self.add_input_path,
            "add_spectra_source": self.add_spectra_source,
            "add_output_docx": self.add_output_docx,
            "add_output_folder": self.add_output_folder,
            "add_input_kind": self.add_input_kind,
            "add_method_mode": self.add_method_mode,
        }

    def _set_output_folder(self, folder: str, *, save: bool = True) -> None:
        self.output_folder.set(folder)
        self._sync_output_docx_from_folder()
        if save:
            self._save_settings()

    def _sync_output_docx_from_folder(self) -> None:
        output_docx = _output_docx_from_folder(self.output_folder.get(), self.output_docx.get())
        if output_docx:
            self.output_docx.set(output_docx)

    def _sync_output_folder_from_docx(self) -> None:
        raw_docx = self.output_docx.get().strip().strip('"')
        if raw_docx:
            self.output_folder.set(str(Path(raw_docx).expanduser().parent))

    def _bool_settings_variables(self) -> dict[str, BooleanVar]:
        return {
            "check_support": self.check_support,
            "generate_loadings": self.generate_loadings,
            "calculate_elemental_analysis": self.calculate_elemental_analysis,
            "baseline_apply_1h": self.baseline_apply_1h,
            "baseline_apply_13c": self.baseline_apply_13c,
            "highlight_solvent_peaks": self.highlight_solvent_peaks,
        }

    def _on_close(self) -> None:
        self._save_settings()
        if self._poll_after_id is not None:
            try:
                self.root.after_cancel(self._poll_after_id)
            except tk.TclError:
                pass
            self._poll_after_id = None
        self.root.destroy()


def _rounded_rectangle(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs) -> int:
    radius = max(1, min(radius, int((x2 - x1) / 2), int((y2 - y1) / 2)))
    points = (
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    )
    return canvas.create_polygon(points, smooth=True, **kwargs)


class _PillButton(tk.Canvas):
    def __init__(
        self,
        parent,
        *,
        text: str,
        command,
        theme: dict[str, str],
        subtle: bool = False,
        height: int = 38,
    ) -> None:
        super().__init__(
            parent,
            width=224,
            height=height,
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
            background=theme["sidebar_bg"],
        )
        self.text = text
        self.command = command
        self.theme = theme
        self.subtle = subtle
        self._height = height
        self._hovered = False
        self._selected = False
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self._draw()

    def set_theme(self, theme: dict[str, str]) -> None:
        self.theme = theme
        self.configure(background=theme["sidebar_bg"])
        self._draw()

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._draw()

    def _on_enter(self, _event=None) -> None:
        self._hovered = True
        self._draw()

    def _on_leave(self, _event=None) -> None:
        self._hovered = False
        self._draw()

    def _on_click(self, _event=None) -> None:
        self.command()

    def _draw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), int(self.cget("width")))
        height = max(self.winfo_height(), self._height)
        theme = self.theme
        if self._selected:
            fill = theme["sidebar_selected"]
            outline = ""
        elif self._hovered:
            fill = theme["sidebar_hover"]
            outline = ""
        elif self.subtle:
            fill = theme["sidebar_hover"]
            outline = ""
        else:
            fill = theme["sidebar_bg"]
            outline = theme["sidebar_hover"]
        _rounded_rectangle(self, 2, 2, width - 2, height - 2, int((height - 4) / 2), fill=fill, outline=outline)
        anchor = "center" if self.subtle else "w"
        x = int(width / 2) if self.subtle else 18
        font_weight = "bold" if self._selected else "normal"
        self.create_text(
            x,
            int(height / 2),
            text=self.text,
            anchor=anchor,
            fill=theme["text"],
            font=("Segoe UI", 10, font_weight),
        )


class _ThemeSwitch(tk.Canvas):
    def __init__(self, parent, *, mode: str, command, theme: dict[str, str]) -> None:
        super().__init__(
            parent,
            width=96,
            height=36,
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
            background=theme["sidebar_bg"],
        )
        self.mode = mode if mode in THEME_PALETTES else "light"
        self.command = command
        self.theme = theme
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Button-1>", self._on_click)
        self._draw()

    def set_theme(self, theme: dict[str, str]) -> None:
        self.theme = theme
        self.configure(background=theme["sidebar_bg"])
        self._draw()

    def set_mode(self, mode: str) -> None:
        self.mode = mode if mode in THEME_PALETTES else "light"
        self._draw()

    def _on_click(self, event) -> None:
        width = max(self.winfo_width(), int(self.cget("width")))
        self.command("light" if event.x < width / 2 else "dark")

    def _draw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), int(self.cget("width")))
        height = max(self.winfo_height(), int(self.cget("height")))
        theme = self.theme
        _rounded_rectangle(self, 2, 2, width - 2, height - 2, int((height - 4) / 2), fill=theme["sidebar_hover"], outline="")
        half = int(width / 2)
        if self.mode == "dark":
            x1, x2 = half, width - 3
        else:
            x1, x2 = 3, half
        _rounded_rectangle(self, x1, 3, x2, height - 3, int((height - 6) / 2), fill=theme["accent"], outline="")
        light_color = "#ffffff" if self.mode == "light" else theme["muted"]
        dark_color = "#ffffff" if self.mode == "dark" else theme["muted"]
        self.create_text(int(width * 0.25), int(height / 2), text="☀", fill=light_color, font=("Segoe UI Symbol", 13, "bold"))
        self.create_text(int(width * 0.75), int(height / 2), text="☾", fill=dark_color, font=("Segoe UI Symbol", 14, "bold"))


class _CollapsibleInstructionBlock(ttk.Frame):
    def __init__(
        self,
        parent,
        *,
        title: str,
        summary: str,
        theme: dict[str, str],
        expanded: bool = False,
    ) -> None:
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.title = title
        self.summary = summary
        self.theme = theme
        self.expanded = expanded
        self.header = tk.Canvas(self, height=44, highlightthickness=0, borderwidth=0, cursor="hand2", background=theme["app_bg"])
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.bind("<Configure>", lambda _event: self._draw_header())
        self.header.bind("<Button-1>", lambda _event: self.toggle())
        self.body = ttk.Frame(self, style="Card.TFrame", padding=(14, 8, 14, 12))
        self.body.columnconfigure(0, weight=1)
        if self.expanded:
            self.body.grid(row=1, column=0, sticky="ew")
        self._draw_header()

    def set_theme(self, theme: dict[str, str]) -> None:
        self.theme = theme
        self.header.configure(background=theme["app_bg"])
        self._draw_header()

    def toggle(self) -> None:
        self.expanded = not self.expanded
        if self.expanded:
            self.body.grid(row=1, column=0, sticky="ew")
        else:
            self.body.grid_remove()
        self._draw_header()

    def _draw_header(self) -> None:
        self.header.delete("all")
        width = max(self.header.winfo_width(), 360)
        height = max(self.header.winfo_height(), 44)
        theme = self.theme
        fill = theme["card_bg"]
        outline = theme["border"]
        _rounded_rectangle(self.header, 2, 2, width - 2, height - 2, int((height - 4) / 2), fill=fill, outline=outline)
        marker = "▾" if self.expanded else "▸"
        self.header.create_text(18, int(height / 2), text=marker, anchor="w", fill=theme["accent"], font=("Segoe UI Symbol", 13, "bold"))
        self.header.create_text(42, int(height / 2), text=self.title, anchor="w", fill=theme["text"], font=("Segoe UI", 11, "bold"))
        self.header.create_text(width - 18, int(height / 2), text=self.summary, anchor="e", fill=theme["muted"], font=("Segoe UI", 9))


class _ScrollableFrame(ttk.Frame):
    def __init__(self, parent, *, padding: int = 0) -> None:
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.content = ttk.Frame(self.canvas, padding=padding)
        self._window_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._sync_content_width)
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)
        self.content.bind("<Enter>", self._bind_mousewheel)
        self.content.bind("<Leave>", self._unbind_mousewheel)

    def _sync_scroll_region(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_content_width(self, event) -> None:
        self.canvas.itemconfigure(self._window_id, width=event.width)

    def _bind_mousewheel(self, _event=None) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event=None) -> None:
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event) -> None:
        self.canvas.yview_scroll(_mousewheel_units(event.delta), "units")


def _mousewheel_units(delta: int) -> int:
    if delta == 0:
        return 0
    return -1 * int(delta / abs(delta))


class _LogText(ttk.Frame):
    def __init__(self, parent, *, height: int = 16) -> None:
        super().__init__(parent)
        import tkinter as tk

        self.text = tk.Text(self, wrap="word", height=height, borderwidth=0, font=("Consolas", 10))
        self.text.pack(fill="both", expand=True)

    def grid(self, *args, **kwargs):
        super().grid(*args, **kwargs)

    def configure(self, *args, **kwargs):
        self.text.configure(*args, **kwargs)

    def yview(self, *args):
        return self.text.yview(*args)

    def write(self, text: str) -> None:
        self.text.insert("end", text)
        self.text.see("end")

    def clear(self) -> None:
        self.text.delete("1.0", "end")


class _RunLogBuffer:
    def __init__(self) -> None:
        self._parts: list[str] = []

    def configure(self, *args, **kwargs) -> None:
        return None

    def write(self, text: str) -> None:
        self._parts.append(str(text))

    def clear(self) -> None:
        self._parts.clear()

    def save_to_logs_dir(self, logs_dir: str) -> None:
        if not logs_dir:
            return
        try:
            path = Path(logs_dir).expanduser()
            path.mkdir(parents=True, exist_ok=True)
            (path / "gui_run.log").write_text("".join(self._parts), encoding="utf-8")
        except OSError:
            return


class _QueueWriter:
    def __init__(self, log_queue: queue.Queue[str]) -> None:
        self.log_queue = log_queue

    def write(self, text: str) -> int:
        if text:
            self.log_queue.put(text)
        return len(text)

    def flush(self) -> None:
        return None


def _build_generate_request(
    *,
    input_kind: str,
    input_path_text: str,
    output_docx_text: str,
    spectra_source_text: str = "",
    spectra_zip_text: str = "",
    template_docx_text: str = "",
    references_text: str = "",
    loadings_schema_text: str = "",
    loadings_scope_text: str = "",
    mnova_exe_text: str = "",
    mnova_graphics_profile_text: str = "",
    mnova_graphics_profile_1h_text: str = "",
    mnova_graphics_profile_13c_text: str = "",
    insert_spectra_as: str = "png",
    peak_threshold_percent_text: str = "",
    peak_threshold_1h_percent_text: str = "",
    peak_threshold_13c_percent_text: str = "",
    target_signal_height_percent_text: str = f"{DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION * 100:g}",
    h1_ppm_min_text: str = f"{DEFAULT_X_RANGES['1H'][0]:g}",
    h1_ppm_max_text: str = f"{DEFAULT_X_RANGES['1H'][1]:g}",
    c13_ppm_min_text: str = f"{DEFAULT_X_RANGES['13C'][0]:g}",
    c13_ppm_max_text: str = f"{DEFAULT_X_RANGES['13C'][1]:g}",
    baseline_mode_text: str = DEFAULT_BASELINE_MODE,
    baseline_apply_1h: bool = DEFAULT_BASELINE_APPLY_1H,
    baseline_apply_13c: bool = DEFAULT_BASELINE_APPLY_13C,
    baseline_poly_order_text: str = str(DEFAULT_BASELINE_POLY_ORDER),
    whittaker_lambda_text: str = f"{DEFAULT_WHITTAKER_LAMBDA:g}",
    whittaker_asymmetry_text: str = f"{DEFAULT_WHITTAKER_ASYMMETRY:g}",
    highlight_solvent_peaks: bool = False,
    generate_loadings: bool = False,
    calculate_elemental_analysis: bool = False,
    check_support: bool = True,
) -> GenerateSIRequest:
    input_path = _required_existing_file(input_path_text, "Choose an existing compound table.", suffixes=(".docx",))
    output_docx = Path(output_docx_text.strip().strip('"')).expanduser()
    if not output_docx.name.lower().endswith(".docx"):
        raise ValueError("Output file must be a .docx file.")
    shared_peak_threshold = _optional_peak_threshold_fraction(peak_threshold_percent_text)
    loadings_schema = loadings_scope = None
    if generate_loadings:
        loadings_schema = _optional_existing_file(loadings_schema_text, "Reaction schema .docx", suffixes=(".docx",))
        loadings_scope = _optional_existing_file(loadings_scope_text, "Scope .docx", suffixes=(".docx",))
        if any((loadings_schema, loadings_scope)) and not all((loadings_schema, loadings_scope)):
            raise ValueError("Choose both reagent loadings files or leave both empty for auto-detect.")

    return GenerateSIRequest(
        input_path=input_path,
        input_kind="word",
        output_path=output_docx,
        spectra_source=_optional_spectra_source(spectra_source_text or spectra_zip_text),
        template_docx=_optional_existing_file(template_docx_text, "SI template .docx", suffixes=(".docx",)),
        references_path=_optional_existing_file(references_text, "References .yml", suffixes=(".yml", ".yaml")),
        loadings_schema_docx=loadings_schema,
        loadings_scope_docx=loadings_scope,
        mnova_exe=_optional_existing_file(mnova_exe_text, "MestReNova .exe", suffixes=(".exe",)),
        mnova_graphics_profile=_optional_existing_file(
            mnova_graphics_profile_text,
            "Mnova graphics .mngp",
            suffixes=(".mngp",),
        ),
        mnova_graphics_profile_1h=_optional_existing_file(
            mnova_graphics_profile_1h_text,
            "1H .mngp",
            suffixes=(".mngp",),
        ),
        mnova_graphics_profile_13c=_optional_existing_file(
            mnova_graphics_profile_13c_text,
            "13C .mngp",
            suffixes=(".mngp",),
        ),
        insert_spectra_as=_validated_spectrum_mode(insert_spectra_as),
        peak_threshold_fraction=shared_peak_threshold,
        peak_threshold_fraction_1h=_validated_peak_threshold_fraction(
            peak_threshold_1h_percent_text,
            shared_peak_threshold if shared_peak_threshold is not None else DEFAULT_H1_PEAK_THRESHOLD_FRACTION,
        ),
        peak_threshold_fraction_13c=_validated_peak_threshold_fraction(
            peak_threshold_13c_percent_text,
            shared_peak_threshold if shared_peak_threshold is not None else DEFAULT_C13_PEAK_THRESHOLD_FRACTION,
        ),
        target_signal_height_fraction=_validated_target_signal_height_fraction(target_signal_height_percent_text),
        x_range_ppm_1h=_validated_ppm_range(h1_ppm_min_text, h1_ppm_max_text, "1H ppm range"),
        x_range_ppm_13c=_validated_ppm_range(c13_ppm_min_text, c13_ppm_max_text, "13C ppm range"),
        baseline_mode=_validated_baseline_mode(baseline_mode_text),
        baseline_apply_1h=bool(baseline_apply_1h),
        baseline_apply_13c=bool(baseline_apply_13c),
        baseline_poly_order=_validated_positive_int(baseline_poly_order_text, "Baseline polynomial order"),
        whittaker_lambda=_validated_positive_float(whittaker_lambda_text, "Whittaker lambda"),
        whittaker_asymmetry=_validated_fraction(whittaker_asymmetry_text, "Whittaker asymmetry"),
        highlight_solvent_peaks=bool(highlight_solvent_peaks),
        generate_loadings=generate_loadings,
        calculate_elemental_analysis=calculate_elemental_analysis,
        no_check_support=not check_support,
    )


def _build_check_request(manifest_text: str, *, support_docx_text: str = "") -> CheckSIRequest:
    manifest_path = _required_existing_file(manifest_text, "Choose an existing manifest JSON.", suffixes=(".json",))
    return CheckSIRequest(
        manifest_path=manifest_path,
        support_docx=_optional_existing_file(support_docx_text, "Support .docx override", suffixes=(".docx",)),
    )


def _build_add_compounds_request(
    *,
    manifest_text: str,
    support_docx_text: str,
    input_kind: str,
    method_mode_text: str = "same_series",
    input_path_text: str,
    output_folder_text: str = "",
    output_docx_text: str = "",
    spectra_source_text: str = "",
    template_docx_text: str = "",
    references_text: str = "",
    loadings_schema_docx_text: str = "",
    loadings_scope_docx_text: str = "",
    mnova_exe_text: str = "",
    mnova_graphics_profile_text: str = "",
    mnova_graphics_profile_1h_text: str = "",
    mnova_graphics_profile_13c_text: str = "",
    insert_spectra_as: str = "png",
    peak_threshold_percent_text: str = "",
    peak_threshold_1h_percent_text: str = "",
    peak_threshold_13c_percent_text: str = "",
    target_signal_height_percent_text: str = f"{DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION * 100:g}",
    h1_ppm_min_text: str = f"{DEFAULT_X_RANGES['1H'][0]:g}",
    h1_ppm_max_text: str = f"{DEFAULT_X_RANGES['1H'][1]:g}",
    c13_ppm_min_text: str = f"{DEFAULT_X_RANGES['13C'][0]:g}",
    c13_ppm_max_text: str = f"{DEFAULT_X_RANGES['13C'][1]:g}",
    baseline_mode_text: str = DEFAULT_BASELINE_MODE,
    baseline_apply_1h: bool = DEFAULT_BASELINE_APPLY_1H,
    baseline_apply_13c: bool = DEFAULT_BASELINE_APPLY_13C,
    baseline_poly_order_text: str = str(DEFAULT_BASELINE_POLY_ORDER),
    whittaker_lambda_text: str = f"{DEFAULT_WHITTAKER_LAMBDA:g}",
    whittaker_asymmetry_text: str = f"{DEFAULT_WHITTAKER_ASYMMETRY:g}",
    highlight_solvent_peaks: bool = False,
    generate_loadings: bool = False,
    calculate_elemental_analysis: bool = False,
    check_support: bool = True,
    previous_output_dir_text: str = "",
) -> AddCompoundsRequest:
    input_path = _required_existing_file(input_path_text, "Choose an existing new compound table.", suffixes=(".docx",))
    output_docx = _optional_output_docx(output_docx_text)
    output_folder = _optional_output_folder(output_folder_text)
    if not output_docx and not output_folder:
        output_folder = input_path.parent
    previous_output_dir = _optional_existing_folder(previous_output_dir_text, "Previous output folder")
    if previous_output_dir:
        default_manifest, default_support = _previous_output_defaults(previous_output_dir)
        manifest_text = manifest_text or (str(default_manifest) if default_manifest else "")
        support_docx_text = support_docx_text or (str(default_support) if default_support else "")
    shared_peak_threshold = _optional_peak_threshold_fraction(peak_threshold_percent_text)
    add_loadings_requested = generate_loadings or bool(loadings_schema_docx_text.strip() or loadings_scope_docx_text.strip())
    return AddCompoundsRequest(
        manifest_path=_required_existing_file(manifest_text, "Choose an existing manifest JSON.", suffixes=(".json",)),
        support_docx=_optional_existing_file(support_docx_text, "Existing support .docx", suffixes=(".docx",)),
        previous_output_dir=previous_output_dir,
        input_path=input_path,
        input_kind="word",
        output_docx=output_docx,
        output_folder=output_folder,
        method_mode=_validated_add_method_mode(method_mode_text),
        spectra_source=_optional_spectra_source(spectra_source_text),
        template_docx=_optional_existing_file(template_docx_text, "SI template .docx", suffixes=(".docx",)),
        references_path=_optional_existing_file(references_text, "References .yml", suffixes=(".yml", ".yaml")),
        loadings_schema_docx=_optional_existing_file(
            loadings_schema_docx_text,
            "Reaction schema .docx",
            suffixes=(".docx",),
        ),
        loadings_scope_docx=_optional_existing_file(
            loadings_scope_docx_text,
            "Scope table .docx",
            suffixes=(".docx",),
        ),
        mnova_exe=_optional_existing_file(mnova_exe_text, "MestReNova .exe", suffixes=(".exe",)),
        mnova_graphics_profile=_optional_existing_file(
            mnova_graphics_profile_text,
            "Mnova graphics .mngp",
            suffixes=(".mngp",),
        ),
        mnova_graphics_profile_1h=_optional_existing_file(
            mnova_graphics_profile_1h_text,
            "1H .mngp",
            suffixes=(".mngp",),
        ),
        mnova_graphics_profile_13c=_optional_existing_file(
            mnova_graphics_profile_13c_text,
            "13C .mngp",
            suffixes=(".mngp",),
        ),
        insert_spectra_as=_validated_spectrum_mode(insert_spectra_as),
        peak_threshold_fraction=shared_peak_threshold,
        peak_threshold_fraction_1h=_validated_peak_threshold_fraction(
            peak_threshold_1h_percent_text,
            shared_peak_threshold if shared_peak_threshold is not None else DEFAULT_H1_PEAK_THRESHOLD_FRACTION,
        ),
        peak_threshold_fraction_13c=_validated_peak_threshold_fraction(
            peak_threshold_13c_percent_text,
            shared_peak_threshold if shared_peak_threshold is not None else DEFAULT_C13_PEAK_THRESHOLD_FRACTION,
        ),
        target_signal_height_fraction=_validated_target_signal_height_fraction(target_signal_height_percent_text),
        x_range_ppm_1h=_validated_ppm_range(h1_ppm_min_text, h1_ppm_max_text, "1H ppm range"),
        x_range_ppm_13c=_validated_ppm_range(c13_ppm_min_text, c13_ppm_max_text, "13C ppm range"),
        baseline_mode=_validated_baseline_mode(baseline_mode_text),
        baseline_apply_1h=bool(baseline_apply_1h),
        baseline_apply_13c=bool(baseline_apply_13c),
        baseline_poly_order=_validated_positive_int(baseline_poly_order_text, "Baseline polynomial order"),
        whittaker_lambda=_validated_positive_float(whittaker_lambda_text, "Whittaker lambda"),
        whittaker_asymmetry=_validated_fraction(whittaker_asymmetry_text, "Whittaker asymmetry"),
        highlight_solvent_peaks=bool(highlight_solvent_peaks),
        generate_loadings=add_loadings_requested,
        calculate_elemental_analysis=calculate_elemental_analysis,
        no_check_support=not check_support,
    )


def _build_patch_request(
    *,
    source_output_folder_text: str,
    operation_text: str,
    instruction_text: str,
    support_docx_text: str = "",
) -> PatchSIRequest:
    source_output_folder = _required_existing_folder(
        source_output_folder_text,
        "Choose an existing generated output folder.",
    )
    support_override = _optional_existing_file(
        support_docx_text,
        "Existing support .docx",
        suffixes=(".docx",),
    )
    manifest_path, discovered_support = _validate_patch_source_output_folder(
        source_output_folder,
        require_support=support_override is None,
    )
    operation = operation_text.strip().lower()
    if operation not in {"renumber", "remove", "reorder", "swap"}:
        raise ValueError("Choose one patch operation: renumber, remove, reorder, or swap.")
    if not instruction_text.strip():
        raise ValueError(f"Enter instructions for the {operation} operation.")
    renumber = parse_renumber_map(instruction_text) if operation == "renumber" else {}
    remove = parse_remove_list(instruction_text) if operation == "remove" else ()
    reorder = parse_reorder_list(instruction_text) if operation == "reorder" else ()
    swap = parse_swap_pairs(instruction_text) if operation == "swap" else ()
    return PatchSIRequest(
        manifest_path=manifest_path,
        support_docx=support_override or discovered_support,
        renumber=renumber,
        remove=remove,
        reorder=reorder,
        swap=swap,
    )


def _build_patch_summary(state: dict[str, Any]) -> dict[str, str]:
    artifacts = state.get("artifacts", {})
    report_path = _resolved_artifact(artifacts, "patch_report")
    summary = {
        "support_docx": _resolved_artifact(artifacts, "support_docx"),
        "manifest": _resolved_artifact(artifacts, "manifest"),
        "run_summary": report_path,
        "logs_dir": _resolved_artifact(artifacts, "logs_dir"),
        "output_folder": _resolved_artifact(artifacts, "output_root"),
        "overview": _report_overview(report_path),
    }
    if not summary["output_folder"]:
        summary["output_folder"] = _summary_output_folder(summary)
    return {key: value for key, value in summary.items() if value}


def _build_add_compounds_summary(state: dict[str, Any]) -> dict[str, str]:
    artifacts = state.get("artifacts", {})
    report_path = _resolved_artifact(artifacts, "add_report")
    summary = {
        "support_docx": _resolved_artifact(artifacts, "support_docx"),
        "manifest": _resolved_artifact(artifacts, "manifest"),
        "run_summary": report_path,
        "logs_dir": _resolved_artifact(artifacts, "logs_dir"),
        "output_folder": _resolved_artifact(artifacts, "output_root"),
        "overview": _report_overview(report_path),
    }
    if not summary["output_folder"]:
        summary["output_folder"] = _summary_output_folder(summary)
    return {key: value for key, value in summary.items() if value}


def _build_check_summary(state: dict[str, Any], request: CheckSIRequest) -> dict[str, str]:
    artifacts = state.get("artifacts", {})
    report_path = _resolved_artifact(artifacts, "check_report")
    summary = {
        "manifest": str(Path(artifacts.get("manifest", request.manifest_path)).resolve()),
        "run_summary": report_path,
        "logs_dir": _resolved_artifact(artifacts, "logs_dir"),
        "output_folder": _resolved_artifact(artifacts, "output_root"),
        "overview": _report_overview(report_path),
    }
    if not summary["output_folder"]:
        summary["output_folder"] = _summary_output_folder(summary)
    return {key: value for key, value in summary.items() if value}


def _build_result_summary(state: dict[str, Any]) -> dict[str, str]:
    artifacts = state.get("artifacts", {})
    output_path = output_path_from_state(state)
    report_path = _resolved_artifact(artifacts, "run_summary")
    summary = {
        "support_docx": str(Path(artifacts.get("support_docx", output_path)).resolve()),
        "processed_spectra_zip": _resolved_artifact(artifacts, "processed_spectra_zip"),
        "processed_mnova_dir": _resolved_artifact(artifacts, "processed_mnova_dir"),
        "mnova_reports_dir": _resolved_artifact(artifacts, "mnova_reports_dir"),
        "logs_dir": _resolved_artifact(artifacts, "logs_dir"),
        "manifest": _resolved_artifact(artifacts, "manifest"),
        "run_summary": report_path,
        "output_folder": _resolved_artifact(artifacts, "output_root"),
        "input_warnings": _resolved_artifact(artifacts, "input_warnings"),
        "support_warnings": _resolved_artifact(artifacts, "support_warnings"),
        "overview": _report_overview(report_path),
    }
    if not summary["output_folder"]:
        summary["output_folder"] = _summary_output_folder(summary)
    return {key: value for key, value in summary.items() if value}


def _resolved_artifact(artifacts: dict[str, str], key: str) -> str:
    value = artifacts.get(key, "")
    return str(Path(value).resolve()) if value else ""


def _summary_output_folder(summary: dict[str, str]) -> str:
    for key in ("output_folder", "support_docx", "run_summary", "logs_dir"):
        value = summary.get(key)
        if not value:
            continue
        path = Path(value).expanduser()
        folder = path if path.is_dir() else path.parent
        if folder.name.lower() == "docx":
            folder = folder.parent
        return str(folder.resolve())
    return ""


def _report_overview(report_path: str) -> str:
    if not report_path:
        return ""
    path = Path(report_path)
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""

    parts: list[str] = []
    status = str(data.get("status") or "").replace("_", " ")
    if status:
        parts.append(f"Status: {status}")
    compound_count = data.get("compound_count")
    if compound_count is not None:
        parts.append(f"Compounds: {compound_count}")
    issue_counts = data.get("issue_counts", {}) or {}
    total_issues = 0
    for severity, label in [("error", "Errors"), ("warning", "Warnings"), ("info", "Info")]:
        try:
            count = int(issue_counts.get(severity, 0) or 0)
        except (TypeError, ValueError):
            count = 0
        total_issues += count
        if count:
            parts.append(f"{label}: {count}")
    issue_code_counts = data.get("issue_code_counts", {}) or {}
    top_issue_codes = _top_issue_codes(issue_code_counts)
    if top_issue_codes:
        parts.append("Top issues: " + top_issue_codes)
    if status and not total_issues:
        parts.append("Issues: 0")
    return " | ".join(parts)


def _top_issue_codes(issue_code_counts: dict[str, Any], limit: int = 3) -> str:
    items: list[tuple[str, int]] = []
    for code, raw_count in issue_code_counts.items():
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            continue
        if code and count > 0:
            items.append((str(code), count))
    items.sort(key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{code} x{count}" for code, count in items[:limit])


def _existing_result_path(raw_path: str, label: str) -> Path:
    raw_path = raw_path.strip().strip('"')
    if not raw_path:
        raise ValueError(f"{label} has not been generated yet.")
    path = Path(raw_path).expanduser()
    if not path.exists():
        raise ValueError(f"{label} does not exist: {path}")
    return path.resolve()


def _has_preflight_code(issues: list[dict[str, Any]], code: str) -> bool:
    return any(issue.get("code") == code for issue in issues)


def _failure_dialog_message(item: dict[str, Any]) -> str:
    title = str(item.get("error") or "Operation failed")
    issues = [issue for issue in item.get("issues", []) if isinstance(issue, dict)]
    errors = [issue for issue in issues if issue.get("severity") == "error"]
    selected_issues = errors or issues
    if not selected_issues:
        return title

    lines = [title, "", "Details:"]
    for issue in selected_issues[:6]:
        lines.extend(_issue_dialog_lines(issue))
    if len(selected_issues) > 6:
        lines.append(f"- ... and {len(selected_issues) - 6} more issue(s).")
    summary = item.get("summary")
    if isinstance(summary, dict) and summary.get("run_summary"):
        lines.extend(["", f"Report: {summary['run_summary']}"])
    return "\n".join(lines)


def _issue_dialog_lines(issue: dict[str, Any]) -> list[str]:
    code = str(issue.get("code") or "ERROR")
    message = str(issue.get("message") or "").strip()
    path = str(issue.get("path") or "").strip()
    lines = [f"- {code}: {message}" if message else f"- {code}"]
    if path:
        lines.append(f"  File: {path}")
    return lines


def _next_available_docx_path(path: Path) -> Path:
    path = path.resolve()
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError(f"Cannot find a free output file name near: {path}")


def _dialog_initialdir(*candidates: str | Path | None) -> str | None:
    for candidate in candidates:
        if not candidate:
            continue
        raw_path = str(candidate).strip().strip('"')
        if not raw_path:
            continue
        path = Path(raw_path).expanduser()
        if path.exists():
            directory = path if path.is_dir() else path.parent
            return str(directory.resolve())
        parent = path.parent
        if str(parent) not in {"", "."} and parent.exists():
            return str(parent.resolve())
    return None


def _output_docx_from_folder(output_folder_text: str, fallback_docx_text: str = "") -> str:
    raw_folder = output_folder_text.strip().strip('"')
    if raw_folder:
        return str(Path(raw_folder).expanduser() / "support_information.docx")
    return fallback_docx_text.strip().strip('"')


def _default_mngp_profile_text(nucleus: str) -> str:
    filename = "classic_13C.mngp" if nucleus == "13C" else "classic_1H.mngp"
    path = bundled_resource_path(Path("mngp_styles") / filename)
    return str(path) if path.exists() else ""


def _example_field_updates(table: Path, spectra_zip: Path, output_docx: Path) -> dict[str, str]:
    example = table.parent
    classic_1h = Path(_default_mngp_profile_text("1H"))
    classic_13c = Path(_default_mngp_profile_text("13C"))
    return {
        "input_kind": "word",
        "input_path": str(table),
        "spectra_source": str(spectra_zip),
        "spectra_zip": str(spectra_zip),
        "output_docx": str(output_docx),
        "output_folder": str(output_docx.parent),
        "template_docx": str(example / "SI_template.docx") if (example / "SI_template.docx").exists() else "",
        "loadings_schema_docx": str(example / "Reaction_schema.docx") if (example / "Reaction_schema.docx").exists() else "",
        "loadings_scope_docx": str(example / "Scope.docx") if (example / "Scope.docx").exists() else "",
        "mnova_graphics_profile": "",
        "mnova_graphics_profile_1h": str(classic_1h) if classic_1h.exists() else "",
        "mnova_graphics_profile_13c": str(classic_13c) if classic_13c.exists() else "",
        "h1_ppm_min": f"{DEFAULT_X_RANGES['1H'][0]:g}",
        "h1_ppm_max": f"{DEFAULT_X_RANGES['1H'][1]:g}",
        "c13_ppm_min": f"{DEFAULT_X_RANGES['13C'][0]:g}",
        "c13_ppm_max": f"{DEFAULT_X_RANGES['13C'][1]:g}",
        "existing_manifest": "",
        "check_support_docx": "",
        "patch_source_output_dir": "",
        "patch_operation": "renumber",
        "patch_instruction": "",
        "add_previous_output_dir": "",
        "add_manifest": "",
        "add_support_docx": "",
        "add_template_docx": "",
        "add_loadings_schema_docx": "",
        "add_loadings_scope_docx": "",
        "add_input_path": "",
        "add_spectra_source": "",
        "add_output_docx": "",
        "add_output_folder": str(output_docx.parent),
        "add_method_mode": "same_series",
    }


def _required_existing_file(raw_path: str, message: str, *, suffixes: tuple[str, ...] = ()) -> Path:
    path = Path(raw_path.strip().strip('"')).expanduser()
    if not path.exists():
        raise ValueError(message)
    _validate_existing_file(path, suffixes=suffixes)
    return path


def _optional_existing_file(raw_path: str, label: str, *, suffixes: tuple[str, ...] = ()) -> Path | None:
    raw_path = raw_path.strip().strip('"')
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if not path.exists():
        raise ValueError(f"{label} does not exist: {path}")
    _validate_existing_file(path, label=label, suffixes=suffixes)
    return path


def _optional_existing_folder(raw_path: str, label: str) -> Path | None:
    raw_path = str(raw_path).strip().strip('"')
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if not path.exists():
        raise ValueError(f"{label} does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"{label} must be a folder: {path}")
    return path


def _required_existing_folder(raw_path: str, message: str) -> Path:
    path = _optional_existing_folder(raw_path, "Selected output folder")
    if path is None:
        raise ValueError(message)
    return path


def _previous_output_defaults(output_dir: Path) -> tuple[Path | None, Path | None]:
    root = Path(output_dir).expanduser()
    candidates = [
        root / "docx" / "support_information.manifest.json",
        root / "support_information.manifest.json",
    ]
    manifest = next((path for path in candidates if path.exists() and path.is_file()), None)
    support_candidates = [
        root / "docx" / "support_information.docx",
        root / "support_information.docx",
    ]
    support = next((path for path in support_candidates if path.exists() and path.is_file()), None)
    return manifest, support


def _validate_patch_source_output_folder(output_dir: Path, *, require_support: bool = True) -> tuple[Path, Path | None]:
    manifest, support = _previous_output_defaults(output_dir)
    missing: list[str] = []
    if manifest is None:
        missing.append("docx/support_information.manifest.json")
    if support is None and require_support:
        missing.append("docx/support_information.docx")
    if missing:
        raise ValueError(
            "The selected folder is not a generated Auto Support output. Missing: " + ", ".join(missing)
        )
    assert manifest is not None
    return manifest, support


def _optional_spectra_source(raw_path: str) -> Path | None:
    raw_path = str(raw_path).strip().strip('"')
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if not path.exists():
        raise ValueError(f"Spectra source does not exist: {path}")
    if path.is_dir():
        return path
    _validate_existing_file(path, label="Spectra source", suffixes=(".zip",))
    return path


def _validate_existing_file(path: Path, *, label: str = "Selected path", suffixes: tuple[str, ...] = ()) -> None:
    if not path.is_file():
        raise ValueError(f"{label} must be a file: {path}")
    if suffixes and path.suffix.lower() not in suffixes:
        expected = ", ".join(suffixes)
        raise ValueError(f"{label} must have one of these extensions: {expected}. Got: {path}")


def _optional_output_docx(raw_path: str) -> Path | None:
    raw_path = raw_path.strip().strip('"')
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if path.suffix.lower() != ".docx":
        raise ValueError("Output file must be a .docx file.")
    return path


def _optional_output_folder(raw_path: str) -> Path | None:
    raw_path = raw_path.strip().strip('"')
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if path.suffix:
        raise ValueError("Output folder must be a folder path, not a file.")
    return path


def _validated_spectrum_mode(value: str) -> SpectrumEmbedMode:
    value = value.strip().lower()
    if value in {"png", "mnova", "none"}:
        return value
    return "png"


def _validated_add_method_mode(value: str) -> str:
    normalized = str(value or "same_series").strip().lower().replace("-", "_")
    if normalized in {"same_series", "new_method"}:
        return normalized
    return "same_series"


def _validated_baseline_mode(value: str) -> str:
    mode = str(value or DEFAULT_BASELINE_MODE).strip().lower()
    if mode in {"auto", "off", "bernstein", "whittaker"}:
        return mode
    return DEFAULT_BASELINE_MODE


def _optional_peak_threshold_fraction(raw_value: str) -> float | None:
    raw_value = str(raw_value).strip()
    if not raw_value:
        return None
    return _validated_peak_threshold_fraction(raw_value, DEFAULT_H1_PEAK_THRESHOLD_FRACTION)


def _validated_peak_threshold_fraction(raw_value: str, default: float = DEFAULT_H1_PEAK_THRESHOLD_FRACTION) -> float:
    raw_value = str(raw_value).strip().replace(",", ".")
    if not raw_value:
        return default
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError("Peak threshold must be a number, for example 6 or 0.06.") from exc
    fraction = value / 100 if value > 1 else value
    if fraction < 0 or fraction > 1:
        raise ValueError("Peak threshold must be between 0 and 100%.")
    return fraction


def _validated_target_signal_height_fraction(raw_value: str) -> float:
    raw_value = str(raw_value).strip().replace(",", ".")
    if not raw_value:
        return DEFAULT_TARGET_SIGNAL_HEIGHT_FRACTION
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError("Signal height must be a number, for example 80 or 0.8.") from exc
    fraction = value / 100 if value > 1 else value
    if fraction < 0.20 or fraction > 0.95:
        raise ValueError("Signal height must be between 20 and 95%.")
    return fraction


def _validated_ppm_range(min_value: str, max_value: str, label: str) -> tuple[float, float]:
    try:
        first = float(str(min_value).strip().replace(",", "."))
        second = float(str(max_value).strip().replace(",", "."))
    except ValueError as exc:
        raise ValueError(f"{label} must contain two numeric ppm values.") from exc
    if first == second:
        raise ValueError(f"{label} min and max values must be different.")
    return (min(first, second), max(first, second))


def _validated_positive_int(raw_value: str, label: str) -> int:
    raw_value = str(raw_value).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a positive integer.") from exc
    if value <= 0:
        raise ValueError(f"{label} must be a positive integer.")
    return value


def _validated_positive_float(raw_value: str, label: str) -> float:
    raw_value = str(raw_value).strip().replace(",", ".")
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a positive number.") from exc
    if value <= 0:
        raise ValueError(f"{label} must be a positive number.")
    return value


def _validated_fraction(raw_value: str, label: str) -> float:
    value = _validated_positive_float(raw_value, label)
    if value > 1:
        raise ValueError(f"{label} must be between 0 and 1.")
    return value


def _format_peak_threshold_percent(fraction: float) -> str:
    return f"{fraction * 100:g}"


def _format_fraction_percent(fraction: float) -> str:
    return f"{fraction * 100:g}"


def copy_starter_files_to(destination_parent: str | Path, *, examples_root: Path | None = None) -> Path:
    examples = Path(examples_root) if examples_root is not None else examples_dir()
    sources = [(relative_path, examples / relative_path) for relative_path in STARTER_EXAMPLE_DIRS]
    missing = [str(path) for _, path in sources if not path.is_dir()]
    if missing:
        raise FileNotFoundError("Missing starter files: " + "; ".join(missing))

    destination = _next_available_folder(Path(destination_parent).expanduser() / "AutoSupportGenerator_examples")
    destination.mkdir(parents=True, exist_ok=False)
    for relative_path, source in sources:
        shutil.copytree(source, destination / relative_path.name)
    return destination


def _next_available_folder(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.name}_{index}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Could not choose a free starter-files folder near {path}.")


def main() -> None:
    root = Tk()
    SIGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
