from __future__ import annotations

import os
import queue
import sys
import threading
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox
from tkinter import ttk

from .external_tools import find_mnova_executable
from .graph.state import GenerateSIRequest
from .workflows.generate_si import output_path_from_state, run_generate_si


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
        self.output_docx = StringVar(value=str(_default_output_path()))
        self.input_kind = StringVar(value="word")
        self.check_support = BooleanVar(value=True)
        self.status_text = StringVar(value="Ready")

        self._is_running = False
        self._log_queue: queue.Queue[str] = queue.Queue()

        self._configure_style()
        self._build_ui()
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
        outer.rowconfigure(4, weight=1)

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
        options.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            options,
            text="Check support (NMR counts and HRMS values)",
            variable=self.check_support,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(options, textvariable=self.status_text, style="Status.TLabel").grid(row=0, column=1, sticky="e")
        self.progress = ttk.Progressbar(options, mode="indeterminate", length=180)
        self.progress.grid(row=0, column=2, sticky="e", padx=(12, 0))

        log_frame = ttk.LabelFrame(outer, text="Run Log", padding=8)
        log_frame.grid(row=4, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log = _LogText(log_frame)
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)

        actions = ttk.Frame(outer)
        actions.grid(row=5, column=0, sticky="ew", pady=(12, 0))
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

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word documents", "*.docx"), ("All files", "*.*")],
            initialfile=Path(self.output_docx.get()).name if self.output_docx.get() else "support_information.docx",
        )
        if path:
            variable_path = Path(path)
            self.output_docx.set(str(variable_path))

    def _load_examples(self) -> None:
        examples = _examples_dir()
        table = examples / "test_input.docx"
        spectra = examples / "test_input.zip"
        if not table.exists() or not spectra.exists():
            messagebox.showerror("Auto Support Generator", f"Example files were not found in:\n{examples}")
            return
        self.input_kind.set("word")
        self.input_path.set(str(table))
        self.spectra_zip.set(str(spectra))
        self.output_docx.set(str(_default_output_path()))
        self.status_text.set("Example loaded")

    def _open_examples_folder(self) -> None:
        examples = _examples_dir()
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

    def _start_generation(self) -> None:
        if self._is_running:
            messagebox.showinfo("SI Generator", "Generation is already running.")
            return

        try:
            request = self._build_request()
        except ValueError as exc:
            messagebox.showerror("SI Generator", str(exc))
            return

        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._is_running = True
        self.run_button.configure(state="disabled")
        self.status_text.set("Running")
        self.progress.start(12)
        self.log.write(
            "\n> Generate SI\n"
            f"Input: {request.input_path}\n"
            f"Output: {request.output_path}\n\n"
        )
        thread = threading.Thread(target=self._run_workflow, args=(request,), daemon=True)
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
            check_support=self.check_support.get(),
        )

    def _run_workflow(self, request: GenerateSIRequest) -> None:
        writer = _QueueWriter(self._log_queue)
        try:
            with redirect_stdout(writer), redirect_stderr(writer):
                result = run_generate_si(request)
            self._log_queue.put(f"\nGenerated {output_path_from_state(result).resolve()}\n")
            if result.get("artifacts", {}).get("manifest"):
                self._log_queue.put(f"Manifest: {result['artifacts']['manifest']}\n")
            self._log_queue.put("\nDone.\n")
            self._log_queue.put("__RUN_SUCCEEDED__")
        except Exception as exc:
            self._log_queue.put(f"\nERROR: {exc}\n")
            self._log_queue.put("__RUN_FAILED__")
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
                elif item == "__RUN_SUCCEEDED__":
                    self.status_text.set("Done")
                elif item == "__RUN_FAILED__":
                    self.status_text.set("Failed")
                else:
                    self.log.write(item)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log_queue)

    def _open_output_folder(self) -> None:
        path = Path(self.output_docx.get() or ".").expanduser()
        folder = path if path.is_dir() else path.parent
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))


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
        no_check_support=not check_support,
    )


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


def _optional_profile(raw_value: str) -> str | Path | None:
    raw_value = raw_value.strip().strip('"')
    if not raw_value:
        return None
    path = Path(raw_value).expanduser()
    return path if path.exists() else raw_value


def main() -> None:
    root = Tk()
    SIGeneratorApp(root)
    root.mainloop()


def _app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _examples_dir() -> Path:
    return _app_base_dir() / "examples"


def _default_output_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AutoSupportGenerator" / "output" / "support_information.docx"
    return Path.cwd() / "output" / "support_information.docx"


if __name__ == "__main__":
    main()
