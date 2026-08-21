from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from share_safe.core import run
from share_safe.models import FileResult, UsageError
from share_safe.report import print_summary

FILE_DIALOG_TYPES = [
    ("Images and PDF", "*.jpg *.jpeg *.png *.webp *.heic *.heif *.hif *.pdf"),
    ("JPEG", "*.jpg *.jpeg"),
    ("PNG", "*.png"),
    ("WebP", "*.webp"),
    ("HEIC", "*.heic *.heif *.hif"),
    ("PDF", "*.pdf"),
    ("All files", "*.*"),
]


def resolve_display_path(raw: str, *, base: Path | None = None) -> str:
    """Return an absolute path for display. Blank input stays blank."""
    text = (raw or "").strip()
    if not text:
        return ""
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = (base if base is not None else Path.cwd()) / path
    return str(path.resolve())


def suggest_output_path(input_path: str) -> str:
    """Default output that never points at the input itself."""
    text = resolve_display_path(input_path)
    if not text:
        return ""
    src = Path(text)
    if src.exists() and src.is_dir():
        return str((src.parent / f"{src.name}.safe").resolve())
    if src.suffix:
        return str(src.with_name(f"{src.stem}.safe{src.suffix}"))
    return str((src.parent / f"{src.name}.safe").resolve())


def _exit_code(results: list[FileResult], *, check: bool) -> int:
    if any(r.status == "error" for r in results):
        return 1
    if check and any(r.had_gps for r in results):
        return 1
    return 0


def execute(
    input_path: str,
    output_path: str,
    *,
    check: bool = False,
    report: bool = True,
) -> tuple[int, str]:
    """Run the same core path as the CLI. Returns (exit_code, report text)."""
    src = resolve_display_path(input_path)
    if not src:
        return 2, "share-safe: 请填写输入路径\n"
    dest = resolve_display_path(output_path) or None
    try:
        results = run(
            [src],
            output=dest,
            check=check,
            force=False,
            keep_model=False,
            recursive=False,
        )
    except UsageError as exc:
        return 2, f"share-safe: {exc}\n"
    text = print_summary(results, check=check) if report else ""
    return _exit_code(results, check=check), text


class GuiApp:
    def __init__(self) -> None:
        self.input_var: Any = None
        self.output_var: Any = None
        self.check_var: Any = None
        self.report_var: Any = None
        self.input_label: Any = None
        self.output_label: Any = None
        self.result: Any = None
        self._root: Any = None

    def resolve_fields(self) -> None:
        resolved_in = resolve_display_path(self.input_var.get())
        if resolved_in:
            self.input_var.set(resolved_in)
        resolved_out = resolve_display_path(self.output_var.get())
        if resolved_out:
            self.output_var.set(resolved_out)
        elif resolved_in:
            self.output_var.set(suggest_output_path(resolved_in))

    def _initial_dir(self, raw: str) -> str:
        text = resolve_display_path(raw)
        if not text:
            return str(Path.cwd())
        path = Path(text)
        if path.exists() and path.is_dir():
            return str(path)
        parent = path.parent
        return str(parent) if parent.exists() else str(Path.cwd())

    def _browse_input_file(self) -> None:
        from tkinter import filedialog

        chosen = filedialog.askopenfilename(
            parent=self._root,
            title="选择输入文件",
            initialdir=self._initial_dir(self.input_var.get()),
            filetypes=FILE_DIALOG_TYPES,
        )
        if chosen:
            self.input_var.set(resolve_display_path(chosen))
            if not str(self.output_var.get()).strip():
                self.output_var.set(suggest_output_path(chosen))

    def _browse_input_dir(self) -> None:
        from tkinter import filedialog

        chosen = filedialog.askdirectory(
            parent=self._root,
            title="选择输入目录",
            initialdir=self._initial_dir(self.input_var.get()),
            mustexist=True,
        )
        if chosen:
            self.input_var.set(resolve_display_path(chosen))
            if not str(self.output_var.get()).strip():
                self.output_var.set(suggest_output_path(chosen))

    def _browse_output_file(self) -> None:
        from tkinter import filedialog

        chosen = filedialog.asksaveasfilename(
            parent=self._root,
            title="选择输出文件",
            initialdir=self._initial_dir(self.output_var.get() or self.input_var.get()),
            filetypes=FILE_DIALOG_TYPES,
        )
        if chosen:
            self.output_var.set(resolve_display_path(chosen))

    def _browse_output_dir(self) -> None:
        from tkinter import filedialog

        chosen = filedialog.askdirectory(
            parent=self._root,
            title="选择输出目录",
            initialdir=self._initial_dir(self.output_var.get() or self.input_var.get()),
        )
        if chosen:
            self.output_var.set(resolve_display_path(chosen))

    def _run(self) -> None:
        self.resolve_fields()
        code, text = execute(
            input_path=self.input_var.get(),
            output_path=self.output_var.get(),
            check=bool(self.check_var.get()),
            report=bool(self.report_var.get()),
        )
        self.result.configure(state="normal")
        self.result.delete("1.0", "end")
        self.result.insert("1.0", f"退出码 {code}\n\n{text}")
        self.result.configure(state="normal")
        self.result.see("end")


