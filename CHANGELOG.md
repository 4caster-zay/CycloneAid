# Changelog

## 0.11.0a1 — 2026-10-22 (workspace alpha)

- Replaced the opening screen with a forecast workspace containing project controls, session properties, grouped row and import actions, and embedded Map, Track, Intensity, and Wind change tabs.
- Added a keyboard-accessible Sky/Typhoon switch, saved local appearance preferences, and consistent control and dialog styling for hover, focus, pressed, and disabled states.
- Allowed blank storm names, grouped name edits into one undoable action, and included pending edits in saves and recovery. Unnamed charts display “Untitled storm” while saved project names remain blank.
- Added chart-map readiness indicators, background setup, retries, and separate OSM tile status. Existing project modes and explicit map choices are preserved.
- Fitted previews to the output pane and preserved editing focus when rendering finished. Results from an earlier project cannot replace the current project's previews. Exports retain full resolution, and replaced figures and canvas callbacks are cleaned up.
- Added keyboard cell navigation, reset undo history when changing projects, improved pane resizing, and bundled the sample project in installed builds.

## 0.10.0a2 — 2026-10-22 (alpha testing release)

- Added timestamp-only row generation from a UTC start, interval, and horizon, with a preview and one-step undo. Generated timestamps retain their provenance; forecast values are not marked as interpolated.
- Started new sessions with an empty table. Generated coordinates and winds remain blank until entered and validated.
- Preserved fractional seconds when displaying and editing timestamps, including closely spaced generated rows.
- Added a linked roadmap, contribution guide, issue and PR templates, grouped monthly dependency updates, and required cross-platform CI checks on `main`.
- Archived the original project review with a reconciliation against the current code, and moved diagnostic benchmarks into the documentation.
- Included examples, launchers, locked dependencies, release tools, and linked documentation in source distributions.
- Fixed the missing Tk runtime in CI, selected Python 3.12 explicitly, and allowed platform checks to run independently.
- Preserved existing previews when replacement initialization failed, released failed figures, and canceled pending canvas callbacks before closing.
- Recorded worker and Tk callback tracebacks in rotating local logs and included the log path in preview error dialogs.
- Prevented duplicate recovery-autosave callbacks after a manual autosave.
- Verified repeated sample preview replacement, resizing, and closure in both degraded and cached full-geography modes.

## 0.10.0a1 — 2026-10-21 (alpha testing release)

- Added immutable forecast and session models, shared validation, explicit intensity overrides, and timestamp provenance.
- Staged CSV, GPX, KML, and KMZ imports before replacing data, preserving UTC timestamps and track boundaries.
- Added atomic project saves and loads, recovery autosaves, and undo/redo.
- Corrected exact-window RI calculations and geodesic legacy heuristic envelopes, and added approximate coastline-crossing detection.
- Moved rendering and exports into one process, rejected obsolete previews, and managed figure cleanup.
- Added indexed city searches and incremental table and map updates.
- Added package metadata, reproducible dependencies, regression tests, and cross-platform CI.
- Added persistent local setup, launchers, dependency diagnostics, and automatic environment selection for source checkouts.
- Replaced the bundled forecast with the labeled TEST PALAU 120-hour synthetic scenario and matching project metadata.
- Fixed home-screen callback cleanup and improved forecast callouts, coastline-crossing labels, and RI annotation placement.
- Added native Linux and small-delta scrolling on the home screen and corrected its content alignment. Rejected stale map tiles, created tile images on the Tk thread, bounded downloads and caches, and normalized map-wheel zoom.

## Historical versions

The source previously declared Alpha 0.9.3 while the README and latest Git tag declared 0.9.1. Existing tags are preserved. Historical release notes are available under Help in the application.
