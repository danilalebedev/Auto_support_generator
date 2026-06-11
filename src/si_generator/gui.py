from __future__ import annotations

import os
import queue
import threading
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox
from tkinter import ttk
from typing import Any

from .domain.manifest import manifest_has_errors
from .domain.patching import parse_renumber_map, parse_reorder_list
from .domain.types import SpectrumEmbedMode
from .external_tools import find_mnova_executable
from .graph.state import CheckSIRequest, GenerateSIRequest, PatchSIRequest
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
        self.root.geometry("980x720")
        self.root.minsize(820, 620)

        self.input_path = StringVar()
        self.spectra_zip = StringVar()
        self.template_docx = StringVar()
        self.style_config = StringVar()
        self.journal_profile = StringVar()
        self.references_file = StringVar()
        self.mnova_exe = StringVar()
        self.output_docx = StringVar(value=str(default_output_path()))
        self.input_kind = StringVar(value="word")
        self.insert_spectra_as = StringVar(value="png")
        self.check_support = BooleanVar(value=True)
        self.generate_loadings = BooleanVar(value=False)
        self.status_text = StringVar(value="Ready")
        self.result_support = StringVar(value="")
        self.result_spectra = StringVar(value="")
        self.result_manifest = StringVar(value="")
        self.existing_manifest = StringVar(value="")
        self.patch_output_docx = StringVar(value="")
        self.patch_renumber = StringVar(value="")
        self.patch_reorder = StringVar(value="")

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
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(5, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Auto Support Generator", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Word table + spectra zip -> formatted Supporting Information", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Button(header, text="Load example", command=self._load_examples).grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))
        ttk.Button(header, text="Open examples", command=self._open_examples_folder).grid(row=0, column=2, rowspan=2, sticky="e", padx=(8, 0))

        files = ttk.LabelFrame(outer, text="Input and Output", padding=12)
        files.grid(row=1, column=0, sticky="ew")
        files.columnconfigure(1, weight=1)

        ttk.Label(files, text="Table type").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        kind = ttk.Frame(files)
        kind.grid(row=0, column=1, sticky="w", pady=4)
        ttk.Radiobutton(kind, text="Word table with ChemDraw objects", variable=self.input_kind, value="word").pack(side="left")
        ttk.Radiobutton(kind, text="CSV table", variable=self.input_kind, value="csv").pack(side="left", padx=(16, 0))

        self._file_row(files, 1, "Compound table", self.input_path, self._browse_input)
        self._file_row(files, 2, "Spectra zip", self.spectra_zip, lambda: self._browse_file(self.spectra_zip, [("Zip archives", "*.zip"), ("All files", "*.*")]))
        self._file_row(files, 3, "Template .docx", self.template_docx, lambda: self._browse_file(self.template_docx, [("Word documents", "*.docx"), ("All files", "*.*")]), optional=True)
        self._file_row(files, 4, "Style config .yml", self.style_config, lambda: self._browse_file(self.style_config, [("YAML files", "*.yml *.yaml"), ("All files", "*.*")]), optional=True)
        self._file_row(files, 5, "Journal profile", self.journal_profile, lambda: self._browse_file(self.journal_profile, [("YAML files", "*.yml *.yaml"), ("All files", "*.*")]), optional=True)
        self._file_row(files, 6, "References .yml", self.references_file, lambda: self._browse_file(self.references_file, [("YAML files", "*.yml *.yaml"), ("All files", "*.*")]), optional=True)
        self._file_row(
            files,
            7,
            "MestReNova .exe",
            self.mnova_exe,
            lambda: self._browse_file(self.mnova_exe, [("MestReNova", "*.exe"), ("All files", "*.*")]),
            optional=True,
            extra_button=("Detect", self._detect_mnova),
        )
        self._file_row(files, 8, "Output .docx", self.output_docx, self._browse_output)

        options = ttk.LabelFrame(outer, text="Options", padding=12)
        options.grid(row=2, column=0, sticky="ew", pady=(12, 12))
        options.columnconfigure(3, weight=1)
        ttk.Checkbutton(
            options,
            text="Check support (NMR counts and HRMS values)",
            variable=self.check_support,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(options, text="Spectra appendix").grid(row=0, column=1, sticky="e", padx=(12, 8))
        ttk.Combobox(
            options,
            textvariable=self.insert_spectra_as,
            values=("png", "mnova", "both", "none"),
            state="readonly",
            width=8,
        ).grid(row=0, column=2, sticky="w")
        ttk.Label(options, textvariable=self.status_text, style="Status.TLabel").grid(row=0, column=3, sticky="e")
        self.progress = ttk.Progressbar(options, mode="indeterminate", length=180)
        self.progress.grid(row=0, column=4, sticky="e", padx=(12, 0))
        ttk.Checkbutton(
            options,
            text="Calculate reagent loadings",
            variable=self.generate_loadings,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

        results = ttk.LabelFrame(outer, text="Results", padding=12)
        results.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        results.columnconfigure(1, weight=1)
        self._result_row(results, 0, "Support .docx", self.result_support)
        self._result_row(results, 1, "Spectra package", self.result_spectra)
        self._result_row(results, 2, "Manifest", self.result_manifest)

        tools = ttk.LabelFrame(outer, text="Existing SI Tools", padding=12)
        tools.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        tools.columnconfigure(1, weight=1)
        self._file_row(
            tools,
            0,
            "Manifest",
            self.existing_manifest,
            lambda: self._browse_file(self.existing_manifest, [("Manifest JSON", "*.json"), ("All files", "*.*")]),
            optional=True,
            extra_button=("Check", self._start_manifest_check),
        )
        self._file_row(tools, 1, "Patched output .docx", self.patch_output_docx, self._browse_patch_output, optional=True)
        ttk.Label(tools, text="Renumber").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(tools, textvariable=self.patch_renumber).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Label(tools, text="Example: 2a=3a,2b=3b", style="Muted.TLabel").grid(row=2, column=2, sticky="w", padx=(8, 0), pady=4)
        ttk.Label(tools, text="Reorder").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(tools, textvariable=self.patch_reorder).grid(row=3, column=1, sticky="ew", pady=4)
        ttk.Button(tools, text="Apply patch", command=self._start_patch).grid(row=3, column=2, sticky="e", padx=(8, 0), pady=4)

        log_frame = ttk.LabelFrame(outer, text="Run Log", padding=8)
        log_frame.grid(row=5, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log = _LogText(log_frame)
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)

        actions = ttk.Frame(outer)
        actions.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        actions.columnconfigure(0, weight=1)
        self.run_button = ttk.Button(actions, text="Generate SI", command=self._start_generation, style="Accent.TButton")
        self.run_button.pack(side="right")
        ttk.Button(actions, text="Open output folder", command=self._open_output_folder).pack(side="right", padx=(0, 8))
        ttk.Button(actions, text="Clear log", command=lambda: self.log.clear()).pack(side="right", padx=(0, 8))

    def _file_row(self, parent, row: int, label: str, variable: StringVar, command, optional: bool = False, extra_button=None) -> None:
        ttk.Label(parent, text=f"{label}{' (optional)' if optional else ''}").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        button_box = ttk.Frame(parent)
        button_box.grid(row=row, column=2, sticky="e", padx=(8, 0), pady=4)
        if extra_button:
            text, extra_command = extra_button
            ttk.Button(button_box, text=text, command=extra_command).pack(side="left", padx=(0, 6))
        ttk.Button(button_box, text="Browse...", command=command).pack(side="left")

    def _result_row(self, parent, row: int, label: str, variable: StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        entry = ttk.Entry(parent, textvariable=variable, state="readonly")
        entry.grid(row=row, column=1, sticky="ew", pady=3)

    def _browse_input(self) -> None:
        if self.input_kind.get() == "csv":
            types = [("CSV files", "*.csv"), ("All files", "*.*")]
        else:
            types = [("Word documents", "*.docx"), ("All files", "*.*")]
        self._browse_file(self.input_path, types)
        if self.input_path.get() and not self.output_docx.get():
            self.output_docx.set(str(Path(self.input_path.get()).with_name("support_information.docx")))

    def _browse_file(self, variable: StringVar, filetypes) -> None:
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            variable.set(path)
            self._save_settings()

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word documents", "*.docx"), ("All files", "*.*")],
            initialfile=Path(self.output_docx.get()).name if self.output_docx.get() else "support_information.docx",
        )
        if path:
            variable_path = Path(path)
            self.output_docx.set(str(variable_path))
            self._save_settings()

    def _browse_patch_output(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word documents", "*.docx"), ("All files", "*.*")],
            initialfile="support_information_patched.docx",
        )
        if path:
            self.patch_output_docx.set(path)
            self._save_settings()

    def _load_examples(self) -> None:
        examples = examples_dir()
        table = examples / "test_input.docx"
        spectra = examples / "test_input.zip"
        if not table.exists() or not spectra.exists():
            messagebox.showerror("Auto Support Generator", f"Example files were not found in:\n{examples}")
            return
        self.input_kind.set("word")
        self.input_path.set(str(table))
        self.spectra_zip.set(str(spectra))
        self.output_docx.set(str(default_output_path()))
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
            request = _build_check_request(self.existing_manifest.get())
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
            spectra_zip_text=self.spectra_zip.get(),
            template_docx_text=self.template_docx.get(),
            style_config_text=self.style_config.get(),
            journal_profile_text=self.journal_profile.get(),
            references_text=self.references_file.get(),
            mnova_exe_text=self.mnova_exe.get(),
            insert_spectra_as=self.insert_spectra_as.get(),
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
            if manifest_has_errors(result.get("issues", [])):
                self._log_queue.put("\nManifest check failed.\n")
                self._log_queue.put({"type": "run_failed", "error": "Manifest check failed"})
            else:
                self._log_queue.put("\nManifest check passed.\n")
                self._log_queue.put({"type": "run_succeeded", "summary": {"manifest": str(request.manifest_path.resolve())}})
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
            if manifest_has_errors(result.get("issues", [])):
                self._log_queue.put("\nPatch check failed.\n")
                self._log_queue.put({"type": "run_failed", "error": "Patch check failed"})
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

    def _clear_results(self) -> None:
        self.result_support.set("")
        self.result_spectra.set("")
        self.result_manifest.set("")

    def _apply_result_summary(self, summary: dict[str, str]) -> None:
        self.result_support.set(summary.get("support_docx", ""))
        self.result_spectra.set(summary.get("processed_spectra_zip", ""))
        self.result_manifest.set(summary.get("manifest", ""))
        support_path = summary.get("support_docx")
        if support_path:
            self._last_output_folder = Path(support_path).expanduser().parent
        if summary.get("manifest"):
            self.existing_manifest.set(summary["manifest"])
        self._save_settings()

    def _load_saved_settings(self) -> None:
        settings = load_gui_settings()
        for key, variable in self._string_settings_variables().items():
            value = settings.get(key)
            if isinstance(value, str):
                variable.set(value)
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
            "spectra_zip": self.spectra_zip,
            "template_docx": self.template_docx,
            "style_config": self.style_config,
            "journal_profile": self.journal_profile,
            "references_file": self.references_file,
            "mnova_exe": self.mnova_exe,
            "output_docx": self.output_docx,
            "input_kind": self.input_kind,
            "insert_spectra_as": self.insert_spectra_as,
            "existing_manifest": self.existing_manifest,
            "patch_output_docx": self.patch_output_docx,
            "patch_renumber": self.patch_renumber,
            "patch_reorder": self.patch_reorder,
        }

    def _bool_settings_variables(self) -> dict[str, BooleanVar]:
        return {
            "check_support": self.check_support,
            "generate_loadings": self.generate_loadings,
        }

    def _on_close(self) -> None:
        self._save_settings()
        self.root.destroy()


class _LogText(ttk.Frame):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        import tkinter as tk

        self.text = tk.Text(self, wrap="word", height=16, borderwidth=0, font=("Consolas", 10))
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
    spectra_zip_text: str = "",
    template_docx_text: str = "",
    style_config_text: str = "",
    journal_profile_text: str = "",
    references_text: str = "",
    mnova_exe_text: str = "",
    insert_spectra_as: str = "png",
    generate_loadings: bool = False,
    check_support: bool = True,
) -> GenerateSIRequest:
    input_path = _required_existing_file(input_path_text, "Choose an existing compound table.")
    output_docx = Path(output_docx_text.strip().strip('"')).expanduser()
    if not output_docx.name.lower().endswith(".docx"):
        raise ValueError("Output file must be a .docx file.")

    return GenerateSIRequest(
        input_path=input_path,
        input_kind="csv" if input_kind == "csv" else "word",
        output_path=output_docx,
        spectra_zip=_optional_existing_file(spectra_zip_text, "Spectra zip"),
        template_docx=_optional_existing_file(template_docx_text, "Template .docx"),
        style_config_path=_optional_existing_file(style_config_text, "Style config"),
        journal_profile=_optional_profile(journal_profile_text),
        references_path=_optional_existing_file(references_text, "References .yml"),
        mnova_exe=_optional_existing_file(mnova_exe_text, "MestReNova .exe"),
        insert_spectra_as=_validated_spectrum_mode(insert_spectra_as),
        generate_loadings=generate_loadings,
        no_check_support=not check_support,
    )