def build_window(root: Any) -> GuiApp:
    import tkinter as tk
    from tkinter import ttk
    from tkinter.scrolledtext import ScrolledText

    app = GuiApp()
    app._root = root
    app.input_var = tk.StringVar()
    app.output_var = tk.StringVar()
    app.check_var = tk.BooleanVar(value=False)
    app.report_var = tk.BooleanVar(value=True)

    root.title("share-safe")
    root.minsize(640, 420)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    frame = ttk.Frame(root, padding=12)
    frame.grid(row=0, column=0, sticky="nsew")
    frame.columnconfigure(1, weight=1)

    app.input_label = ttk.Label(frame, text="输入路径")
    app.input_label.grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
    in_entry = ttk.Entry(frame, textvariable=app.input_var)
    in_entry.grid(row=0, column=1, sticky="ew", pady=4)
    in_entry.bind("<FocusOut>", lambda _e: app.resolve_fields())
    in_btns = ttk.Frame(frame)
    in_btns.grid(row=0, column=2, sticky="e", padx=(8, 0), pady=4)
    ttk.Button(in_btns, text="文件", command=app._browse_input_file).pack(side="left", padx=(0, 4))
    ttk.Button(in_btns, text="目录", command=app._browse_input_dir).pack(side="left")

    app.output_label = ttk.Label(frame, text="输出路径")
    app.output_label.grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
    out_entry = ttk.Entry(frame, textvariable=app.output_var)
    out_entry.grid(row=1, column=1, sticky="ew", pady=4)
    out_entry.bind("<FocusOut>", lambda _e: app.resolve_fields())
    out_btns = ttk.Frame(frame)
    out_btns.grid(row=1, column=2, sticky="e", padx=(8, 0), pady=4)
    ttk.Button(out_btns, text="文件", command=app._browse_output_file).pack(side="left", padx=(0, 4))
    ttk.Button(out_btns, text="目录", command=app._browse_output_dir).pack(side="left")

    opts = ttk.Frame(frame)
    opts.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 4))
    ttk.Checkbutton(
        opts,
        text="--check  只检查是否仍含 GPS，不写文件",
        variable=app.check_var,
    ).pack(anchor="w")
    ttk.Checkbutton(
        opts,
        text="--report  显示处理报告",
        variable=app.report_var,
    ).pack(anchor="w")

    ttk.Button(frame, text="运行", command=app._run).grid(
        row=3, column=0, columnspan=3, sticky="w", pady=(8, 8)
    )

    ttk.Label(frame, text="结果报告").grid(row=4, column=0, columnspan=3, sticky="w")
    app.result = ScrolledText(frame, height=16, wrap="word", font="TkFixedFont")
    app.result.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=(4, 0))
    frame.rowconfigure(5, weight=1)
    return app


def launch() -> int:
    try:
        import tkinter as tk
    except ImportError:
        print("share-safe: GUI requires tkinter", file=sys.stderr)
        return 2
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"share-safe: cannot open GUI ({exc})", file=sys.stderr)
        return 2
    build_window(root)
    root.mainloop()
    return 0
