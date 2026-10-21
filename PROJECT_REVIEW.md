# CycloneAid project review

Reviewed 21 October 2026 against commit `592ca1f` on `main`. This review covers all six Python modules, the sample data, dependency declarations, README, and tracked repository structure. Application source has not been changed.

## What the project does

CycloneAid is a Python desktop tool for preparing cyclone forecast graphics and inspecting a supplied forecast. Its core value is replacing manually drawn track graphics with repeatable, data-driven output. The home-screen origin story describes that specific need.

The operator enters or imports forecast times, coordinates, wind speeds, storm structure, intensity classifications, and landfall flags. A Tkinter table and an OpenStreetMap tile panel support editing. The application produces three products:

1. A geographic forecast track with a heuristic uncertainty envelope, intensity markers, cities, and landfall annotations.
2. A wind-intensity timeline with category bands and an event table.
3. A wind-change-rate chart that highlights an RI threshold.

CSV supports import and export. GPX and KML are import paths. KMZ appears in the file picker but is not actually decoded as a ZIP archive. The code does not implement GPX/KML export despite the README's broader wording. It also does not calculate pressure changes, run a forecast model, assimilate observations, retrieve live storm advisories, or predict wind speed. “Live” describes map interaction rather than a live meteorological feed.

The primary map renderer is explicitly restricted to 100–150°E and 0–40°N, with Philippine province overlays. Its practical geographic scope is narrower than the README's general hurricane-and-typhoon positioning.

| Module | Responsibility | Architectural observation |
|---|---|---|
| `storm_tracker_gui.py` | Tkinter screens, table editing, import/export, map synchronization, rendering jobs | About 1,773 lines; combines UI, data conversion, validation orchestration, and job state. |
| `storm_tracker.py` | ForecastPoint model, GPX parsing, geography caches, city lookup, cone construction, track plotting | The domain model is coupled to the heaviest plotting dependencies. |
| `storm_prognostic.py` | Intensity timeline and event table | Reuses shared city data but bypasses the spatial index through its call signature. |
| `storm_RI_plot.py` | Wind-unit conversion, windowed wind-change calculation, RI plotting | Calculation is partly separable, but importing it also imports the GUI. |
| `validation.py` | Hard-error and soft-warning checks | Useful abstraction; core checks are much weaker than the GUI's row checks. |
| `export_preset.py` | Forecaster/Media presentation rules and RenderContext | A sound separation between presentation policy and forecast data; applied primarily to the track renderer. |

## SWOT

| Strengths | Weaknesses |
|---|---|
| Solves a concrete forecaster workflow: enter a forecast once and generate several related graphics. | Confirmed failures exist in RI plotting, modern-pandas imports, asynchronous error reporting, and CLI schema compatibility. |
| Supports distinct storm structure and intensity fields, including legacy category conversion. | Forecast data lives in Treeview cells; parsing and business rules are duplicated across UI, model, importers, and renderers. |
| RenderContext and export presets establish a useful presentation boundary. | A large GUI module and circular/dynamic imports make maintenance and isolated testing harder. |
| Geography caches and an R-tree already exist; performance improvements can build on them. | Main city-processing paths do not consistently use the index, and renderers write files as a side effect. |
| Validation results distinguish blocking errors from advisory warnings; generated timestamps have a provenance flag. | Scientific assumptions, timestamp provenance, coordinate conventions, and invalid-input handling are not consistently enforced. |
| Standard scientific/geospatial libraries and an MIT license support extension. | No tracked automated tests, CI workflow, package configuration, or dependency lockfile were found. |

| Opportunities | Threats |
|---|---|
| Establish one validated forecast/session model shared by every interface and output. | Polished graphics may communicate more scientific confidence than the heuristic cone and approximate landfall logic support. |
| Separate figure construction, interactive preview, and final export. | Broad dependency lower bounds allow upgrades that already break existing code paths. |
| Connect the existing city index to actual callers, then optimize map updates and validation. | Basemap assets and OSM tiles add network/cache dependencies; no application-level offline readiness check or recovery workflow is present. |
| Add explicit source agency, wind averaging period, issue time, basin, and configurable cone methodology. | Stale exports and destructive imports can undermine user trust even when graphics look correct. |
| Add project save/load, recovery, undo, and adapters for authoritative forecast inputs. | Continued feature additions to the monolithic GUI increase regression risk without tests. |
| Expand geography deliberately with geodesic geometry and basin-aware settings. | Applying regional clipping or mixed input conventions to other basins can produce invalid or misleading output. |

## Correctness and reliability findings

### 1. RI has two independent execution failures — high priority

**Reproduced.** At [storm_RI_plot.py:188](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_RI_plot.py:188), the plotting function uses `timezone.utc`, but `timezone` is imported only inside the script's `__main__` block. Calling the plotting function as a library, as the GUI does, raises `NameError` after reaching that footer.

