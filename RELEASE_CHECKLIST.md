# 0.10.0a2 release verification

Candidate date: **22 October 2026**. Experimental alpha for client testing only; not for operational use. Version maturity does not establish forecast skill, empirical cone calibration, or native GUI compatibility.

## Verified baseline

- [x] Committed `ae43992` passed all six Windows/Linux/macOS × base/desktop CI jobs and the Linux GUI job: [baseline CI run](https://github.com/4caster-zay/CycloneAid/actions/runs/39710621706).
- [x] The [historical review reconciliation](docs/history/PROJECT_REVIEW.md) maps old findings to current code/tests; no still-reproducible historical blocker was established.
- [x] [Historical benchmarks](docs/benchmarks/BENCHMARK_RESULTS.md) retain their dates and measurement limits; they are not a current performance guarantee.
- [x] Prior alpha evidence is preserved in the [0.10.0a1 verification archive](docs/history/release-0.10.0a1.md).

## Candidate gates

Record commands, counts, and outcomes against the final candidate in the implementation PR and release notes. A source commit's passed CI is required before publication.

- [x] Full Linux regression suite: 60 tests passed, including CLI exports, renderer errors/restarts, and all initial generation/session/GUI checks.
- [x] Linux Tk suite used a temporary Xvfb display and cached full geography, including generation preview/cancel, append/undo/redo, validation, recovery, and 18 degraded/full sample preview cycles.
- [x] After preserving fractional-second table values, all six focused generation GUI tests passed, including unchanged timestamp edits and preview invalidation.
- [x] Ruff, single-source release metadata, locked dependency export byte equality, and `pip check` passed.
- [x] Wheel/source distribution built; generation modules and version verified. Extracted source CLI export regression passed; samples, launchers, locks, tools, and linked docs are included.
- [ ] Candidate's full seven-job committed CI passes.
- [ ] Version/changelog/README/tag all identify `0.10.0a2`; publish qualified GitHub prerelease with built artifacts and exact CI evidence.

## Explicit remaining alpha verification

These are evidence requests, not confirmed defects. Keep them open until results are recorded; disclose them in every candidate/prerelease note while outstanding.

- [ ] [Native Windows smoke check #2](https://github.com/4caster-zay/CycloneAid/issues/2): editing, generation, previews/export, close during rendering, and interrupted-work recovery.
- [ ] [Native macOS smoke check #3](https://github.com/4caster-zay/CycloneAid/issues/3): the same graphical-desktop workflow and shutdown/recovery checks.
- [ ] [OSM target-network check #4](https://github.com/4caster-zay/CycloneAid/issues/4): online/slow/offline pan/zoom and independent Natural Earth chart readiness.

Publication gate: all locally executable candidate checks and committed CI pass, no confirmed blocker remains, and every unperformed check has a linked issue and explicit release-note disclosure. Native/network follow-ups may remain open for this experimental alpha; do not describe them as passed. Track release completion in [issue #1](https://github.com/4caster-zay/CycloneAid/issues/1).
