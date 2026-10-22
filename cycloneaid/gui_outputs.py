"""Embedded, on-demand chart views for the forecast workspace.

The session adapter owns rendering jobs. This module owns only their independent
Tk figure copies, so selecting a tab can never submit work to the renderer.
"""
import tkinter as tk
from tkinter import ttk


class _ChartPane(ttk.Frame):
    """Dispose a canvas's scheduled Tk work before releasing its widgets."""

    figure_canvas = None

    def __init__(self, parent, figure, closed):
        super().__init__(parent, style="Workspace.TFrame")
        self.figure = figure
        self._closed = closed
        self._disposed = False
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _cancel_canvas_jobs(self):
        canvas = self.figure_canvas
        if canvas is None:
            return
        for name in ("_idle_draw_id", "_event_loop_id"):
            identifier = getattr(canvas, name, None)
            if identifier is not None:
                try:
                    canvas.get_tk_widget().after_cancel(identifier)
                except tk.TclError:
                    pass
                setattr(canvas, name, None)

    def _dispose(self):
        if self._disposed:
            return
        self._disposed = True
        self._cancel_canvas_jobs()
        import matplotlib.pyplot as plt
        plt.close(self.figure)
        self._closed(self)

    def _on_destroy(self, event):
        # An ancestor's Tk destruction does not call child Python destroy().
        if event.widget is self:
            self._dispose()

    def destroy(self):
        self._dispose()
        super().destroy()