**Reproduced with pandas 3.0.6.** At [storm_RI_plot.py:70](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_RI_plot.py:70), the calculation treats integer datetime values as nanoseconds unconditionally. A normal `datetime64[us, UTC]` input with valid 24-hour intervals returned zero RI rows. Converting that same input explicitly to nanosecond resolution produced the expected two results. Handle datetime units explicitly or compare timedeltas directly.

### 2. Imports are incompatible with an allowed dependency version — high priority

**Reproduced.** [storm_tracker.py:211](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker.py:211) uses `.floor('H')`. pandas 3.0.6 rejects that frequency alias and suggests lowercase `h`. The line executes for GPX imports even when input timestamps exist. KML import contains the same expression at [storm_tracker_gui.py:1379](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker_gui.py:1379).

`requirements.txt` allows pandas 3 because it specifies only `pandas>=1.5.0`. A supported-version policy and a reproducible environment are needed alongside the code fixes.

### 3. Core validation permits invalid forecasts — high priority

**Reproduced.** [validation.py:80](/home/zaypc/Documents/Personal/Projects/CycloneAid/validation.py:80) checks mainly for `None` and empty strings. The shared validator accepted:

- A single point with latitude 100°, longitude 500°, and wind −5 kt.
- A point with a NaN latitude.
- A point with a `NaT` timestamp.
- A 10-kt point explicitly classified as C5.

A missing timestamp in a two-point forecast caused an exception instead of a clean ValidationResult. Distinct timestamps 30 minutes apart were rejected as duplicate lead times because [validation.py:128](/home/zaypc/Documents/Personal/Projects/CycloneAid/validation.py:128) truncates lead hours to integers. If only whole-hour forecasts are intended, make that restriction explicit rather than treating distinct times as duplicates.

The GUI has some additional bounds checks, but allowing longitudes through 360° conflicts with its land-mask convention. Central validation should enforce finite numbers, UTC timestamps, consistent longitude normalization, required enums, and stated intensity override rules before downstream calculations run.

### 4. Background exception reporting loses the original error — high priority

**Reproduced using the actual preview method with a controlled renderer failure.** At [storm_tracker_gui.py:1660](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker_gui.py:1660), a delayed lambda references exception variable `e`. Python clears that exception variable when the `except` block exits. The scheduled callback raises another `NameError`, hiding the useful render error. The track and prognostic workers repeat the same pattern.

Capture the message before scheduling the callback, or bind it as a callback argument. This fix will make other failures substantially easier to diagnose.

### 5. Preview and job state can become stale or overlap — high priority

**Source-confirmed; concurrent execution was not stress-tested.** [storm_tracker_gui.py:1630](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker_gui.py:1630) and [storm_tracker_gui.py:1667](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker_gui.py:1667) save cached figures without verifying whether table values or storm name changed after preview. Edits do not invalidate those figures.

