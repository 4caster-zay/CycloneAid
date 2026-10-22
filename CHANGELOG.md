# Changelog

## 0.11.0a1 — 2026-10-22 (workspace alpha)

- Open directly into a forecast workspace with project actions, editable session properties, grouped row/import controls, and embedded Map/Track/Intensity/Wind change tabs.
- Add semantic Sky/Typhoon styling, a keyboard-accessible appearance switch, persistent local preferences, consistent hover/focus/disabled states, and themed dialogs/toolbars.
- Keep blank storm-name drafts editable, commit names as one undoable action, include pending edits in save/recovery, and display Untitled storm only in unnamed chart titles.
- Show explicit chart-map readiness, one-time background setup, retries, and independent OSM availability; preserve stored project modes and later operator choices.
- Fit complete preview graphics to the pane, preserve focus during render completion, and protect new projects from previous jobs' results. Retain full-resolution snapshot exports and figure/callback cleanup.
- Add keyboard cell navigation, project-safe history reset, responsive pane sizing, and a packaged sample available in installed builds.

## 0.10.0a2 — 2026-10-22 (alpha testing release)

- Generate timestamp-only forecast rows from an explicit UTC start, interval, and horizon; preview before appending as one undoable action, preserving generated timestamp provenance without labeling forecast values interpolated.
- Keep new sessions empty so operators can generate their first rows directly. Generated coordinates and winds remain blank until entered and validated.
- Preserve fractional seconds in table display and timestamp editing, including closely spaced generated rows.
- Establish a linked roadmap, contribution guide, issue/PR templates, grouped monthly dependency updates, and required cross-platform CI checks on main.
- Archive the original review with a current reconciliation and move diagnostic benchmarks under documentation.
- Include examples, launchers, locked dependencies, release tools, and linked documentation in source distributions.
- Fix CI's missing Tk runtime, explicitly select Python 3.12, and keep platform checks running independently.
- Preserve an existing preview if replacement initialization fails; release failed figures and cancel pending embedded-canvas callbacks before closing.
- Record worker and Tk callback tracebacks in rotating local logs and identify the log path in preview error dialogs.
- Prevent duplicate recovery-autosave callbacks when an autosave is triggered manually.
- Exercise repeated sample preview replacement, resizing, and closure in degraded and cached full geography.

## 0.10.0a1 — 2026-10-21 (alpha testing release)

- Introduce immutable forecast/session models, common validation, explicit intensity overrides, and timestamp provenance.
- Stage CSV, GPX, KML, and KMZ imports before replacing data; preserve UTC and track boundaries.
- Add atomic project save/load, recovery autosaves, and undo/redo.
- Correct exact-window RI calculations and geodesic legacy heuristic envelopes; detect approximate coastline crossings.
- Isolate rendering and exports in one process, reject obsolete previews, and manage figure lifetime.
- Use indexed city searches and incremental table/map updates.
- Add package metadata, reproducible dependencies, automated regression tests, and cross-platform CI.
- Add persistent local setup, launchers, dependency diagnostics, and automatic source-checkout environment selection.
- Replace the bundled forecast with the labeled TEST PALAU 120-hour synthetic scenario and matching project metadata.
- Fix Home-screen callback cleanup and improve forecast callouts, multiple coastline-crossing labels, and RI annotation placement.
- Support native Linux and small-delta Home scrolling; correct Home content alignment. Reject stale map tiles, create tile images on the Tk thread, bound downloads/caches, and normalize map-wheel zoom.

## Historical versions

The source previously declared Alpha 0.9.3 while the README and latest Git tag declared 0.9.1. Existing tags are preserved. Historical GUI release notes remain available in the application.
