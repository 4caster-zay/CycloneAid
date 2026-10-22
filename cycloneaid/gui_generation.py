"""Small modal dialog for previewing and appending forecast timestamps."""
import tkinter as tk
from tkinter import ttk

from cycloneaid.generation import MAX_GENERATED_ROWS, generate_rows, preview_generation, suggest_start_time


class GenerateRowsDialog(tk.Toplevel):
    def __init__(self, screen):
        super().__init__(screen)
        self.screen = screen
        self.title("Generate forecast rows")
        self.resizable(False, False)
        self.transient(screen.winfo_toplevel())
        self.start_var = tk.StringVar(self, "")
        self.interval_var = tk.StringVar(self, "6")
        self.horizon_var = tk.StringVar(self, "120")
        self.preview_var = tk.StringVar(self, "")
        self.error_var = tk.StringVar(self, "")
        self._writing_start = False
        self._start_is_suggested = bool(screen.controller.session.rows)
        self._preview = None
        for index, (label, variable) in enumerate((("Start (UTC)", self.start_var),
                                                  ("Interval (hours)", self.interval_var),
                                                  ("Horizon (hours)", self.horizon_var))):
            ttk.Label(self, text=label).grid(row=index, column=0, padx=12, pady=6, sticky="w")
            entry = ttk.Entry(self, textvariable=variable, width=34)
            entry.grid(row=index, column=1, padx=12, pady=6)
            if index == 0:
                self.start_entry = entry
        ttk.Label(self, text="YYYY-MM-DD HH:MM[:SS]; times are UTC.").grid(
            row=3, column=0, columnspan=2, padx=12, sticky="w")
        ttk.Label(self, text=f"Timestamps only; both endpoints included. Up to {MAX_GENERATED_ROWS:,} rows per batch.").grid(
            row=4, column=0, columnspan=2, padx=12, pady=6, sticky="w")
        ttk.Label(self, textvariable=self.preview_var, justify="left").grid(
            row=5, column=0, columnspan=2, padx=12, pady=6, sticky="w")
        ttk.Label(self, textvariable=self.error_var, foreground="#b00020", wraplength=420).grid(
            row=6, column=0, columnspan=2, padx=12, sticky="w")
        buttons = ttk.Frame(self)
        buttons.grid(row=7, column=0, columnspan=2, padx=12, pady=12, sticky="e")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=6)
        self.apply_button = ttk.Button(buttons, text="Append rows", command=self._apply)
        self.apply_button.pack(side=tk.LEFT)
        self.start_var.trace_add("write", self._start_changed)
        self.interval_var.trace_add("write", self._interval_changed)
        self.horizon_var.trace_add("write", self._update_preview)
        self._interval_changed()
        self.bind("<Escape>", lambda event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set()
        self.start_entry.focus_set()

    def _start_changed(self, *_):
        if not self._writing_start:
            self._start_is_suggested = False
        self._update_preview()

    def _interval_changed(self, *_):
        if self._start_is_suggested:
            try:
                suggested = suggest_start_time(self.screen.controller.session.rows, self.interval_var.get())
            except ValueError:
                suggested = None
            self._writing_start = True
            try:
                self.start_var.set(suggested.isoformat() if suggested is not None else "")
            finally:
                self._writing_start = False
        self._update_preview()

    def _update_preview(self, *_):
        self._preview = None
        try:
            preview = preview_generation(self.start_var.get(), self.interval_var.get(), self.horizon_var.get(),
                                         existing_rows=self.screen.controller.session.rows)
        except ValueError as exc:
            self.preview_var.set("")
            self.error_var.set(str(exc))
            self.apply_button.config(state=tk.DISABLED)
            return
        self._preview = preview
        self.preview_var.set(f"First UTC: {preview.start.isoformat()}\nLast UTC: {preview.end.isoformat()}\nRows to append: {preview.count}")
        self.error_var.set("")
        self.apply_button.config(state=tk.NORMAL)

    def _apply(self):
        # Revalidate against the current session before the single history commit.
        self._update_preview()
        if self._preview is None:
            return
        rows = self.screen.controller.session.rows
        generated = generate_rows(self.start_var.get(), self.interval_var.get(), self.horizon_var.get(),
                                  existing_rows=rows)
        self.screen._commit(rows=(*rows, *generated), infer_issue_time=False)
        self.destroy()