The loading flag disables buttons, but [storm_tracker_gui.py:1214](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker_gui.py:1214) can re-enable them when a user edits a cell during a render. Multiple render jobs can then overlap. Workers also read a Tk StringVar, and plotting uses global pyplot state without serialization. Matplotlib documents that it is not thread-safe and requires appropriate synchronization: [official threading guidance](https://matplotlib.org/stable/faq/index.html#work-with-threads).

Use a validated data snapshot, a revision identifier, and one rendering coordinator. Capture UI settings on the main thread, reject obsolete job results, and serialize plotting or isolate it in a worker process.

### 6. Cone construction has geographic and horizon errors — high priority

**Reproduced.** [storm_tracker.py:327](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker.py:327) samples the first 24 hours regardless of whether the supplied track ends earlier. A stationary six-hour track produced a radius corresponding approximately to the 24-hour 80-km entry. A single-point track was similarly expanded into a 24-hour envelope.

Interpolated coordinates are clipped to longitude ≤150° and latitude 0–40°, while original forecast-point circles are not. East-of-150°E and Southern Hemisphere examples produced disconnected MultiPolygons. The renderer assumes `cone.exterior`, which a MultiPolygon does not provide. Separately, a valid single-point forecast with the default Forecaster preset raised `IndexError` at the annotation code's second-point access.

[storm_tracker.py:323](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker.py:323) creates circles in longitude/latitude degrees using an averaged latitude correction. That approximation does not preserve physical radius in every direction. Longitude interpolation also lacks antimeridian handling.

The radius tables are hardcoded and High/Low confidence scales are heuristic. No empirical calibration, source period, basin, or coverage probability is recorded. For comparison, the NHC describes its cone using historical forecast-error coverage; this is an example of documenting the methodology, not a recommendation to apply Atlantic radii in the western Pacific: [NHC cone definition](https://www.nhc.noaa.gov/aboutcone.shtml).

### 7. RI semantics need a precise data contract — medium to high priority

At [storm_RI_plot.py:79](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_RI_plot.py:79), the algorithm takes the first point at or after the desired endpoint and normalizes the change to 24 hours. With sparse data, it may use a 30-hour or 48-hour interval rather than an actual 24-hour difference. Specify an endpoint interpolation policy or report missing coverage; do not silently equate those quantities.

The NHC definition refers to at least 30 kt gained in a 24-hour period: [NHC glossary](https://www.nhc.noaa.gov/aboutgloss.shtml). The README's attribution to “WMO” is not substantiated by a source in this repository.

**Reproduced.** A rate whose start point was original and end point was marked interpolated was reported as non-interpolated, because only the starting flag is propagated. Mixed-origin segments also lose connecting line segments in both track and RI rendering because groups do not share boundary endpoints.

### 8. Import/export behavior can lose information — medium to high priority

- **KMZ failure reproduced:** [storm_tracker_gui.py:1409](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker_gui.py:1409) parses the ZIP-format KMZ file directly as XML.
- **Source-confirmed timezone shift:** GPX timestamps are formatted without first converting to UTC at [storm_tracker_gui.py:1325](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker_gui.py:1325). `2026-01-01 03:00+09:00` becomes a table value of `2026-01-01 03:00`, later interpreted as UTC; the actual UTC time is `2025-12-31 18:00`.
- CSV and GPX import clear the current table before all rows have been validated and staged. Failure partway through can leave the old forecast lost and a partial replacement present.
- KML processing flattens all `<coordinates>` elements into one list, potentially joining unrelated points, lines, or polygon rings into a single storm track. It does not interpret KML track timestamps.
- GPX points with missing timestamps are assigned current-time hourly timestamps. These are fabricated times, rather than times interpolated between known observations. Mixed known/missing times can create incoherent ordering.
- CSV does not save the full session: storm name, confidence, selected preset, and independent issue-time metadata are not preserved.
- **CLI failures reproduced:** both track and prognostic scripts require a legacy `category` column that the checked-in sample and GUI CSV exporter do not provide. Both print an error but exit successfully, making automation failures harder to detect.

### 9. Landfall and city analysis have important limits — medium priority

Auto-landfall compares consecutive point locations, rather than intersecting track segments with a coastline. A segment can cross land between two water points without being flagged. Coordinate edits do not recompute all downstream transitions, and manual landfall-cell edits do not trigger map synchronization.

**Reproduced.** The indexed city search uses the same degree buffer for latitude and longitude. At 30°N, it excluded a synthetic city 2.5° east even though the linear haversine search correctly found it 240.7 km away, inside the configured 250-km radius. Fix longitude bounds and antimeridian behavior before relying on the index everywhere.

## Where performance work will matter most

### A. Separate preview from final export

[storm_tracker.py:843](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker.py:843) and [storm_prognostic.py:235](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_prognostic.py:235) write a 300-DPI image every time they construct a figure, including preview requests. Track Save then rebuilds the entire figure and exports it again at [storm_tracker_gui.py:1599](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker_gui.py:1599).

An isolated track build with 8,000 synthetic cities and basemap features disabled took about **1.16 s**. A separate 300-DPI export of that figure took about **3.42 s**. This demonstrates substantial avoidable preview work; it is not an end-to-end application benchmark. Build figures without writing files, use interactive-resolution previews, and export only on request. Reuse cached output only when the forecast revision and rendering settings still match.

Track saving currently runs on the GUI thread. Prognostic and RI saves also encode images on that thread. Preview threading therefore does not eliminate blocking operations from the user workflow.

### B. Connect the existing R-tree to its callers

[storm_prognostic.py:164](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_prognostic.py:164) and [storm_tracker.py:752](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker.py:752) explicitly pass `cities_data`, which disables indexed lookup in `find_nearest_city`. Prognostic processing does this for every point before deciding whether the point is an event. That is O(forecast points × cities), including work for rows never displayed in the event table.

In 100 repeated queries over 8,000 deterministic synthetic cities, the current linear caller path took **3.68 s**, versus **0.32 s** for the existing indexed path—about **11.6×** faster in this isolated run. Both measurements include the current helper's overhead. Fix the index's geographic bounds, query only needed event points, and reuse the shared indexed service.

The track's city-label loop at [storm_tracker.py:544](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker.py:544) also tests every city against the cone. `optimize_city_processing` exists but is not called. Use the cone bounding box to query candidates, then a prepared or vectorized geometry predicate.

### C. Stop rebuilding the map and reparsing the table on every edit

[storm_tracker_gui.py:1107](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker_gui.py:1107) deletes all markers and the path, recreates them, and resets the viewport. For 1,000 simulated rows, one refresh made **1,000 new markers, 1,001 deletions including the old path, and a new position/zoom change**. These are operation counts from a test double, not real widget timing.

[storm_tracker_gui.py:1225](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker_gui.py:1225) reparses and retags every row. A single pass over 1,000 simulated rows took about **2.16 s** in the review environment. Repeated row additions also rescan the growing table. The importers already stage their UI updates better than that, so they should not be described as having the same per-row refresh pattern.

Maintain parsed row state outside Treeview; validate the changed row immediately and run cross-row checks when appropriate. Debounce bursts of changes, update existing markers by stable row ID, update the path once, and make viewport fitting an explicit user action or import-time behavior.

### D. Close figures deliberately

GUI preview destruction closes only the Tk window; it does not deregister the pyplot figure. Track Save creates another figure and never closes it. **Reproduced:** three unclosed track renders left three registered figures. Repeated use can therefore retain figures, artists, and render buffers. Define ownership for preview figures and saved artifacts, and close figures on replacement, screen teardown, and final save when they are no longer in use.

### E. Reduce unnecessary cone geometry after fixing its meaning

[storm_tracker.py:327](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker.py:327) always constructs roughly 143 interpolated circles plus original-point circles and extras. A 0.95-radius extra is contained inside the main circle and contributes no useful area. The 1.05 extra actually changes the stated radius. Three identical cone fills add rendering work rather than creating a spatial gradient.

The sample cone alone took about **102 ms**; a short stationary cone still took about **99 ms**. This is real overhead, but lower priority than export and city/table work in the measured examples. Limit sampling to the valid horizon, choose a geometric tolerance, and remove redundant construction only after tests establish the intended envelope.

### F. Remove circular and repeated imports

[storm_tracker_gui.py:24](/home/zaypc/Documents/Personal/Projects/CycloneAid/storm_tracker_gui.py:24) manually executes sibling modules and overwrites their `sys.modules` entries. RI and preset metadata import the GUI merely to read the version. **Reproduced:** importing `storm_tracker`, then the GUI, left the original tracker object different from both the GUI's tracker and the currently registered tracker.

Move metadata into a dependency-light module and use normal package imports. This avoids duplicate module instances and geography caches and makes non-GUI plotting easier to test.

### G. Keep smaller optimizations in proportion

The RI loop performs one `searchsorted` and several pandas scalar accesses per result. Vectorized endpoint searches and array arithmetic could help long imported tracks. Small lists of 6-hour forecast points are unlikely to justify prioritizing this over the confirmed correctness failures and larger workflows above. Likewise, caching a few scalar trigonometric operations will not compensate for repeated image encoding or global city scans.

## Verification and limits

The review used a temporary environment under `/tmp`, separate from the project. Key installed versions were Python 3.12.14, pandas 3.0.6, NumPy 2.5.4, Matplotlib 3.11.2, Cartopy 0.26.0, Shapely 2.2.0, SciPy 1.18.1, and Rtree 1.4.1. These satisfy the relevant declared lower bounds. Optional map and land-mask integrations were not installed in that environment.

Checks included compiling all six Python modules, executing RI/validation/import/cone edge cases, exercising the original asynchronous callback with a controlled failure, running both CLI entrypoints against the sample CSV, checking module identity and figure retention, and measuring isolated city/render/table behavior. Map operation counting used a test double. Rendering checks deliberately disabled basemap features and supplied synthetic cities to avoid mixing downloads with computation.

A complete interactive GUI run, actual OSM tile behavior, coastline-based landfall accuracy, peak process memory, and full cold/warm rendering profiles have not been verified. Timings are single-environment diagnostic measurements, not performance guarantees. Scientific calibration and historical forecast skill were not established by this review.

Diagnostic files are currently `/tmp/cycloneaid_review_probes.py`, `/tmp/cycloneaid_review_extra.py`, and `/tmp/cycloneaid-review-output/`. They are temporary audit aids, not a committed test suite.

## Recommended work order

1. **Make existing workflows reliable:** fix RI datetime handling and imports, error callbacks, dependency compatibility, shared validation, and CLI schema support. Add targeted regression tests for these demonstrated failures.
2. **Protect output integrity:** version data snapshots, invalidate stale previews, coordinate render jobs, stage imports before replacing data, and normalize times and coordinates.
3. **Remove the largest waste:** split rendering from saving, use the corrected city index, avoid full-table/map refreshes, and manage figure lifetime.
4. **Clarify scientific behavior:** document supported regions, wind conventions, RI windows, generated timestamps, landfall limitations, and cone methodology; replace degree-circle approximations with an appropriate geodesic approach.
5. **Improve maintainability:** introduce a shared forecast/session model, normal package imports, a small metadata module, reproducible dependency constraints, CI, and project save/recovery. Extend features after those foundations are dependable.

The existing desktop workflow and rendering libraries can support this work. The evidence favors incremental repair and separation of responsibilities before considering a framework rewrite.
