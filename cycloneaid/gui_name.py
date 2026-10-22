"""Draft storm-name editing without per-keystroke history or cursor rewrites."""
from dataclasses import replace
import tkinter as tk

from cycloneaid.metadata import display_storm_name as display_storm_name
from cycloneaid.ui_theme import register_widget


class NameEditingMixin:
    def _init_name_editing(self):
        self._name_pending = False
        self._name_syncing = False
        self._name_entry = None
        self._name_trace = None
        self._name_placeholder = None

    def _bind_name_entry(self, entry):
        """Bind an Entry whose textvariable is ``storm_name_var`` once constructed."""
        self._name_entry = entry
        self._name_trace = self.storm_name_var.trace_add("write", self._name_text_changed)
        self._name_placeholder = register_widget(tk.Label(entry, text="Storm name", anchor="w",
                                                         cursor="xterm", padx=0, pady=0), "placeholder")
        self._name_placeholder.bind("<Button-1>", lambda event: entry.focus_set())
        entry.bind("<Return>", self._name_enter, add="+")
        entry.bind("<FocusOut>", self._name_focus_out, add="+")
        entry.bind("<FocusIn>", self._update_name_placeholder, add="+")
        entry.bind("<Destroy>", self._name_entry_destroyed, add="+")
        self._update_name_placeholder()

    def _name_text_changed(self, *_):
        if not self._name_syncing:
            self._name_pending = self.storm_name_var.get() != self.controller.session.settings.storm_name
            self._update_name_placeholder()
            self._notify_name_status()

    def _notify_name_status(self):
        callback = getattr(self, "_update_project_status", None)
        if callback:
            callback()

    def _has_pending_name_edit(self):
        return bool(getattr(self, "_name_pending", False))

    def _name_enter(self, event=None):
        self._flush_name_edit()
        return "break"

    def _name_focus_out(self, event=None):
        if self._name_entry is not None and self._name_entry.focus_get() is self._name_entry:
            return
        self._flush_name_edit()
        self._update_name_placeholder()

    def _flush_name_edit(self):
        """Commit the draft as one normal session change, preserving a blank name."""
        if not self._has_pending_name_edit():
            return False
        text = self.storm_name_var.get()
        self._name_pending = False
        if text == self.controller.session.settings.storm_name:
            self._notify_name_status()
            return False
        self._commit(settings=replace(self.controller.session.settings, storm_name=text), infer_issue_time=False)
        self._notify_name_status()
        return True

    def _sync_name_from_session(self, force=False):
        """Ordinary row/settings changes must leave an in-progress name untouched."""
        if self._has_pending_name_edit() and not force:
            return
        text = self.controller.session.settings.storm_name
        self._name_syncing = True
        try:
            if self.storm_name_var.get() != text:
                self.storm_name_var.set(text)
            self._name_pending = False
        finally:
            self._name_syncing = False
        self._update_name_placeholder()

    def _update_name_placeholder(self, event=None):
        placeholder = getattr(self, "_name_placeholder", None)
        entry = getattr(self, "_name_entry", None)
        if placeholder is None or entry is None:
            return
        try:
            if not self.storm_name_var.get() and entry.focus_get() is not entry:
                placeholder.place(x=6, rely=.5, anchor="w")
            else:
                placeholder.place_forget()
        except tk.TclError:
            pass  # Widget destruction can coincide with a queued focus event.

    def _name_entry_destroyed(self, event):
        if event.widget is self._name_entry and self._name_trace:
            self.storm_name_var.trace_remove("write", self._name_trace)
            self._name_trace = None
