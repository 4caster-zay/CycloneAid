# CycloneAid 🌀

**Version 0.11.0a1 — experimental alpha for client testing.**

CycloneAid prepares graphics from a forecast supplied by an operator. It provides a Tkinter data table and interactive OSM map, a regional forecast-track graphic, an intensity timeline, and exact-window wind-change analysis. It does not forecast winds, retrieve live advisories, assimilate observations, or calculate pressure changes.

**For testing and development only; not for operational use.** Check inputs and outputs against the appropriate official agency. Software release maturity does not establish forecast skill or scientific calibration.

## Quick start for local testing

From this project folder, run `./setup.sh` once, then `./start.sh` on Linux/macOS. On Windows, run `setup.bat` once, then `start.bat`. Setup installs the exact hashed dependencies into a persistent `.venv`; activation is optional. Python 3.12 with Tk is required.

You can also run `python3 storm_tracker_gui.py` (or `python storm_tracker_gui.py` on Windows). The script selects this project's `.venv` automatically before importing dependencies. `./start.sh --check` checks the interpreter, Tk, and installed dependencies without opening a window. Run the GUI from your graphical desktop terminal; an SSH/headless session needs its own display server.

To test the charts immediately:

1. Launch CycloneAid; it opens directly into the forecast workspace.
2. Choose **Project → Open sample** (also available in installed builds).
3. Choose **Enable maps** above the output tabs for full geography. Cached assets work immediately; missing assets offer one-time setup. The sample's saved without-basemap mode remains explicit until you enable maps.
4. Select **Track**, **Intensity**, or **Wind change**, then choose **Preview**. Previews update only on request; **Export PNG…** also works without a preview.
5. Edit a coordinate, use Undo/Redo, and save your project with the header **Save** action or **Project → Save as…**.

The **TEST PALAU** sample matches `forecast.csv`: a synthetic 120-hour scenario starting east of Palau, strengthening offshore, crossing the Philippines, and weakening before returning over water. See [scenario assumptions and expected checks](examples/README.md). Open the project file to retain the TEST title, source, and explicit 1-minute wind assumption in exported graphics; CSV alone does not carry session metadata.

The sample deliberately stores without-basemap (`degraded`) geography for an immediate offline first preview. New projects request full geography. The persistent readiness area shows **Full maps ready**, **Map setup needed**, or **Without basemap**, with setup/enable actions. Full geography includes the basemap, city analysis, and approximate coastline events; OSM live-map tiles require separate connectivity or cached coverage.

The source launcher also uses a prepared `.cache/cartopy` directory when present. An explicit `CARTOPY_DATA_DIR` takes precedence. `./start.sh --check` reports whether the required full-geography assets are cached.

Rendering failures appear in the chart tab with diagnostic details; request errors explain the action needed. Source checkouts write it to `.cache/logs/cycloneaid.log`; tracebacks also appear in the launching terminal. Logs rotate automatically. Installed builds store logs beside recovery data under the user's state directory. Include the exact error and the relevant log excerpt when reporting a bug.

## Install and run

Python **3.12** is the initial supported runtime. Tk must be available; on Debian/Ubuntu install `python3-tk`. Windows and macOS Python distributions must include Tk support.

