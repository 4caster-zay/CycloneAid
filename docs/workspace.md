# Forecast workspace

CycloneAid opens directly into the forecast editor. New, Open, Save, Project, Help, and the Sky/Typhoon switch are in the header. The project status shows whether the project is new, saved, or has unsaved changes. Storm name, confidence, preset, and Session details appear in the row below.

## Edit and save

Use **Add** or **Generate rows** above the table. The **Rows** menu lets you insert, duplicate, move, and delete rows. Use **Import / Export** for CSV, GPX, and KML/KMZ files. Save a project file to retain the complete session, including incomplete drafts and data provenance.

Double-click a cell or select it and press Enter to edit. Tab saves the edit and moves forward; Shift+Tab moves backward; Escape cancels. Press Enter or leave the storm-name field to save a name edit as one undoable change. Saving, previewing, exporting, or opening another project also saves pending edits. Recovery includes a name you are still typing.

You can leave the storm name blank. It stays blank in the project file, and charts use **Untitled storm** as their title. Creating or opening a project starts a new undo history. A render still finishing for the previous project cannot replace the new project's previews.

## Maps and readiness

The area above the output tabs shows **Full maps ready**, **Map setup needed**, or **Without basemap**. New projects use full maps. Existing projects retain their saved choice; the synthetic sample starts without a basemap so it can be opened before map setup.

Choose **Enable maps** to use cached Natural Earth assets. If assets are missing, you can start a one-time download in the background and follow its progress. A failed download can be retried. Previewing a chart with missing assets shows setup instructions. Downloads only enable maps for the project that requested them, and choosing to continue without a basemap cancels that pending change.

**Continue without basemap** omits the chart basemap, city analysis, and automatic coastline events. You can still edit forecast values and set manual landfall flags. The choice does not change forecast values.

The **Map** tab shows OpenStreetMap tile status and a **Retry live map** action. Tile availability is checked separately from the Natural Earth assets used by charts. Retry preserves the current view and already loaded tiles. You can still preview chart maps if the live map is unavailable.

## Preview and export

The right side has **Map**, **Track**, **Intensity**, and **Wind change** tabs. Select a chart tab, then choose **Preview** or **Refresh** to render it. The status tells you whether a preview is empty, rendering, current, stale, or failed. You can keep editing during rendering. Edits mark an existing preview stale while leaving it visible for reference.

Charts, titles, and legends scale to fit the output area. Drag the divider to give the editor or output more room; the split is retained when you resize the window. Use the Matplotlib toolbar to pan and zoom. Its save action works like **Export PNG**.

**Export PNG** works without first creating a preview. If the current preview matches the forecast and settings, the export retains its view. PNGs use the full-resolution chart regardless of the preview's size. If refreshing a chart fails, the previous preview remains available. Chart resources are released when a preview is replaced or the workspace closes.

## Appearance and screen sizes

Choose **Sky** for the light theme or **Typhoon** for the dark theme. The selected option shows the active theme, and the switch supports keyboard navigation. CycloneAid remembers your choice locally, separately from project files. Menus, fields, tabs, disabled controls, dialogs, and chart-toolbar icons follow the theme. Chart export presets are independent of the application theme.

The workspace is designed for 1920×1080 desktops and supports windows down to 1000×650. Properties and toolbar actions wrap at smaller sizes. Release verification includes screenshots of both themes at 1920×1080, 1366×768, and 1000×650. Native Windows/macOS checks and target-network testing remain separately tracked in the [release checklist](../RELEASE_CHECKLIST.md).
