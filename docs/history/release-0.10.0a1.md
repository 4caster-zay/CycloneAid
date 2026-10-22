# 0.10.0a1 release verification

**Historical record: 21 October 2026.** Version `0.10.0a1` was an alpha build for client feedback. This page preserves its verification results and outstanding checks at the time. See the [current release checklist](../../RELEASE_CHECKLIST.md) for later results.

## Completed local checks

- [x] Reproduced the RI datetime/provenance regression before fixing it.
- [x] Regression coverage for domain validation, staged imports, project round-trips, atomic failure handling, undo/redo, and timestamp provenance.
- [x] Geometry coverage for physical radii, short/stationary/single-point tracks, horizon limits, multipart rendering, regional rejection, and between-point landfall.
- [x] Spawned-renderer coverage for preview copies, cache reuse/invalidation, errors, crashes/restart, serialization, and cleanup.
- [x] Linux Tk checks under a temporary Xvfb display: editing, undo/redo, settings, project save, recovery, busy controls, and failed import preservation.
- [x] Interactive preview/export checks while editing, real map marker reuse, and clean map callback teardown.
- [x] Cold Natural Earth asset preparation and full sample chart exports with subsequent downloads blocked.
- [x] Visual inspection of full-geography sample charts, including event-table and metadata layout.
- [x] Locked desktop dependency installation and dependency compatibility check.
- [x] Persistent checkout `.venv`, setup/launch scripts, base-Python bootstrap, and dependency/cache diagnostics.
- [x] Full application Home → data entry → sample project → Home navigation and clean shutdown; stale Home mouse-wheel callback fixed.
- [x] Native Linux/small-delta scrolling, map tile staleness, main-thread image creation, normalized wheel zoom, and resize/teardown regression checks.
- [x] Final local regression suite: 44 tests passed with Tk enabled; lint, release metadata, and generated dependency export checks passed.
- [x] TEST PALAU CSV/project consistency, exact and interpolated RI windows, and all three offline full-geography exports.
- [x] Matching generated requirements export and single-source release metadata check.
- [x] Wheel build and repeated median benchmarks; see the [benchmark archive](../benchmarks/BENCHMARK_RESULTS.md).

## Follow-up recorded at the time

Follow-up verification on 22 October 2026: 47 local tests passed with Tk enabled and cached full geography, including 18 sample preview cycles across all three products. The clean core-only environment also passed (37 executed, 10 desktop/GUI checks skipped). Lint and wheel construction passed. The original unrecorded client popup has not been reproduced; new logs retain future worker and Tk tracebacks.

- [ ] Run the final committed CI matrix on Windows, Linux, and macOS, with and without desktop extras.
- [ ] Perform native Windows/macOS interactive smoke checks, including closing the app during rendering and recovering interrupted work.
- [ ] Confirm OSM tile behavior on target networks; cached Natural Earth readiness does not establish tile availability.
- [ ] Collect client feedback and resolve confirmed regressions in the next alpha build (`0.10.0a2`).

Empirical cone calibration and operational suitability were not established by this release.