Recommended reproducible environment, using [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/4caster-zay/CycloneAid.git
cd CycloneAid
uv sync --locked --extra desktop
uv run cycloneaid
```

The desktop extra supplies `tkintermapview` and optional `global-land-mask` point QC. Without it, the table and charts remain available, with a map placeholder. Basemap and city data are separate downloadable Natural Earth assets.

The existing pip installation route remains supported:

```bash
python -m venv venv
# Linux/macOS: source venv/bin/activate
# Windows: venv\Scripts\activate
python -m pip install --require-hashes -r requirements.txt
python storm_tracker_gui.py
```

`requirements.txt` is exported from `uv.lock`, with the desktop extra. Regenerate it after intentional dependency updates using:

```bash
uv export --locked --extra desktop --no-dev --no-emit-project --no-header --output-file requirements.txt
```

## Desktop workflow and session safety

- Use **Generate rows…** beside the row controls to create timestamps from an explicit UTC start, interval (default 6 hours), and horizon (default 120 hours). Preview the inclusive range before appending. Coordinates and winds stay blank for deliberate entry, and the addition is one undoable action. Existing timestamps must be valid and strictly increasing; generated times must follow them. See [forecast row generation](docs/row-generation.md).
- Enter or edit forecast data once, then preview or save any of the three chart products. Save can render without a preview. Preview construction never writes image files.
- Use **Session details…** for independent issue time, source agency, wind averaging period, and full/degraded geography. Unknown conventions stay unknown; the application does not convert wind averaging periods.
- Use the header **Save/Open** actions for versioned `.cycloneaid.json` project files. They preserve all rows, settings, provenance, and intensity override reasons, including incomplete drafts. Saving is atomic.
- **Ctrl+N** starts a project; **Ctrl+S** saves a project; **Ctrl+O** opens one; **Ctrl+Z / Ctrl+Y** undo/redo committed edits. Imports and batch row changes are single undoable actions.
- Dirty sessions receive a recovery autosave every 30 seconds. Recovery is offered on the next data-entry session. Recovery lives under `$XDG_STATE_HOME/cycloneaid` or `~/.local/state/cycloneaid`, and `%LOCALAPPDATA%/cycloneaid` on Windows.
- Charts use immutable snapshots. Edits invalidate previous previews; obsolete jobs cannot replace current previews. An export uses the snapshot captured when Export PNG was selected.
- Rendering and image encoding run in one separate process. Preview navigation stays interactive; exporting an existing current preview preserves its viewport. Embedded previews fit the pane without changing full-resolution exports.
- Map edits update existing markers without resetting the viewport. Use **Fit track** to recenter; imports fit the track once.

CSV is forecast interchange, not a full project backup. CSV import/export, GPX import, and KML/KMZ import are implemented. **GPX/KML export is not implemented.** Multiple GPX segments or KML tracks require explicit selection instead of being joined. KML polygon rings are not treated as tracks. Spatial formats without winds ask for an operator-supplied initial wind value, recorded in the project import notes.

All imports are staged before replacing the session. Missing times require an explicit start and interval; existing times are preserved. Generated times are marked separately from provided or interpolated times. Invalid or cancelled imports leave the current forecast unchanged. Timestamp offsets convert to UTC; timezone-free legacy timestamps are interpreted as UTC with a warning. The table displays UTC, and CSV files serialize normalized UTC timestamps without dropping precision; project files also retain editable draft values.

The workspace has an editor on the left and Map/Track/Intensity/Wind change tabs on the right. Drag the divider to resize them; your split is retained when resizing the window. Controls wrap for smaller windows. The design targets large desktops and remains usable at 1000×650. See the [workspace guide](docs/workspace.md).

The top-right **Sky / Typhoon** switch remembers local appearance outside project files. Storm names may remain blank: drafts stay editable, and charts use **Untitled storm** without changing the stored blank value. Enter/focus loss commits the name as one undoable edit; save/export/navigation capture pending edits. Double-click or press Enter to edit a cell; Tab/Shift+Tab commits and moves, and Escape cancels. Validation details are available from the status area or Help.

## Data and scientific behavior

- **Geography:** track graphics support forecast positions within **100–150°E and 0–40°N**, with Philippine province overlays. Unsupported positions are rejected, rather than clipped or moved. The plot fits the supplied track and supported envelope, including its boundary padding.
- **Coordinates:** accepted import longitudes use signed or 0–360° notation and normalize internally to `[-180, 180)`. Coordinates and winds must be finite; wind must be nonnegative. Times must be valid, strictly increasing, and unique. Sub-hourly forecasts are supported.
- **Classification:** the application's lower wind thresholds are TD 0, TS 34, STS 48, C1 64, C2 83, C3 96, C4 113, C5 137 kt. Storm structure is independent. These application rules do not identify an agency's wind averaging convention. A conflicting manual class requires a reason and remains visibly flagged in metadata.
- **Uncertainty:** `legacy-heuristic-v1` retains the original radius table: 20/40/80/115/150/175/200/300/400 km at 0/12/24/36/48/60/72/96/120 hours. High and Low confidence multiply these radii by 0.8 and 1.3. WGS84 geodesic discs replace degree-circle approximations. Coverage stops at the actual track end or T+120h, whichever comes first. This is a **heuristic envelope with no calibrated probability**; its name, limit, and qualification remain on track exports in both presets.
- **RI:** the default threshold is a gain of at least **30 kt in exactly 24 hours**, following the [NHC glossary](https://www.nhc.noaa.gov/aboutgloss.shtml#r). A missing endpoint is linearly interpolated between surrounding forecast values and marked estimated. No endpoint is extrapolated, and missing coverage produces no result. Estimated contributing points propagate to the result. Other window lengths are labeled wind change, not RI. Wind units must be supplied explicitly; the application does not guess units from magnitudes.
- **Landfall:** automatic events are approximate sea-to-land intersections with cached Natural Earth 10m land polygons along densified track segments. Their times and winds are interpolated, not observed. This can detect a crossing between two offshore forecast points, but coastline resolution and supplied forecast spacing limit accuracy. Manual flags remain independent. The optional land mask only provides point QC. It is disabled by default because its global grid uses approximately 1 GB of memory; enable it in Session details or with `--landmask-qc`.

CSV accepts the current columns `time,lat,lon,wind_kt,landfall,storm_type,intensity_class,is_interpolated`, plus optional `override_reason,time_origin`. Legacy `category` is also accepted; explicit current classification takes precedence. Allowed timestamp provenance values are `provided`, `generated`, `interpolated`, and `legacy-estimated`.

## Offline behavior and scripts

Use **Prepare maps** in the readiness area or **Help → Map setup** while connected to populate the Natural Earth cache. Full charts then work from that cache. OSM tile availability is independent and requires connectivity or tile cache coverage. If assets are unavailable, choose **degraded** geography explicitly: charts omit the basemap, city analysis, and automatic coastline events and identify that limitation. Inputs and manual landfall flags remain available.

Existing script commands remain available; installed entry points are `cycloneaid-track`, `cycloneaid-prognostic`, and `cycloneaid-ri`:

```bash
python storm_tracker.py Moderate EXAMPLE forecast.csv --degraded
python storm_prognostic.py forecast.csv EXAMPLE --degraded
python storm_RI_plot.py forecast.csv EXAMPLE 30
```

`--output chart.png` selects an export path. Otherwise scripts write into `Tracks/`, `Prognostics/`, or `RI_plots/`. GPX inputs with missing times can use `--start '2026-10-21T00:00Z' --interval-hours 6`. CLI failures print diagnostics to stderr and exit unsuccessfully. Library figure builders return figures without writing files; callers own and must close those figures.

## Development and release policy

```bash
uv run python -m unittest discover -s tests -v
uv run ruff check .
uv run python tools/check_release.py
# Linux GUI verification, with Xvfb installed:
CYCLONEAID_GUI_TESTS=1 xvfb-run -a uv run python -m unittest discover -s tests -v
# Also repeat all preview products with real, already-cached geography:
CYCLONEAID_GUI_TESTS=1 CYCLONEAID_GEOGRAPHY_TESTS=1 CARTOPY_DATA_DIR="$PWD/.cache/cartopy" xvfb-run -a uv run python -m unittest discover -s tests -p test_gui.py -v
# Explicit cold-download and warm-offline geography verification:
uv run python tools/smoke_geography.py --cache /tmp/cycloneaid-map-cache --output /tmp/cycloneaid-charts --download
```

CI checks Python 3.12 on Windows, Linux, and macOS, with and without desktop extras. GUI integration tests also run under Xvfb on Linux. Unit tests use synthetic geography and never require network downloads. `tools/benchmark.py` records repeated median timings; performance results are environment-specific diagnostics.

The canonical version is in `cycloneaid/metadata.py`; packaging, the GUI, and chart metadata consume it. Use SemVer change meanings with Python prerelease notation: compatible fixes increment PATCH, substantial changes/features during 0.x increment MINOR, and prereleases use `aN`, `bN`, then `rcN`. Tags match versions, e.g. `v0.11.0a1`. Reserve 1.0 for a dependable documented workflow and compatibility contract; scientific calibration is separately stated. See [CHANGELOG.md](CHANGELOG.md) and [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).

For planned work and contributing, start with the [roadmap](ROADMAP.md) and [contribution guide](CONTRIBUTING.md). [Historical review and reconciliation](docs/history/PROJECT_REVIEW.md) and [diagnostic benchmarks](docs/benchmarks/BENCHMARK_RESULTS.md) retain the earlier evidence and its limits.

MIT licensed. Created by Forecaster Zayed.
