"""Chart geography setup and independent live-map availability for the workspace.

Asset preparation uses the existing single renderer. The owning screen must call
``_handle_map_asset_result`` before its normal render-result handling and advance
``_project_generation`` whenever it replaces the current project.
"""
from dataclasses import replace
from tkinter import messagebox, ttk

from cycloneaid.geography import geography_readiness


WITHOUT_BASEMAP = (
    "Charts omit the basemap, city analysis, and automatic coastline events. "
    "Forecast inputs and manual landfall flags remain available."
)


class MapReadinessMixin:
    """Small UI adapter; no asset downloads or mode changes happen at startup."""

    def _init_map_readiness(self):
        self._map_asset_job_id = None
        self._map_asset_request_generation = None
        self._map_asset_enable_requested = False
        self._map_asset_error = ""
        self._chart_map_status = "Map setup needed"
        self._chart_map_detail = ""
        self._osm_map_state = "unknown"
        self._osm_map_detail = ""

    def _build_map_readiness(self, parent):
        frame = ttk.Frame(parent, padding=(8, 5))
        frame.columnconfigure(0, weight=1)
        self._map_readiness_frame = frame
        self._map_readiness_label = ttk.Label(frame, anchor="w")
        self._map_readiness_label.grid(row=0, column=0, sticky="ew")
        self._map_readiness_detail_label = ttk.Label(frame, anchor="w", wraplength=420)
        self._map_readiness_detail_label.grid(row=1, column=0, sticky="ew", pady=(2, 3))
        actions = ttk.Frame(frame)
        actions.grid(row=2, column=0, sticky="w")
        self._enable_maps_button = ttk.Button(actions, text="Enable maps", command=self.enable_maps)
        self._enable_maps_button.grid(row=0, column=0, padx=(0, 6))
        self._without_basemap_button = ttk.Button(
            actions, text="Continue without basemap", command=self.continue_without_basemap)
        self._without_basemap_button.grid(row=0, column=1)
        self._map_preparation_progress = ttk.Progressbar(frame, mode="indeterminate")
        self._map_preparation_progress.grid(row=3, column=0, sticky="ew", pady=3)
        self._osm_status_label = ttk.Label(frame, anchor="w", wraplength=420)
        self._osm_status_label.grid(row=4, column=0, sticky="ew", pady=(3, 0))
        self._osm_retry_button = ttk.Button(frame, text="Retry live map", command=self.retry_osm_map)
        self._osm_retry_button.grid(row=5, column=0, sticky="w", pady=(3, 0))

        def wrap(event):
            width = max(180, event.width - 20)
            self._map_readiness_detail_label.configure(wraplength=width)
            self._osm_status_label.configure(wraplength=width)

        frame.bind("<Configure>", wrap, add="+")
        self._refresh_map_readiness()
        self._refresh_osm_status()
        return frame

    def _refresh_map_readiness(self):
        """Read the cache only; never infer tile connectivity or fetch geography."""
        missing = geography_readiness()
        self._map_missing_assets = missing
        degraded = self.controller.session.settings.geography_mode == "degraded"
        preparing = self._map_asset_job_id is not None
        if degraded:
            status, detail = "Without basemap", WITHOUT_BASEMAP
        elif missing:
            status = "Map setup needed"
            detail = "Prepare map assets once while connected to use full charts offline."
        else:
            status = "Full maps ready"
            detail = "Chart geography is cached for offline previews and PNG exports."
        if preparing:
            detail += " Preparing map assets in the background…"
        elif self._map_asset_error:
            detail += f" Map setup failed: {self._map_asset_error} Retry when connected."
        self._chart_map_status, self._chart_map_detail = status, detail
        if not hasattr(self, "_map_readiness_label"):
            return
        self._map_readiness_label.configure(text=status)
        self._map_readiness_detail_label.configure(text=detail)
        show_enable = degraded or bool(missing)
        if show_enable:
            self._enable_maps_button.grid()
            label = ("Retry map setup" if self._map_asset_error else
                     "Enable maps" if degraded else "Prepare maps")
            self._enable_maps_button.configure(text=label, state="disabled" if self.renderer.busy else "normal")
        else:
            self._enable_maps_button.grid_remove()
        if not degraded and missing:
            self._without_basemap_button.grid()
        else:
            self._without_basemap_button.grid_remove()
        if preparing:
            self._map_preparation_progress.grid()
            self._map_preparation_progress.start(15)
        else:
            self._map_preparation_progress.stop()
            self._map_preparation_progress.grid_remove()

    def enable_maps(self):
        """Enable a warm cache immediately or prepare it for this project only."""
        if not geography_readiness():
            self._map_asset_error = ""
            self._commit(settings=replace(self.controller.session.settings, geography_mode="full"))
            self._refresh_map_readiness()
            self._set_status("Full maps enabled; refresh a chart to include the basemap")
            return
        if self.renderer.busy:
            self._set_status("Wait for the current render or map setup to finish, then retry")
            return
        missing = geography_readiness()
        if not messagebox.askyesno(
                "Prepare map assets",
                f"Download {len(missing)} missing Natural Earth datasets and enable full maps for this project?\n\n"
                "Full charts then work offline. OSM live-map tiles still need connectivity or cached coverage.",
                parent=self):
            return
        try:
            job_id = self.renderer.submit("assets")
        except Exception as exc:
            self._map_asset_error = str(exc)
            self._refresh_map_readiness()
            self._set_status(f"Map setup could not start: {exc}")
            return
        self._map_asset_job_id = job_id
        self._map_asset_request_generation = getattr(self, "_project_generation", 0)
        self._map_asset_enable_requested = True
        self._map_asset_error = ""
        self._set_buttons_loading(True, "Preparing map assets…")
        self._refresh_map_readiness()

    def prepare_assets(self):
        """Compatibility command used by the Project menu."""
        self.enable_maps()

    def continue_without_basemap(self):
        if not messagebox.askyesno("Continue without basemap", WITHOUT_BASEMAP + "\n\nContinue?", parent=self):
            return
        self._map_asset_enable_requested = False
        self._map_asset_error = ""
        self._commit(settings=replace(self.controller.session.settings, geography_mode="degraded"))
        self._refresh_map_readiness()
        self._set_status("Without basemap; city analysis and automatic coastline events are omitted")

    def _handle_map_asset_result(self, result):
        """Consume an asset result without changing a subsequently opened project."""
        if result.product != "assets":
            return False
        if self._map_asset_job_id is not None and result.job_id != self._map_asset_job_id:
            return True
        requested_generation = self._map_asset_request_generation
        enable_requested = self._map_asset_enable_requested
        self._map_asset_job_id = None
        self._map_asset_request_generation = None
        self._map_asset_enable_requested = False
        self._set_buttons_loading(False)
        error = result.error
        if not error and geography_readiness():
            error = "Some required datasets are still missing"
        self._map_asset_error = error
        if error:
            self._set_status(f"Map setup failed: {error}. Retry setup or continue without basemap.")
        elif enable_requested and requested_generation == getattr(self, "_project_generation", 0):
            self._commit(settings=replace(self.controller.session.settings, geography_mode="full"))
            self._set_status("Full maps ready; refresh a chart to include the basemap")
        else:
            self._set_status("Map assets cached; the current project's geography setting was kept")
        self._refresh_map_readiness()
        return True

    def _refresh_osm_status(self, state=None, detail=""):
        """Update only from live-map evidence, independently of Natural Earth."""
        if state is not None:
            self._osm_map_state, self._osm_map_detail = state, detail
        labels = {
            "unknown": "OSM live map: tiles need connectivity or cached coverage.",
            "loading": "OSM live map: loading tiles…",
            "ready": "OSM live map: tiles are available for the current view.",
            "unavailable": "OSM live map unavailable. Check connectivity, then retry.",
        }
        text = labels.get(self._osm_map_state, labels["unknown"])
        if self._osm_map_detail:
            text += " " + self._osm_map_detail
        if self._osm_map_state == "unknown":
            text += " Chart-map readiness does not verify tile access."
        self._osm_map_status = text
        if hasattr(self, "_osm_status_label"):
            self._osm_status_label.configure(text=text)
            if self._osm_map_state == "unavailable":
                self._osm_retry_button.grid()
            else:
                self._osm_retry_button.grid_remove()

    def retry_osm_map(self):
        retry = getattr(self, "_retry_live_map", None)
        if retry is None:
            self._refresh_osm_status("unavailable", "Live-map support is not installed; chart previews remain available.")
            return
        self._refresh_osm_status("loading")
        try:
            retry()
        except Exception as exc:
            self._refresh_osm_status("unavailable", str(exc))