def _build_check_request(manifest_text: str) -> CheckSIRequest:
    manifest_path = _required_existing_file(manifest_text, "Choose an existing manifest JSON.")
    return CheckSIRequest(manifest_path=manifest_path)


def _build_patch_request(
    *,
    manifest_text: str,
    renumber_text: str,
    reorder_text: str,
    output_docx_text: str = "",
) -> PatchSIRequest:
    manifest_path = _required_existing_file(manifest_text, "Choose an existing manifest JSON.")
    renumber = parse_renumber_map(renumber_text) if renumber_text.strip() else {}
    reorder = parse_reorder_list(reorder_text)
    if not renumber and not reorder:
        raise ValueError("Enter renumber or reorder patch instructions.")
    return PatchSIRequest(
        manifest_path=manifest_path,
        renumber=renumber,
        reorder=reorder,
        output_docx=_optional_output_docx(output_docx_text),
    )


def _build_patch_summary(state: dict[str, Any]) -> dict[str, str]:
    artifacts = state.get("artifacts", {})
    summary = {
        "support_docx": _resolved_artifact(artifacts, "support_docx"),
        "manifest": _resolved_artifact(artifacts, "manifest"),
    }
    return {key: value for key, value in summary.items() if value}


def _build_result_summary(state: dict[str, Any]) -> dict[str, str]:
    artifacts = state.get("artifacts", {})
    output_path = output_path_from_state(state)
    summary = {
        "support_docx": str(Path(artifacts.get("support_docx", output_path)).resolve()),
        "processed_spectra_zip": _resolved_artifact(artifacts, "processed_spectra_zip"),
        "manifest": _resolved_artifact(artifacts, "manifest"),
    }
    return {key: value for key, value in summary.items() if value}


def _resolved_artifact(artifacts: dict[str, str], key: str) -> str:
    value = artifacts.get(key, "")
    return str(Path(value).resolve()) if value else ""


def _required_existing_file(raw_path: str, message: str) -> Path:
    path = Path(raw_path.strip().strip('"')).expanduser()
    if not path.exists():
        raise ValueError(message)
    return path


def _optional_existing_file(raw_path: str, label: str) -> Path | None:
    raw_path = raw_path.strip().strip('"')
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if not path.exists():
        raise ValueError(f"{label} does not exist: {path}")
    return path


def _optional_output_docx(raw_path: str) -> Path | None:
    raw_path = raw_path.strip().strip('"')
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if not path.name.lower().endswith(".docx"):
        raise ValueError("Patched output file must be a .docx file.")
    return path


def _optional_profile(raw_value: str) -> str | Path | None:
    raw_value = raw_value.strip().strip('"')
    if not raw_value:
        return None
    path = Path(raw_value).expanduser()
    return path if path.exists() else raw_value


def _validated_spectrum_mode(value: str) -> SpectrumEmbedMode:
    value = value.strip().lower()
    if value in {"png", "mnova", "both", "none"}:
        return value
    return "png"


def main() -> None:
    root = Tk()
    SIGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
