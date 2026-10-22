# 0.10.0a2 release verification

**Historical record: 22 October 2026.** Version `0.10.0a2` was an experimental alpha for client testing. This page preserves the candidate checks and follow-up recorded for that release. Forecast skill, empirical cone calibration, and native GUI compatibility were not established. See the [current release checklist](../../RELEASE_CHECKLIST.md) for later results.

## Verified baseline

- [x] Committed `ae43992` passed all six Windows/Linux/macOS × base/desktop CI jobs and the Linux GUI job: [baseline CI run](https://github.com/4caster-zay/CycloneAid/actions/runs/39710621706).
- [x] The [historical review reconciliation](PROJECT_REVIEW.md) maps old findings to current code/tests; no still-reproducible historical blocker was established.
- [x] [Historical benchmarks](../benchmarks/BENCHMARK_RESULTS.md) retain their dates and measurement limits; they are not a current performance guarantee.
- [x] Prior alpha evidence is preserved in the [0.10.0a1 verification archive](release-0.10.0a1.md).

## Candidate verification

The implementation PR and release notes record commands, test counts, and results. Publication required successful CI against the source commit.

- [x] Final Linux regression suite: all 62 tests passed in 128 seconds, including CLI exports, renderer errors/restarts, and generation/session/GUI checks.
- [x] Linux Tk suite used a temporary Xvfb display and cached full geography, including generation preview/cancel, append/undo/redo, validation, recovery, and 18 degraded/full sample preview cycles.
- [x] After preserving fractional-second table values, all six focused generation GUI tests passed, including unchanged timestamp edits and preview invalidation.
- [x] Ruff, single-source release metadata, locked dependency export byte equality, and `pip check` passed.
- [x] Wheel/source distribution built; generation modules and version verified. Extracted wheel imports/generation and extracted source CLI export regression passed; samples, launchers, locks, tools, and linked docs are included.
- [x] Source candidate `1732888` passed all seven committed CI jobs: [candidate CI run](https://github.com/4caster-zay/CycloneAid/actions/runs/39713028678). Publication also required passing final PR checks after the documentation updates.
- [x] Canonical version, changelog, and README identified `0.10.0a2`. Publication required the matching tag `v0.10.0a2`, built artifacts, and final CI evidence.

## Outstanding platform and network checks

These checks were still outstanding at publication. The linked issues track their results, and release notes disclose them while they remain open.

- [ ] [Native Windows smoke check #2](https://github.com/4caster-zay/CycloneAid/issues/2): editing, generation, previews/export, close during rendering, and interrupted-work recovery.
- [ ] [Native macOS smoke check #3](https://github.com/4caster-zay/CycloneAid/issues/3): the same graphical-desktop workflow and shutdown/recovery checks.
- [ ] [OSM target-network check #4](https://github.com/4caster-zay/CycloneAid/issues/4): online/slow/offline pan/zoom and independent Natural Earth chart readiness.

The release required successful local checks and committed CI, no confirmed blockers, and a linked issue and release-note disclosure for each unperformed check. Native and network follow-ups could remain open for this alpha, with their unverified status stated. The [GitHub prerelease](https://github.com/4caster-zay/CycloneAid/releases/tag/v0.10.0a2) and [issue #1](https://github.com/4caster-zay/CycloneAid/issues/1) record publication, tag, artifacts, and final CI evidence.
