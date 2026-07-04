from __future__ import annotations

import json
import os
import queue
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
    DEFAULT_WHITTAKER_ASYMMETRY,
    DEFAULT_WHITTAKER_LAMBDA,
)
from .domain.types import SpectrumEmbedMode
from .external_tools import find_mnova_executable
from .gui_settings import load_gui_settings, save_gui_settings
from .runtime_diagnostics import format_preflight_issues, issue_has_errors, preflight_generate_request
from .runtime_paths import default_output_path, examples_dir
from .workflows.check_si import run_check_si
from .workflows.generate_si import output_path_from_state, run_generate_si
from .workflows.patch_si import run_patch_si


class SIGeneratorApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Auto Support Generator")
        self.root.geometry("840x560")
        self.root.minsize(720, 480)
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
        self.output_docx = StringVar(value=str(default_output_path()))
        self.input_kind = StringVar(value="word")
        self.insert_spectra_as = StringVar(value="png")
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

        self._is_running = False
        self._last_output_folder: Path | None = None
        self._log_queue: queue.Queue[Any] = queue.Queue()

        self._load_saved_settings()
        self._configure_style()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_log_queue()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Muted.TLabel", foreground="#5f6b7a")
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Status.TLabel", foreground="#355070")

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Auto Support Generator", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Compound table + spectra source -> formatted Supporting Information", style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 0)
        )
        ttk.Button(header, text="Load example", command=self._load_examples).grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))
        ttk.Button(header, text="Open examples", command=self._open_examples_folder).grid(row=0, column=2, rowspan=2, sticky="e", padx=(8, 0))

        notebook = ttk.Notebook(outer)
        notebook.grid(row=1, column=0, sticky="nsew")

        generate_tab = ttk.Frame(notebook, padding=12)
        generate_tab.columnconfigure(0, weight=1)
        generate_tab.rowconfigure(2, weight=1)
        notebook.add(generate_tab, text="Generate")

        simple = ttk.LabelFrame(generate_tab, text="Simple", padding=12)
        simple.grid(row=0, column=0, sticky="ew")
        simple.columnconfigure(1, weight=1)
        ttk.Label(simple, text="Table type").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        kind = ttk.Frame(simple)
        kind.grid(row=0, column=1, sticky="w", pady=4)
        ttk.Radiobutton(kind, text="Word table with ChemDraw objects", variable=self.input_kind, value="word").pack(side="left")
        ttk.Radiobutton(kind, text="CSV table", variable=self.input_kind, value="csv").pack(side="left", padx=(16, 0))
        self._file_row(simple, 1, "Compound table", self.input_path, self._browse_input)
        self._source_row(simple, 2, "Spectra source", self.spectra_source, self._browse_spectra_source, self._browse_spectra_folder)
        self._file_row(simple, 3, "Output .docx", self.output_docx, self._browse_output)

        results = ttk.LabelFrame(generate_tab, text="Results", padding=12)
        results.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        results.columnconfigure(1, weight=1)
        self._result_row(results, 0, "Support .docx", self.result_support, lambda: self._open_result_path(self.result_support, "Support .docx"))
        self._result_row(results, 1, "Output folder", self.result_output_folder, lambda: self._open_result_path(self.result_output_folder, "Output folder"))
        self._result_row(results, 2, "Logs", self.result_logs, lambda: self._open_result_path(self.result_logs, "Logs"))
        self._result_row(results, 3, "Report", self.result_report, lambda: self._open_result_path(self.result_report, "Report"))
        ttk.Label(results, textvariable=self.result_overview, style="Muted.TLabel").grid(row=4, column=0, columnspan=3, sticky="ew", pady=(6, 0))

        log_frame = ttk.LabelFrame(generate_tab, text="Run Log", padding=8)
        log_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log = _LogText(log_frame, height=6)
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)

        advanced_scroll = _ScrollableFrame(notebook, padding=12)
        advanced = advanced_scroll.content
        advanced.columnconfigure(0, weight=1)
        notebook.add(advanced_scroll, text="Advanced")

        files = ttk.LabelFrame(advanced, text="Optional inputs", padding=12)
        files.grid(row=0, column=0, sticky="ew")
        files.columnconfigure(1, weight=1)
        self._file_row(files, 0, "SI template .docx", self.template_docx, lambda: self._browse_file(self.template_docx, [("Word documents", "*.docx"), ("All files", "*.*")]), optional=True)
        self._file_row(files, 1, "References .yml", self.references_file, lambda: self._browse_file(self.references_file, [("YAML files", "*.yml *.yaml"), ("All files", "*.*")]), optional=True)
        self._file_row(
            files,
            2,
            "MestReNova .exe",
            self.mnova_exe,
            lambda: self._browse_file(self.mnova_exe, [("MestReNova", "*.exe"), ("All files", "*.*")]),
            optional=True,
            extra_button=("Detect", self._detect_mnova),
        )

        options = ttk.LabelFrame(advanced, text="Processing", padding=12)
        options.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Checkbutton(
            options,
            text="Check support (NMR, HRMS, elemental analysis)",
            variable=self.check_support,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Label(options, text="Spectra appendix").grid(row=0, column=2, sticky="e", padx=(12, 8), pady=4)
        ttk.Combobox(
            options,
            textvariable=self.insert_spectra_as,
            values=("png", "mnova", "none"),
            state="readonly",
            width=8,
        ).grid(row=0, column=3, sticky="w", pady=4)
        ttk.Label(options, text="1H threshold (%)").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(options, textvariable=self.peak_threshold_1h_percent, width=8).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(options, text="13C threshold (%)").grid(row=1, column=2, sticky="e", padx=(12, 8), pady=4)
        ttk.Entry(options, textvariable=self.peak_threshold_13c_percent, width=8).grid(row=1, column=3, sticky="w", pady=4)

        baseline = ttk.LabelFrame(advanced, text="Baseline correction", padding=12)
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
        ttk.Label(baseline, text="Whittaker lambda").grid(row=1, column=2, sticky="e", padx=(12, 8), pady=4)
        ttk.Entry(baseline, textvariable=self.whittaker_lambda, width=12).grid(row=1, column=3, sticky="w", pady=4)
        ttk.Label(baseline, text="Whittaker asymmetry").grid(row=1, column=4, sticky="e", padx=(12, 8), pady=4)
        ttk.Entry(baseline, textvariable=self.whittaker_asymmetry, width=10).grid(row=1, column=5, sticky="w", pady=4)

        loadings = ttk.LabelFrame(advanced, text="Reagent Loadings", padding=12)
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

        tools_scroll = _ScrollableFrame(notebook, padding=12)
        tools = tools_scroll.content
        tools.columnconfigure(0, weight=1)
        notebook.add(tools_scroll, text="Tools")

        check_box = ttk.LabelFrame(tools, text="Check existing support", padding=12)
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

        patch_box = ttk.LabelFrame(tools, text="Patch existing support", padding=12)
        patch_box.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        patch_box.columnconfigure(1, weight=1)
        self._file_row(patch_box, 0, "Patched output .docx", self.patch_output_docx, self._browse_patch_output, optional=True)
        ttk.Label(patch_box, text="Renumber").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(patch_box, textvariable=self.patch_renumber).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(patch_box, text="Example: 2a=3a,2b=3b", style="Muted.TLabel").grid(row=1, column=2, sticky="w", padx=(8, 0), pady=4)
        ttk.Label(patch_box, text="Remove").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(patch_box, textvariable=self.patch_remove).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Label(patch_box, text="Example: 2a,2c", style="Muted.TLabel").grid(row=2, column=2, sticky="w", padx=(8, 0), pady=4)
        ttk.Label(patch_box, text="Reorder").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(patch_box, textvariable=self.patch_reorder).grid(row=3, column=1, sticky="ew", pady=4)
        ttk.Button(patch_box, text="Apply patch", command=self._start_patch).grid(row=3, column=2, sticky="e", padx=(8, 0), pady=4)

        add_box = ttk.LabelFrame(tools, text="Add compounds", padding=12)
        add_box.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        add_box.columnconfigure(1, weight=1)
        self._file_row(add_box, 0, "Existing manifest", self.add_manifest, lambda: self._browse_file(self.add_manifest, [("Manifest JSON", "*.json"), ("All files", "*.*")]), optional=True)
        self._file_row(add_box, 1, "Existing support .docx", self.add_support_docx, lambda: self._browse_file(self.add_support_docx, [("Word documents", "*.docx"), ("All files", "*.*")]), optional=True)
        self._file_row(add_box, 2, "New compound table", self.add_input_path, self._browse_add_input, optional=True)
        self._source_row(
            add_box,
            3,
            "New spectra source",
            self.add_spectra_source,
            lambda: self._browse_file(self.add_spectra_source, [("Zip archives", "*.zip"), ("All files", "*.*")]),
            lambda: self._browse_folder(self.add_spectra_source),
            optional=True,
        )
        self._file_row(add_box, 4, "Output .docx", self.add_output_docx, self._browse_add_output, optional=True)
        ttk.Button(add_box, text="Add compounds", command=self._start_add_compounds).grid(row=5, column=2, sticky="e", padx=(8, 0), pady=(8, 0))

        actions = ttk.Frame(self.root, padding=(18, 8, 18, 18))
        actions.grid(row=1, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        ttk.Label(actions, textvariable=self.status_text, style="Status.TLabel").pack(side="left")
        self.progress = ttk.Progressbar(actions, mode="indeterminate", length=150)
        self.progress.pack(side="left", padx=(12, 0))
        self.run_button = ttk.Button(actions, text="Generate SI", command=self._start_generation, style="Accent.TButton")
        self.run_button.pack(side="right")
        ttk.Button(actions, text="Open output folder", command=self._open_output_folder).pack(side="right", padx=(0, 8))
        ttk.Button(actions, text="Clear log", command=lambda: self.log.clear()).pack(side="right", padx=(0, 8))

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

    def _result_row(self, parent, row: int, label: str, variable: StringVar, open_command=None) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        entry = ttk.Entry(parent, textvariable=variable, state="readonly")
        entry.grid(row=row, column=1, sticky="ew", pady=3)
        if open_command:
            ttk.Button(parent, text="Open", command=open_command, width=8).grid(row=row, column=2, sticky="e", padx=(8, 0), pady=3)

    def _browse_input(self) -> None:
        if self.input_kind.get() == "csv":
            types = [("CSV files", "*.csv"), ("All files", "*.*")]
        else:
            types = [("Word documents", "*.docx"), ("All files", "*.*")]
        self._browse_file(self.input_path, types)
        if self.input_path.get() and not self.output_docx.get():
            self.output_docx.set(str(Path(self.input_path.get()).with_name("support_information.docx")))

    def _browse_file(self, variable: StringVar, filetypes) -> None:
        kwargs: dict[str, object] = {"filetypes": filetypes}
        initialdir = _dialog_initialdir(variable.get(), self.input_path.get(), self.output_docx.get(), self._last_output_folder)
        if initialdir:
            kwargs["initialdir"] = initialdir
        path = filedialog.askopenfilename(**kwargs)
        if path:
            variable.set(path)
            self._save_settings()

    def _browse_folder(self, variable: StringVar) -> None:
        kwargs: dict[str, object] = {}
        initialdir = _dialog_initialdir(variable.get(), self.input_path.get(), self.output_docx.get(), self._last_output_folder)
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
        initialdir = _dialog_initialdir(self.output_docx.get(), self.input_path.get(), self._last_output_folder)
        if initialdir:
            kwargs["initialdir"] = initialdir
        path = filedialog.asksaveasfilename(**kwargs)
        if path:
            variable_path = Path(path)
            self.output_docx.set(str(variable_path))
            self._save_settings()

    def _browse_patch_output(self) -> None:
        kwargs: dict[str, object] = {
            "defaultextension": ".docx",
            "filetypes": [("Word documents", "*.docx"), ("All files", "*.*")],
            "initialfile": "support_information_patched.docx",
        }
        initialdir = _dialog_initialdir(self.patch_output_docx.get(), self.existing_manifest.get(), self.output_docx.get(), self._last_output_folder)
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
        initialdir = _dialog_initialdir(self.add_output_docx.get(), self.add_input_path.get(), self.output_docx.get(), self._last_output_folder)
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
        self.status_text.set("Example loaded")
        self._save_settings()

    def _open_examples_folder(self) -> None:
        examples = examples_dir()
        examples.mkdir(parents=True, exist_ok=True)
        os.startfile(str(examples))

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
                insert_spectra_as=self.insert_spectra_as.get(),
                peak_threshold_1h_percent_text=self.peak_threshold_1h_percent.get(),
                peak_threshold_13c_percent_text=self.peak_threshold_13c_percent.get(),
                baseline_mode_text=self.baseline_mode.get(),
                baseline_apply_1h=self.baseline_apply_1h.get(),
                baseline_apply_13c=self.baseline_apply_13c.get(),
                baseline_poly_order_text=self.baseline_poly_order.get(),
                whittaker_lambda_text=self.whittaker_lambda.get(),
                whittaker_asymmetry_text=self.whittaker_asymmetry.get(),
                generate_loadings=self.generate_loadings.get(),
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
            output_docx_text=self.output_docx.get(),
            spectra_source_text=self.spectra_source.get(),
            template_docx_text=self.template_docx.get(),
            references_text=self.references_file.get(),
            loadings_schema_text=self.loadings_schema_docx.get(),
            loadings_scope_text=self.loadings_scope_docx.get(),
            mnova_exe_text=self.mnova_exe.get(),
            insert_spectra_as=self.insert_spectra_as.get(),
            peak_threshold_1h_percent_text=self.peak_threshold_1h_percent.get(),
            peak_threshold_13c_percent_text=self.peak_threshold_13c_percent.get(),
            baseline_mode_text=self.baseline_mode.get(),
            baseline_apply_1h=self.baseline_apply_1h.get(),
            baseline_apply_13c=self.baseline_apply_13c.get(),
            baseline_poly_order_text=self.baseline_poly_order.get(),
            whittaker_lambda_text=self.whittaker_lambda.get(),
            whittaker_asymmetry_text=self.whittaker_asymmetry.get(),
            generate_loadings=self.generate_loadings.get(),
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
            summary = _build_patch_summary(result)
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
        self.root.after(100, self._poll_log_queue)

    def _open_output_folder(self) -> None:
        path = self._last_output_folder or Path(self.output_docx.get() or ".").expanduser()
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
        legacy_threshold = settings.get("peak_threshold_percent")
        if isinstance(legacy_threshold, str):
            if not isinstance(settings.get("peak_threshold_1h_percent"), str):
                self.peak_threshold_1h_percent.set(legacy_threshold)
            if not isinstance(settings.get("peak_threshold_13c_percent"), str):
                self.peak_threshold_13c_percent.set(legacy_threshold)
        for key, variable in self._bool_settings_variables().items():
            value = settings.get(key)
            if isinstance(value, bool):
                variable.set(value)

    def _save_settings(self) -> None:
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
            "output_docx": self.output_docx,
            "peak_threshold_1h_percent": self.peak_threshold_1h_percent,
            "peak_threshold_13c_percent": self.peak_threshold_13c_percent,
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

    def _bool_settings_variables(self) -> dict[str, BooleanVar]:
        return {
            "check_support": self.check_support,
            "generate_loadings": self.generate_loadings,
            "baseline_apply_1h": self.baseline_apply_1h,
            "baseline_apply_13c": self.baseline_apply_13c,
        }

    def _on_close(self) -> None:
        self._save_settings()
        self.root.destroy()


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
    insert_spectra_as: str = "png",
    peak_threshold_percent_text: str = "",
    peak_threshold_1h_percent_text: str = "",
    peak_threshold_13c_percent_text: str = "",
    baseline_mode_text: str = DEFAULT_BASELINE_MODE,
    baseline_apply_1h: bool = DEFAULT_BASELINE_APPLY_1H,
    baseline_apply_13c: bool = DEFAULT_BASELINE_APPLY_13C,
    baseline_poly_order_text: str = str(DEFAULT_BASELINE_POLY_ORDER),
    whittaker_lambda_text: str = f"{DEFAULT_WHITTAKER_LAMBDA:g}",
    whittaker_asymmetry_text: str = f"{DEFAULT_WHITTAKER_ASYMMETRY:g}",
    generate_loadings: bool = False,
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
        baseline_mode=_validated_baseline_mode(baseline_mode_text),
        baseline_apply_1h=bool(baseline_apply_1h),
        baseline_apply_13c=bool(baseline_apply_13c),
        baseline_poly_order=_validated_positive_int(baseline_poly_order_text, "Baseline polynomial order"),
        whittaker_lambda=_validated_positive_float(whittaker_lambda_text, "Whittaker lambda"),
        whittaker_asymmetry=_validated_fraction(whittaker_asymmetry_text, "Whittaker asymmetry"),
        generate_loadings=generate_loadings,
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
    insert_spectra_as: str = "png",
    peak_threshold_percent_text: str = "",
    peak_threshold_1h_percent_text: str = "",
    peak_threshold_13c_percent_text: str = "",
    baseline_mode_text: str = DEFAULT_BASELINE_MODE,
    baseline_apply_1h: bool = DEFAULT_BASELINE_APPLY_1H,
    baseline_apply_13c: bool = DEFAULT_BASELINE_APPLY_13C,
    baseline_poly_order_text: str = str(DEFAULT_BASELINE_POLY_ORDER),
    whittaker_lambda_text: str = f"{DEFAULT_WHITTAKER_LAMBDA:g}",
    whittaker_asymmetry_text: str = f"{DEFAULT_WHITTAKER_ASYMMETRY:g}",
    generate_loadings: bool = False,
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
        baseline_mode=_validated_baseline_mode(baseline_mode_text),
        baseline_apply_1h=bool(baseline_apply_1h),
        baseline_apply_13c=bool(baseline_apply_13c),
        baseline_poly_order=_validated_positive_int(baseline_poly_order_text, "Baseline polynomial order"),
        whittaker_lambda=_validated_positive_float(whittaker_lambda_text, "Whittaker lambda"),
        whittaker_asymmetry=_validated_fraction(whittaker_asymmetry_text, "Whittaker asymmetry"),
        generate_loadings=generate_loadings,
        no_check_support=not check_support,
    )


def _build_patch_request(
    *,
    manifest_text: str,
    renumber_text: str,
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


def _example_field_updates(table: Path, spectra_zip: Path, output_docx: Path) -> dict[str, str]:
    return {
        "input_kind": "word",
        "input_path": str(table),
        "spectra_source": str(spectra_zip),
        "spectra_zip": str(spectra_zip),
        "output_docx": str(output_docx),
        "template_docx": "",
        "references_file": "",
        "loadings_schema_docx": "",
        "loadings_scope_docx": "",
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


def main() -> None:
    root = Tk()
    SIGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
