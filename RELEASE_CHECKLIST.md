# 0.11.0a1 workspace release verification

Candidate date: **22 October 2026**. Experimental alpha for testing and development only; not for operational use. Software maturity does not establish forecast skill or empirical cone calibration.

## Component evidence

- [Shared theme/name controls PR #9](https://github.com/4caster-zay/CycloneAid/pull/9) passed required CI before merge.
- [Map-readiness PR #10](https://github.com/4caster-zay/CycloneAid/pull/10) passed required CI before merge.
- [Workspace/output integration PR #11](https://github.com/4caster-zay/CycloneAid/pull/11) has passing [seven-job implementation CI](https://github.com/4caster-zay/CycloneAid/actions/runs/39758124384) for `bd00dd8`. Branch protection requires successful checks on the final documentation commit too.
- Previous release evidence is retained in the [0.10.0a2 archive](docs/history/release-0.10.0a2.md).

## Integration gates

- [x] Complete regression suite: **129 tests pass** with a real Linux Tk display and cached full geography. The six generator GUI tests also pass after the final dialog styling refinement.
- [x] Name editing/dirty state/save/recovery, project-scoped render/setup outcomes, fitted chart views, focus retention, and shutdown cleanup.
- [x] Both themes inspected at 1920×1080, 1366×768, and 1000×650, including responsive controls and map-enabled previews. Separate setup, session-details, generator-dialog, and control-state captures bring the UI evidence set to 14 images.
- [x] Hover, selected, pressed, focused, and disabled appearances checked; all **96 tested theme/style/state combinations** meet 4.5:1 text contrast. Keyboard selection and theme persistence are covered by GUI tests.
- [x] Ruff, version consistency, dependency compatibility, byte-identical hashed dependency export, YAML, and Markdown links.
- [x] Wheel/source builds match checkout files; the packaged sample matches the documented example. Extracted artifact startup/sample/generation and source CLI export checks pass.
- [x] Seven-job implementation CI passes before integration; final commit checks are enforced before merge.

Publication gate: tag `v0.11.0a1` must match the canonical version and final integrated commit. The [GitHub prerelease](https://github.com/4caster-zay/CycloneAid/releases/tag/v0.11.0a1) records final CI and supplies wheel/source artifacts, the UI evidence archive, and SHA-256 checksums. The UI archive distinguishes real cached geography from simulated missing-asset/live-map states; it makes no tester-network claim.

## Explicit remaining platform/network verification

- [Native Windows smoke check #2](https://github.com/4caster-zay/CycloneAid/issues/2): repeat the redesigned workspace's editing, themes, map setup, chart/export, close-during-render, and recovery workflow on a native graphical desktop.
- [Native macOS smoke check #3](https://github.com/4caster-zay/CycloneAid/issues/3): the same desktop checks, including focus and keyboard behavior.
- [Tester-network OSM check #4](https://github.com/4caster-zay/CycloneAid/issues/4): online/slow/offline tile loading and retry, independently of cached Natural Earth charts.

These checks remain unperformed here and must be disclosed in alpha notes. Headless cross-platform CI and Linux screenshots do not substitute for them. Publication requires passing executable gates, no confirmed blocker, and tracked/disclosed outstanding checks. Scientific behavior, regional coverage, project schema 1, and CLI compatibility remain unchanged.
