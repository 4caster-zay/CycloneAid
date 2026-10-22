# Forecast workspace

CycloneAid opens directly into the forecast editor. The header holds New, Open, Save, Project, Help, and the Sky/Typhoon switch. Project status distinguishes a project that has never been saved from saved work and unsaved changes. Storm name, confidence, preset, and Session details sit below it.

## Edit and save

Use Add or Generate rows above the table; Rows contains insertion, duplication, movement, and deletion. Import / Export contains CSV, GPX, and KML/KMZ interchange. Project files preserve the complete session, including incomplete drafts and provenance.

Double-click or press Enter to edit a cell. Tab commits and moves forward; Shift+Tab moves backward; Escape cancels. Storm-name edits remain local until Enter or focus loss and become one undoable change. Save, preview, export, and navigation capture pending edits. Recovery also includes a pending name without breaking the edit into multiple undo steps.

An empty name stays empty in the saved project. Charts display **Untitled storm** as a title fallback. New/Open replaces project history, and old render results cannot populate the replacement project.

## Maps and readiness

The area above the output tabs shows **Full maps ready**, **Map setup needed**, or **Without basemap**. New sessions request full maps. Existing projects retain their saved choice; the synthetic sample deliberately starts without a basemap.

Choose **Enable maps** to use cached Natural Earth assets immediately. If assets are missing, confirm one-time background setup; progress and retry remain visible. Chart requests with missing assets explain how to prepare maps rather than starting an unexpected download. A download finishing after you open another project will not change that project's settings. A later choice to continue without a basemap is respected.

**Continue without basemap** is explicit: it omits the chart basemap, city analysis, and automatic coastline events. Inputs and manual landfall flags remain available. This mode does not change forecast values.

OSM tile guidance and Retry live map live inside the Map tab. Their status comes from visible tile loading and failures, independently of Natural Earth readiness. Retry preserves the viewport and successful in-memory tiles. Missing live-map support does not prevent chart-map previews.

## Preview and export

The right side has Map, Track, Intensity, and Wind change tabs. Selecting a chart does not render it. Choose Preview or Refresh; chart status distinguishes no preview, rendering, current, stale, and failed results. Editing remains available during rendering, and completion preserves keyboard focus.

Figures fit the available pane, scaling titles and legends rather than cropping them. Drag the divider to enlarge an output; your chosen split is retained across window resizes. Matplotlib's toolbar supplies navigation, and its save action uses the same snapshot export path as Export PNG.

Export PNG works without a preview. When a matching current preview exists, its viewport is retained. Exports use the separate worker's full-resolution figure; scaling the embedded preview does not lower PNG resolution. A failed replacement retains the previous figure. Canvas callbacks, progress animations, and figures are cleaned up on replacement and shutdown.

## Appearance and screen sizes

Sky and Typhoon are selected states, rather than buttons naming the opposite mode. The switch supports keyboard navigation, and the application remembers appearance locally outside project files. Menus, fields, tabs, disabled controls, dialogs, and chart-toolbar icons share the theme. Chart presentation presets remain independent of application appearance.

The workspace targets 1920×1080. Properties and toolbar actions wrap as space decreases, and the existing 1000×650 minimum remains supported. The release verification includes screenshots of both themes at 1920×1080, 1366×768, and 1000×650; native Windows/macOS and tester-network evidence remain separately tracked.
