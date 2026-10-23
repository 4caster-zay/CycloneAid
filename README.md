# CycloneAid

**0.11.0a1 · Experimental alpha**

CycloneAid is a desktop tool for plotting tropical cyclone forecasts that you supply. Edit a forecast table, inspect positions on an OpenStreetMap map, and produce track, intensity, and wind-change charts.

**For testing and development only, not operational use.** CycloneAid does not generate forecasts or retrieve live advisories. Check its inputs and outputs against the appropriate official agency. The uncertainty envelope is heuristic and has no calibrated probability; a software release does not establish forecast skill.

## Development direction

CycloneAid is moving forward with continued feature development, building on the new forecast workspace, embedded chart previews, and forecast row generation. Spreadsheet paste and exporting all charts together are candidates for upcoming work; release scope and dates are still to be decided.

We are keeping required automated CI and focused checks for data integrity, scientific calculations, exports, and each changed workflow. Broad native-platform, tester-network, and manual qualification will resume when a release candidate is selected for broader testing. Those checks remain tracked and unverified while feature development continues. See the [roadmap](ROADMAP.md) and [development checks](CONTRIBUTING.md#check-your-work) for the current approach.

## Get started

Python **3.12** with Tk support is required. From the project folder:

| Platform | First-time setup | Launch |
| --- | --- | --- |
| Linux or macOS | `./setup.sh` | `./start.sh` |
| Windows | `setup.bat` | `start.bat` |

Setup installs the locked dependencies in `.venv`; you do not need to activate it. On Debian or Ubuntu, install `python3-tk` first. Windows and macOS Python installations must include Tk.

You can also run `python storm_tracker_gui.py`; the launcher selects the project's `.venv` before loading dependencies. Use `python3` if that is your system's Python command. `./start.sh --check` checks Python, Tk, dependencies, and cached map assets without opening the application. Launch the GUI from a graphical desktop; remote or headless sessions need a display server.

### Try the sample

1. Launch CycloneAid and choose **Project → Open sample**.
2. Select **Track**, **Intensity**, or **Wind change**, then choose **Preview**. Use **Export PNG…** to save a chart, with or without a preview.
3. Choose **Enable maps** above the output tabs to add full geography. Cached assets are used immediately; missing assets require a one-time download.
4. Edit a coordinate, try Undo/Redo, and save the project with **Save** or **Project → Save as…**.

The bundled **TEST PALAU** project is a synthetic 120-hour forecast matching `forecast.csv`. It starts east of Palau, strengthens offshore, crosses the Philippines, and returns over water. It opens without a basemap so you can try the charts offline. Open the project rather than just the CSV to retain the TEST label, source, and 1-minute wind assumption. See the [sample notes](examples/README.md).

### Install with uv or pip

For development, use [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/4caster-zay/CycloneAid.git
cd CycloneAid
uv sync --locked --extra desktop
uv run cycloneaid
```

The `desktop` extra provides the OSM widget and optional land-mask checks. The table and charts work without it. Natural Earth chart assets are downloaded separately.

To install with pip:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\Scripts\activate
python -m pip install --require-hashes -r requirements.txt
python storm_tracker_gui.py
```

`requirements.txt` is the hashed desktop dependency export from `uv.lock`. See [CONTRIBUTING.md](CONTRIBUTING.md) before updating dependencies.

## Working with forecasts

The workspace places the forecast table beside Map, Track, Intensity, and Wind change tabs. Drag the divider to resize them. Controls wrap for smaller windows; the minimum supported size is 1000×650. Sky and Typhoon select the light and dark themes, and the application remembers your choice separately from project files and chart presets.

- **Enter data:** double-click a cell or press Enter to edit it. Tab and Shift+Tab commit and move; Escape cancels. **Generate rows…** creates timestamps from a UTC start, interval, and horizon. Coordinates and winds stay blank until entered. See [row generation](docs/row-generation.md).
- **Set project details:** use **Session details…** for issue time, source agency, wind averaging period, and map mode. Blank storm names are allowed; unnamed charts display **Untitled storm**. Unknown wind conventions remain unknown and are not converted.
- **Save your work:** `.cycloneaid.json` files retain rows, settings, incomplete drafts, provenance, and intensity override reasons. Saves are atomic. Ctrl+N starts a project, Ctrl+O opens one, Ctrl+S saves, and Ctrl+Z/Ctrl+Y undo or redo committed edits. Imports and batch row changes each form one undo step.
- **Preview and export:** charts render only when requested. Editing leaves older previews available and marks them stale. Exports use the validated forecast captured when you select **Export PNG…**. A matching preview's viewport is retained, and fitting it to the pane does not reduce export resolution.
- **Recover work:** unsaved changes are backed up every 30 seconds and offered for recovery at the next launch. Recovery files live under `$XDG_STATE_HOME/cycloneaid` or `~/.local/state/cycloneaid` on Linux/macOS, and `%LOCALAPPDATA%/cycloneaid` on Windows.

Save, preview, export, and project navigation capture pending name edits. Map edits preserve the viewport; **Fit track** recenters it. See the [workspace guide](docs/workspace.md) for more detail.

### Maps and offline use

New projects use full geography; existing projects keep their saved mode. The status above the output tabs shows **Full maps ready**, **Map setup needed**, or **Without basemap**.

Use **Prepare maps** or **Help → Map setup** while connected to download Natural Earth assets. Charts then work offline from the cache. The source launcher uses `.cache/cartopy` when available; `CARTOPY_DATA_DIR` overrides that location. **Continue without basemap** omits the chart basemap, city analysis, and automatic coastline events while keeping forecast inputs and manual landfall flags.

OSM tiles in the Map tab need their own connection or cached coverage. Their loading status and retry control are separate from chart-map readiness.

### Import and export formats

CSV imports and exports forecast rows. GPX, KML, and KMZ imports are also supported; GPX/KML export is not available. Use a project file for a complete backup.

Imports are checked before replacing the forecast. Missing timestamps require a start and interval; offsets are converted to UTC. Timezone-free legacy timestamps are treated as UTC with a warning. Generated timestamps remain distinct from provided or interpolated times. Invalid or canceled imports leave the current forecast unchanged.

Tracks with multiple segments require a selection rather than being joined automatically. KML polygon rings are not imported as tracks. Spatial files without winds ask for an initial wind value, which is recorded in the import notes.

CSV columns are `time,lat,lon,wind_kt,landfall,storm_type,intensity_class,is_interpolated`, with optional `override_reason,time_origin`. Legacy `category` is accepted; an explicit current classification takes precedence. Timestamp provenance values are `provided`, `generated`, `interpolated`, and `legacy-estimated`. CSV retains normalized UTC timestamp precision; project files also retain draft text.

## Scientific scope and limitations

- **Coverage:** track graphics support 100–150°E and 0–40°N, with Philippine province overlays. Positions outside this region are rejected. Longitudes may use signed or 0–360° notation and are normalized to `[-180, 180)`. Coordinates and winds must be finite, winds nonnegative, and timestamps valid, unique, and strictly increasing. Sub-hourly forecasts are supported.
- **Classification:** lower wind thresholds are TD 0, TS 34, STS 48, C1 64, C2 83, C3 96, C4 113, and C5 137 kt. Storm structure is independent. These application rules do not identify an agency's wind averaging convention. A conflicting manual class requires a reason and is flagged in metadata.
- **Uncertainty:** `legacy-heuristic-v1` uses radii of 20/40/80/115/150/175/200/300/400 km at 0/12/24/36/48/60/72/96/120 hours. High and Low confidence multiply them by 0.8 and 1.3. WGS84 geodesic discs extend to the track end or T+120h, whichever comes first. This is an uncalibrated heuristic envelope, not a probability estimate; that qualification appears on track exports in both presets.
- **Wind change and RI:** the default RI threshold is a gain of at least 30 kt in exactly 24 hours, following the [NHC glossary](https://www.nhc.noaa.gov/aboutgloss.shtml#r). Missing endpoints are interpolated between supplied values and marked estimated. There is no extrapolation; insufficient coverage produces no result. Estimated contributing points make the result estimated. Other window lengths are labeled wind change. Wind units must be supplied explicitly.
- **Landfall:** automatic events estimate sea-to-land crossings along densified track segments using Natural Earth 10m polygons. Event times and winds are interpolated, not observed. Coastline resolution and forecast spacing limit accuracy. Manual flags remain independent. Optional land-mask point checks are disabled by default because the global grid uses about 1 GB of memory; enable them in Session details or with `--landmask-qc`.

CycloneAid does not assimilate observations or calculate pressure changes.

## Command-line charts

The existing scripts and installed commands `cycloneaid-track`, `cycloneaid-prognostic`, and `cycloneaid-ri` remain available:

```bash
python storm_tracker.py Moderate EXAMPLE forecast.csv --degraded
python storm_prognostic.py forecast.csv EXAMPLE --degraded
python storm_RI_plot.py forecast.csv EXAMPLE 30
```

Use `--output chart.png` to choose a path. Otherwise, charts go to `Tracks/`, `Prognostics/`, or `RI_plots/`. GPX inputs with missing times accept `--start '2026-10-21T00:00Z' --interval-hours 6`. Failures print diagnostics to stderr and return a nonzero exit status. Library callers receive figures without file writes and must close them.

## Development and support

```bash
uv run python -m unittest discover -s tests -v
uv run ruff check .
uv run python tools/check_release.py
# Linux GUI tests, with Xvfb installed:
CYCLONEAID_GUI_TESTS=1 xvfb-run -a uv run python -m unittest discover -s tests -v
# Repeat previews with cached full geography:
CYCLONEAID_GUI_TESTS=1 CYCLONEAID_GEOGRAPHY_TESTS=1 CARTOPY_DATA_DIR="$PWD/.cache/cartopy" xvfb-run -a uv run python -m unittest discover -s tests -p test_gui.py -v
# Download and offline-cache checks:
uv run python tools/smoke_geography.py --cache .cache/geography-check/maps --output .cache/geography-check/charts --download
```

CI runs Python 3.12 on Windows, Linux, and macOS, with and without desktop extras. Linux GUI tests run under Xvfb. Normal tests use synthetic geography without network downloads. Native desktop and tester-network checks are tracked separately in the [release record](RELEASE_CHECKLIST.md).

Rendering errors appear in the chart tab. Source checkouts write rotating logs to `.cache/logs/cycloneaid.log`; installed builds store them beside recovery data. Tracebacks also appear in the launching terminal. Include the exact error, relevant log excerpt, and a small reproducible input when [reporting a bug](https://github.com/4caster-zay/CycloneAid/issues/new/choose).

Version metadata lives in `cycloneaid/metadata.py`, and release tags match it, such as `v0.11.0a1`. See the [changelog](CHANGELOG.md), [roadmap](ROADMAP.md), and [contribution guide](CONTRIBUTING.md). The [historical review](docs/history/PROJECT_REVIEW.md) and [benchmarks](docs/benchmarks/BENCHMARK_RESULTS.md) retain earlier findings and measurements.

MIT licensed. Created by Forecaster Zayed.
