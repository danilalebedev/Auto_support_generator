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
from .domain.patching import parse_remove_list, parse_renumber_map, parse_reorder_list
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


STARTER_FILE_RELATIVE_PATHS = (
    Path("starter") / "compound_table_starter.docx",
    Path("starter") / "compound_table_starter.csv",
    Path("starter") / "spectra_source_layout.txt",
    Path("starter") / "README_starter_files.md",
    Path("templates") / "SI_template_visual_current.docx",
)


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
        self.references_file = StringVar()
        self.loadings_schema_docx = StringVar()
        self.loadings_scope_docx = StringVar()
        self.mnova_exe = StringVar()
        self.mnova_graphics_profile = StringVar()
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
        self.patch_output_docx = StringVar(value="")
        self.patch_renumber = StringVar(value="")
        self.patch_remove = StringVar(value="")
        self.patch_reorder = StringVar(value="")
        self.add_manifest = StringVar(value="")
        self.add_support_docx = StringVar(value="")
        self.add_input_path = StringVar(value="")
        self.add_spectra_source = StringVar(value="")
        self.add_output_docx = StringVar(value="")
        self.add_input_kind = StringVar(value="word")
        self.page_title = StringVar(value="Generate SI")
        self.page_subtitle = StringVar(value="Create formatted Supporting Information from a compound table and spectra.")

        self._is_running = False
        self._last_output_folder: Path | None = None
        self._log_queue: queue.Queue[Any] = queue.Queue()
        self._poll_after_id: str | None = None
        self._theme = THEME_PALETTES["light"]
        self._nav_buttons: dict[str, _PillButton] = {}
        self._sidebar_buttons: list[_PillButton] = []
        self._page_frames: dict[str, ttk.Frame] = {}
        self._scrollable_frames: list[_ScrollableFrame] = []
        self._theme_switch: _ThemeSwitch | None = None
        self._logo_mark_source: tk.PhotoImage | None = None
        self._logo_mark_image: tk.PhotoImage | None = None

        self._load_saved_settings()
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

        quick = ttk.Frame(sidebar, style="Sidebar.TFrame")
        quick.grid(row=9, column=0, sticky="ew", pady=(14, 0))
        quick.columnconfigure(0, weight=1)
        for row, (text, command) in enumerate(
            (
                ("Example", self._load_examples),
                ("Starter files", self._copy_starter_files),
                ("Examples", self._open_examples_folder),
            )
        ):
            button = _PillButton(quick, text=text, command=command, theme=self._theme, subtle=True, height=34)
            button.grid(row=row, column=0, sticky="ew", pady=(0, 7))
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
        ttk.Button(footer, text="Clear log", command=lambda: self.log.clear()).grid(row=0, column=3, sticky="e", padx=(8, 0))
        self.run_button = ttk.Button(footer, text="Generate SI", command=self._start_generation, style="Accent.TButton")
        self.run_button.grid(row=0, column=4, sticky="e", padx=(8, 0))

    def _make_page(self, parent: ttk.Frame, key: str) -> ttk.Frame:
        page = ttk.Frame(parent, style="App.TFrame")
        page.grid(row=0, column=0, sticky="nsew")
        page.grid_remove()
        page.columnconfigure(0, weight=1)
        self._page_frames[key] = page
        return page

    def _build_generate_page(self, parent: ttk.Frame) -> None:
        page = self._make_page(parent, "generate")
        page.rowconfigure(2, weight=1)

        simple = ttk.LabelFrame(page, text="Simple", padding=12, style="Card.TLabelframe")
        simple.grid(row=0, column=0, sticky="ew")
        simple.columnconfigure(1, weight=1)
        self._file_row(simple, 0, "Compound table", self.input_path, self._browse_input)
        self._source_row(simple, 1, "Spectra source", self.spectra_source, self._browse_spectra_source, self._browse_spectra_folder)
        self._folder_row(simple, 2, "Output folder", self.output_folder, self._browse_output_folder)

        results = ttk.LabelFrame(page, text="Results", padding=12, style="Card.TLabelframe")
        results.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        results.columnconfigure(1, weight=1)
        self._result_row(results, 0, "Support .docx", self.result_support, lambda: self._open_result_path(self.result_support, "Support .docx"), "Open support")
        self._result_row(results, 1, "Output folder", self.result_output_folder, lambda: self._open_result_path(self.result_output_folder, "Output folder"), "Open output folder")
        self._result_row(results, 2, "Logs", self.result_logs, lambda: self._open_result_path(self.result_logs, "Logs"), "Open logs")
        self._result_row(results, 3, "Report", self.result_report, lambda: self._open_result_path(self.result_report, "Report"), "Open report")
        ttk.Label(results, textvariable=self.result_overview, style="Muted.TLabel").grid(row=4, column=0, columnspan=3, sticky="ew", pady=(6, 0))

        log_frame = ttk.LabelFrame(page, text="Run Log", padding=8, style="Card.TLabelframe")
        log_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log = _LogText(log_frame, height=8)
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)

    def _build_advanced_page(self, parent: ttk.Frame) -> None:
        page = self._make_page(parent, "advanced")
        page.rowconfigure(0, weight=1)
        advanced_scroll = _ScrollableFrame(page, padding=2)
        self._scrollable_frames.append(advanced_scroll)
        advanced_scroll.grid(row=0, column=0, sticky="nsew")
        advanced = advanced_scroll.content
        advanced.columnconfigure(0, weight=1)

        files = ttk.LabelFrame(advanced, text="Optional inputs", padding=12, style="Card.TLabelframe")
        files.grid(row=0, column=0, sticky="ew")
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
            "Mnova graphics .mngp",
            self.mnova_graphics_profile,
            lambda: self._browse_file(
                self.mnova_graphics_profile,
                [("MestReNova graphic properties", "*.mngp"), ("All files", "*.*")],
            ),
            optional=True,
        )

        options = ttk.LabelFrame(advanced, text="Processing", padding=12, style="Card.TLabelframe")
        options.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(options, text="Compound table type").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        kind = ttk.Frame(options)
        kind.grid(row=0, column=1, columnspan=3, sticky="w", pady=4)
        ttk.Radiobutton(kind, text="Word table with ChemDraw objects", variable=self.input_kind, value="word").pack(side="left")
        ttk.Radiobutton(kind, text="CSV table", variable=self.input_kind, value="csv").pack(side="left", padx=(16, 0))
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

        baseline = ttk.LabelFrame(advanced, text="Baseline correction", padding=12, style="Card.TLabelframe")
        baseline.grid(row=2, column=0, sticky="ew", pady=(10, 0))
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

        loadings = ttk.LabelFrame(advanced, text="Reagent Loadings", padding=12, style="Card.TLabelframe")
        loadings.grid(row=3, column=0, sticky="ew", pady=(10, 0))
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
        self._file_row(
            patch_box,
            0,
            "Existing manifest",
            self.existing_manifest,
            lambda: self._browse_file(self.existing_manifest, [("Manifest JSON", "*.json"), ("All files", "*.*")]),
        )
        self._file_row(
            patch_box,
            1,
            "Existing support .docx override",
            self.check_support_docx,
            lambda: self._browse_file(self.check_support_docx, [("Word documents", "*.docx"), ("All files", "*.*")]),
            optional=True,
        )
        self._file_row(patch_box, 2, "Patched output .docx", self.patch_output_docx, self._browse_patch_output, optional=True)
        ttk.Label(patch_box, text="Renumber").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(patch_box, textvariable=self.patch_renumber).grid(row=3, column=1, sticky="ew", pady=4)
        ttk.Label(patch_box, text="Example: 2a=3a,2b=3b", style="Muted.TLabel").grid(row=3, column=2, sticky="w", padx=(8, 0), pady=4)
        ttk.Label(patch_box, text="Remove").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(patch_box, textvariable=self.patch_remove).grid(row=4, column=1, sticky="ew", pady=4)
        ttk.Label(patch_box, text="Example: 2a,2c", style="Muted.TLabel").grid(row=4, column=2, sticky="w", padx=(8, 0), pady=4)
        ttk.Label(patch_box, text="Reorder").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(patch_box, textvariable=self.patch_reorder).grid(row=5, column=1, sticky="ew", pady=4)
        ttk.Button(patch_box, text="Apply patch", command=self._start_patch).grid(row=5, column=2, sticky="e", padx=(8, 0), pady=4)

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
        self._file_row(add_box, 0, "Existing manifest", self.add_manifest, lambda: self._browse_file(self.add_manifest, [("Manifest JSON", "*.json"), ("All files", "*.*")]), optional=True)
        self._file_row(add_box, 1, "Existing support .docx", self.add_support_docx, lambda: self._browse_file(self.add_support_docx, [("Word documents", "*.docx"), ("All files", "*.*")]), optional=True)
        ttk.Label(add_box, text="New table type").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        add_kind = ttk.Frame(add_box)
        add_kind.grid(row=2, column=1, columnspan=2, sticky="w", pady=4)
        ttk.Radiobutton(add_kind, text="Word table with ChemDraw objects", variable=self.add_input_kind, value="word").pack(side="left")
        ttk.Radiobutton(add_kind, text="CSV table", variable=self.add_input_kind, value="csv").pack(side="left", padx=(16, 0))
        self._file_row(add_box, 3, "New compound table", self.add_input_path, self._browse_add_input, optional=True)
        self._source_row(
            add_box,
            4,
            "New spectra source",
            self.add_spectra_source,
            lambda: self._browse_file(self.add_spectra_source, [("Zip archives", "*.zip"), ("All files", "*.*")]),
            lambda: self._browse_folder(self.add_spectra_source),
            optional=True,
        )
        self._file_row(add_box, 5, "Output .docx", self.add_output_docx, self._browse_add_output, optional=True)
        ttk.Button(add_box, text="Add compounds", command=self._start_add_compounds).grid(row=6, column=2, sticky="e", padx=(8, 0), pady=(8, 0))

    def _build_instructions_page(self, parent: ttk.Frame) -> None:
        page = self._make_page(parent, "instructions")
        page.rowconfigure(0, weight=1)
        instructions_scroll = _ScrollableFrame(page, padding=2)
        self._scrollable_frames.append(instructions_scroll)
        instructions_scroll.grid(row=0, column=0, sticky="nsew")
        content = instructions_scroll.content
        content.columnconfigure(0, weight=1)

        sections = (
            (
                "Generate a new SI",
                "1. Select a compound table on Generate.\n"
                "2. Select spectra source as a zip archive or a folder.\n"
                "3. Select an output folder.\n"
                "4. Click Generate SI in the bottom-right corner.",
            ),
            (
                "Use examples",
                "Example loads the built-in test input. Starter files copies editable blank files for a new project. "
                "Examples folder opens all bundled input and output examples.",
            ),
            (
                "Processing settings",
                "Open Processing to set the SI template, MestReNova path, Mnova graphics profile, spectra appendix mode, "
                "peak thresholds, ppm ranges, baseline correction and reagent-loading options.",
            ),
            (
                "Review outputs",
                "After generation, use Open support, Open output folder, Open logs and Open report. "
                "Each run is saved into its own output folder with docx, input, spectra, mnova, logs and reports.",
            ),
            (
                "Existing documents",
                "Check validates an existing support from a manifest. Patch creates a modified copy of an SI. "
                "Add appends new compounds without rewriting old compound blocks.",
            ),
        )
        for row, (title, body) in enumerate(sections):
            box = ttk.LabelFrame(content, text=title, padding=12, style="Card.TLabelframe")
            box.grid(row=row, column=0, sticky="ew", pady=(0, 10))
            box.columnconfigure(0, weight=1)
            ttk.Label(box, text=body, wraplength=760, justify="left").grid(row=0, column=0, sticky="ew")

    def _show_page(self, page: str) -> None:
        page_text = {
            "generate": ("Generate SI", "Create formatted Supporting Information from a compound table and spectra."),
            "advanced": ("Processing", "Template, spectra rendering, peak picking, baseline correction, and loadings."),
            "check": ("Check support", "Run validation from an existing manifest and optional support document."),
            "patch": ("Patch SI", "Create a new support document with renumbered, removed, or reordered compounds."),
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
        if self.input_kind.get() == "csv":
            types = [("CSV files", "*.csv"), ("All files", "*.*")]
        else:
            types = [("Word documents", "*.docx"), ("All files", "*.*")]
        self._browse_file(self.input_path, types)
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

    def _browse_patch_output(self) -> None:
        kwargs: dict[str, object] = {
            "defaultextension": ".docx",
            "filetypes": [("Word documents", "*.docx"), ("All files", "*.*")],
            "initialfile": "support_information_patched.docx",
        }
        initialdir = _dialog_initialdir(self.patch_output_docx.get(), self.existing_manifest.get(), self.output_folder.get(), self.output_docx.get(), self._last_output_folder)
        if initialdir:
            kwargs["initialdir"] = initialdir
        path = filedialog.asksaveasfilename(**kwargs)
        if path:
            self.patch_output_docx.set(path)
            self._save_settings()

    def _browse_add_input(self) -> None:
        if self.add_input_kind.get() == "csv":
            types = [("CSV files", "*.csv"), ("All files", "*.*")]
        else:
            types = [("Word documents", "*.docx"), ("All files", "*.*")]
        self._browse_file(self.add_input_path, types)

    def _browse_add_output(self) -> None:
        kwargs: dict[str, object] = {
            "defaultextension": ".docx",
            "filetypes": [("Word documents", "*.docx"), ("All files", "*.*")],
            "initialfile": Path(self.add_output_docx.get()).name if self.add_output_docx.get() else "support_information_added.docx",
        }
        initialdir = _dialog_initialdir(self.add_output_docx.get(), self.add_input_path.get(), self.output_folder.get(), self.output_docx.get(), self._last_output_folder)
        if initialdir:
            kwargs["initialdir"] = initialdir
        path = filedialog.asksaveasfilename(**kwargs)
        if path:
            self.add_output_docx.set(path)
            self._save_settings()

    def _load_examples(self) -> None:
        examples = examples_dir()
        table = examples / "test_input.docx"
        spectra = examples / "test_input.zip"
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
            messagebox.showerror("SI Generator", "Preflight checks failed. See Run Log for details.")
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
                manifest_text=self.existing_manifest.get(),
                support_docx_text=self.check_support_docx.get(),
                renumber_text=self.patch_renumber.get(),
                remove_text=self.patch_remove.get(),
                reorder_text=self.patch_reorder.get(),
                output_docx_text=self.patch_output_docx.get(),
            )
        except ValueError as exc:
            messagebox.showerror("SI Generator", str(exc))
            return
        self._save_settings()
        self._start_background_operation(
            "Patch SI",
            f"Manifest: {request.manifest_path}\nOutput: {request.output_docx or 'auto'}\n",
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
                input_kind=self.add_input_kind.get(),
                input_path_text=self.add_input_path.get(),
                output_docx_text=self.add_output_docx.get(),
                spectra_source_text=self.add_spectra_source.get(),
                template_docx_text=self.template_docx.get(),
                references_text=self.references_file.get(),
                mnova_exe_text=self.mnova_exe.get(),
                mnova_graphics_profile_text=self.mnova_graphics_profile.get(),
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
            f"Manifest: {request.manifest_path}\nNew table: {request.input_path}\nOutput: {request.output_docx}\n",
            self._run_add_compounds_workflow,
            (run_add_compounds, request),
        )

    def _start_background_operation(self, title: str, details: str, target, request) -> None:
        self._is_running = True
        self.run_button.configure(state="disabled")
        self.status_text.set("Running")
        self.progress.start(12)
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
            references_text=self.references_file.get(),
            loadings_schema_text=self.loadings_schema_docx.get(),
            loadings_scope_text=self.loadings_scope_docx.get(),
            mnova_exe_text=self.mnova_exe.get(),
            mnova_graphics_profile_text=self.mnova_graphics_profile.get(),
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
            generate_loadings=self.generate_loadings.get(),
            calculate_elemental_analysis=self.calculate_elemental_analysis.get(),
            check_support=self.check_support.get(),
        )

    def _run_workflow(self, request: GenerateSIRequest) -> None:
        writer = _QueueWriter(self._log_queue)
        try:
            with redirect_stdout(writer), redirect_stderr(writer):
                result = run_generate_si(request)
            summary = _build_result_summary(result)
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
                self._log_queue.put({"type": "run_failed", "error": "Manifest check failed", "summary": summary})
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
                self._log_queue.put({"type": "run_failed", "error": "Patch check failed", "summary": summary})
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
                self._log_queue.put({"type": "run_failed", "error": "Add compounds failed", "summary": summary})
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
        if summary.get("manifest"):
            self.existing_manifest.set(summary["manifest"])
        self._save_settings()

    def _load_saved_settings(self) -> None:
        settings = load_gui_settings()
        for key, variable in self._string_settings_variables().items():
            value = settings.get(key)
            if isinstance(value, str):
                variable.set(value)
        if not self.spectra_source.get() and isinstance(settings.get("spectra_zip"), str):
            self.spectra_source.set(str(settings["spectra_zip"]))
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
            "references_file": self.references_file,
            "loadings_schema_docx": self.loadings_schema_docx,
            "loadings_scope_docx": self.loadings_scope_docx,
            "mnova_exe": self.mnova_exe,
            "mnova_graphics_profile": self.mnova_graphics_profile,
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
            "patch_output_docx": self.patch_output_docx,
            "patch_renumber": self.patch_renumber,
            "patch_remove": self.patch_remove,
            "patch_reorder": self.patch_reorder,
            "add_manifest": self.add_manifest,
            "add_support_docx": self.add_support_docx,
            "add_input_path": self.add_input_path,
            "add_spectra_source": self.add_spectra_source,
            "add_output_docx": self.add_output_docx,
            "add_input_kind": self.add_input_kind,
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
    generate_loadings: bool = False,
    calculate_elemental_analysis: bool = False,
    check_support: bool = True,
) -> GenerateSIRequest:
    input_suffixes = (".csv",) if input_kind == "csv" else (".docx",)
    input_path = _required_existing_file(input_path_text, "Choose an existing compound table.", suffixes=input_suffixes)
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
        input_kind="csv" if input_kind == "csv" else "word",
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
    input_path_text: str,
    output_docx_text: str,
    spectra_source_text: str = "",
    template_docx_text: str = "",
    references_text: str = "",
    mnova_exe_text: str = "",
    mnova_graphics_profile_text: str = "",
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
    generate_loadings: bool = False,
    calculate_elemental_analysis: bool = False,
    check_support: bool = True,
) -> AddCompoundsRequest:
    input_suffixes = (".csv",) if input_kind == "csv" else (".docx",)
    input_path = _required_existing_file(input_path_text, "Choose an existing new compound table.", suffixes=input_suffixes)
    output_docx = Path(output_docx_text.strip().strip('"')).expanduser()
    if not output_docx.name.lower().endswith(".docx"):
        raise ValueError("Add compounds output file must be a .docx file.")
    shared_peak_threshold = _optional_peak_threshold_fraction(peak_threshold_percent_text)
    return AddCompoundsRequest(
        manifest_path=_required_existing_file(manifest_text, "Choose an existing manifest JSON.", suffixes=(".json",)),
        support_docx=_optional_existing_file(support_docx_text, "Existing support .docx", suffixes=(".docx",)),
        input_path=input_path,
        input_kind="csv" if input_kind == "csv" else "word",
        output_docx=output_docx,
        spectra_source=_optional_spectra_source(spectra_source_text),
        template_docx=_optional_existing_file(template_docx_text, "SI template .docx", suffixes=(".docx",)),
        references_path=_optional_existing_file(references_text, "References .yml", suffixes=(".yml", ".yaml")),
        mnova_exe=_optional_existing_file(mnova_exe_text, "MestReNova .exe", suffixes=(".exe",)),
        mnova_graphics_profile=_optional_existing_file(
            mnova_graphics_profile_text,
            "Mnova graphics .mngp",
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
        generate_loadings=generate_loadings,
        calculate_elemental_analysis=calculate_elemental_analysis,
        no_check_support=not check_support,
    )


def _build_patch_request(
    *,
    manifest_text: str,
    renumber_text: str,
    support_docx_text: str = "",
    remove_text: str = "",
    reorder_text: str = "",
    output_docx_text: str = "",
) -> PatchSIRequest:
    manifest_path = _required_existing_file(manifest_text, "Choose an existing manifest JSON.", suffixes=(".json",))
    renumber = parse_renumber_map(renumber_text) if renumber_text.strip() else {}
    remove = parse_remove_list(remove_text)
    reorder = parse_reorder_list(reorder_text)
    if not renumber and not remove and not reorder:
        raise ValueError("Enter renumber, remove, or reorder patch instructions.")
    return PatchSIRequest(
        manifest_path=manifest_path,
        support_docx=_optional_existing_file(support_docx_text, "Existing support .docx", suffixes=(".docx",)),
        renumber=renumber,
        remove=remove,
        reorder=reorder,
        output_docx=_optional_output_docx(output_docx_text),
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


def _example_field_updates(table: Path, spectra_zip: Path, output_docx: Path) -> dict[str, str]:
    return {
        "input_kind": "word",
        "input_path": str(table),
        "spectra_source": str(spectra_zip),
        "spectra_zip": str(spectra_zip),
        "output_docx": str(output_docx),
        "output_folder": str(output_docx.parent),
        "template_docx": "",
        "references_file": "",
        "loadings_schema_docx": "",
        "loadings_scope_docx": "",
        "mnova_graphics_profile": "",
        "h1_ppm_min": f"{DEFAULT_X_RANGES['1H'][0]:g}",
        "h1_ppm_max": f"{DEFAULT_X_RANGES['1H'][1]:g}",
        "c13_ppm_min": f"{DEFAULT_X_RANGES['13C'][0]:g}",
        "c13_ppm_max": f"{DEFAULT_X_RANGES['13C'][1]:g}",
        "existing_manifest": "",
        "check_support_docx": "",
        "patch_output_docx": "",
        "patch_renumber": "",
        "patch_remove": "",
        "patch_reorder": "",
        "add_manifest": "",
        "add_support_docx": "",
        "add_input_path": "",
        "add_spectra_source": "",
        "add_output_docx": "",
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
    if not path.name.lower().endswith(".docx"):
        raise ValueError("Patched output file must be a .docx file.")
    return path


def _validated_spectrum_mode(value: str) -> SpectrumEmbedMode:
    value = value.strip().lower()
    if value in {"png", "mnova", "none"}:
        return value
    return "png"


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
    sources = [(relative_path, examples / relative_path) for relative_path in STARTER_FILE_RELATIVE_PATHS]
    missing = [str(path) for _, path in sources if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing starter files: " + "; ".join(missing))

    destination = _next_available_folder(Path(destination_parent).expanduser() / "AutoSupportGenerator_starter_files")
    destination.mkdir(parents=True, exist_ok=False)
    for relative_path, source in sources:
        target_name = "SI_template.docx" if relative_path.name == "SI_template_visual_current.docx" else relative_path.name
        shutil.copy2(source, destination / target_name)
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