class OutputTabsMixin:
    """Build output tabs and present completed figures without extra workers."""

    _CHART_TABS = (("track", "Track"), ("prognostic", "Intensity"), ("ri", "Wind change"))

    def _build_output_tabs(self, parent):
        self.output_notebook = ttk.Notebook(parent, style="Workspace.TNotebook")
        self.output_notebook.pack(fill=tk.BOTH, expand=True)
        self.map_frame = ttk.Frame(self.output_notebook, style="Workspace.TFrame")
        self.output_notebook.add(self.map_frame, text="Map")
        self._output_pages = {}
        self._output_hosts = {}
        self._output_states = {}
        self._output_state_kind = {}
        self._output_empty_labels = {}
        self._output_buttons = {}
        self._action_btns = []
        for product, label in self._CHART_TABS:
            page = ttk.Frame(self.output_notebook, style="Workspace.TFrame")
            self.output_notebook.add(page, text=label)
            self._output_pages[product] = page
            controls = ttk.Frame(page, style="Workspace.TFrame")
            controls.pack(fill=tk.X, padx=8, pady=(8, 4))
            preview = ttk.Button(controls, text="Preview", style="Accent.TButton",
                                 command=lambda p=product: self._start_plot(p))
            preview.pack(side=tk.LEFT)
            export = ttk.Button(controls, text="Export PNG…", style="Workspace.TButton",
                                command=lambda p=product: self._start_plot(p, True))
            export.pack(side=tk.LEFT, padx=(6, 0))
            self._output_buttons[product] = preview, export
            self._action_btns.extend((preview, export))
            state = tk.StringVar(master=self, value="No preview yet")
            self._output_states[product] = state
            self._output_state_kind[product] = "empty"
            status = ttk.Label(page, textvariable=state, style="Muted.TLabel", anchor=tk.W)
            status.pack(fill=tk.X, padx=8, pady=(0, 6))
            # Keep long failure messages readable when the divider is moved.
            status.bind("<Configure>", lambda event, widget=status:
                        widget.configure(wraplength=max(120, event.width)))
            host = ttk.Frame(page, style="Workspace.TFrame")
            host.pack(fill=tk.BOTH, expand=True)
            self._output_hosts[product] = host
            empty = ttk.Label(host, text="Complete the forecast, then choose Preview.\n"
                              "Charts update only when requested.",
                              justify=tk.CENTER, anchor=tk.CENTER, style="Muted.TLabel")
            empty.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
            self._output_empty_labels[product] = empty
        # No tab-change binding: navigation is independent of rendering.
        self.output_notebook.select(self.map_frame)
        return self.map_frame

    def _set_output_state(self, product, kind, message):
        if product not in getattr(self, "_output_states", {}):
            return
        self._output_state_kind[product] = kind
        self._output_states[product].set(message)

    def _mark_outputs_stale(self):
        revision = self.controller.session.revision
        for product, (_, _, preview_revision) in getattr(self, "_previews", {}).items():
            if preview_revision != revision:
                self._set_output_state(product, "stale", "Previous session state — refresh to include edits")

    def _clear_outputs(self):
        """Release charts when replacing a project, without submitting a job."""
        for _, pane, _ in list(getattr(self, "_previews", {}).values()):
            pane.destroy()
        self._previews.clear()
        for product, label in getattr(self, "_output_empty_labels", {}).items():
            if label.winfo_exists():
                label.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
            self._output_buttons[product][0].configure(text="Preview")
            self._set_output_state(product, "empty", "No preview yet")

    def _output_render_started(self, product, save=False):
        self._set_output_state(product, "rendering", "Exporting PNG…" if save else "Rendering preview…")

    def _output_render_finished(self, product, *, error="", exported=False, obsolete=False):
        if error:
            previous = product in getattr(self, "_previews", {})
            message = "Previous preview remains available. " if previous else ""
            self._set_output_state(product, "failed", f"Failed. {message}{error}")
        elif obsolete:
            previous = product in getattr(self, "_previews", {})
            self._set_output_state(product, "stale" if previous else "empty",
                                   "Forecast changed during rendering — choose Preview again")
        elif exported:
            previous = getattr(self, "_previews", {}).get(product)
            if previous and previous[2] == self.controller.session.revision:
                self._set_output_state(product, "current", "Current preview · PNG exported")
            elif previous:
                self._set_output_state(product, "stale", "PNG exported · preview shows a previous session state")
            else:
                self._set_output_state(product, "empty", "PNG exported · choose Preview to display the chart")

    def _show_preview(self, figure, product, revision):
        """Initialize fully, then replace the prior pane as one UI operation."""
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        pane = None
        previous_focus = self.focus_get()
        try:
            host = self._output_hosts[product]

            def closed(closed_pane):
                current = self._previews.get(product)
                if current and current[1] is closed_pane:
                    self._previews.pop(product, None)
                    if not getattr(self, "_closing", False):
                        label = self._output_empty_labels[product]
                        if label.winfo_exists():
                            label.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
                            self._set_output_state(product, "empty", "No preview yet")

            pane = _ChartPane(host, figure, closed)
            original_inches = tuple(figure.get_size_inches())
            original_dpi = figure.dpi
            canvas = FigureCanvasTkAgg(figure, master=pane)
            pane.figure_canvas = canvas
            canvas._preview_original_inches = original_inches
            default_resize = canvas.resize

            def fit_preview(event):
                if event.width <= 1 or event.height <= 1:
                    return
                # Scale text and legends with the complete source graphic.
                # The worker's export figure is a separate, full-resolution copy.
                scale_dpi = min(event.width/original_inches[0], event.height/original_inches[1])
                figure.set_dpi(min(original_dpi, scale_dpi))
                default_resize(event)

            widget = canvas.get_tk_widget()
            widget.bind("<Configure>", fit_preview)
            # Project shortcuts belong to the workspace, not Matplotlib's PNG
            # save/navigation keymap. Allow them to reach the toplevel binding.
            for sequence in ('<Control-s>', '<Control-o>', '<Control-n>', '<Control-z>', '<Control-y>'):
                widget.bind(sequence, lambda event: None)
            widget.configure(width=1, height=1)
            screen = self

            class Toolbar(NavigationToolbar2Tk):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self._theme_binding = self._root().bind(
                        "<<CycloneAidThemeChanged>>", self._refresh_theme, add="+")
                    self.bind("<Destroy>", self._release_theme_binding, add="+")
                    self._refresh_theme()

                def _refresh_theme(self, event=None):
                    from cycloneaid.ui_theme import style_widget_tree
                    style_widget_tree(self)
                    # Matplotlib chooses light/dark icons from Tk button colors.
                    for button in self._buttons.values():
                        self._set_image_for_button(button)

                def _release_theme_binding(self, event):
                    if event.widget is self:
                        self._root().unbind("<<CycloneAidThemeChanged>>", self._theme_binding)

                def save_figure(self, *args):
                    screen._start_plot(product, True)

            toolbar = Toolbar(canvas, pane, pack_toolbar=False)
            pane.toolbar = toolbar
            toolbar.pack(side=tk.BOTTOM, fill=tk.X)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            # Rendering errors belong to the replacement; retain the old pane.
            canvas.draw()
            if previous_focus is not None and previous_focus.winfo_exists():
                previous_focus.focus_set()
        except Exception as exc:
            if pane is not None:
                pane.destroy()
            else:
                plt.close(figure)
            if previous_focus is not None and previous_focus.winfo_exists():
                previous_focus.focus_set()
            self._output_render_finished(product, error=str(exc))
            raise

        previous = self._previews.get(product)
        self._previews[product] = (figure, pane, revision)
        self._output_empty_labels[product].pack_forget()
        pane.pack(fill=tk.BOTH, expand=True)
        if previous:
            previous[1].destroy()
        self._output_buttons[product][0].configure(text="Refresh")
        if revision == self.controller.session.revision:
            self._set_output_state(product, "current", "Current preview · fitted to pane")
        else:
            self._set_output_state(product, "stale", "Previous session state — refresh to include edits")
