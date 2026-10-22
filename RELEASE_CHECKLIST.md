# 0.11.0a1 workspace release verification

Candidate date: **22 October 2026**. Experimental alpha for testing and development only; not for operational use. Software maturity does not establish forecast skill or empirical cone calibration.

## Component evidence

- [Shared theme/name controls PR #9](https://github.com/4caster-zay/CycloneAid/pull/9) passed required CI before merge.
- [Map-readiness PR #10](https://github.com/4caster-zay/CycloneAid/pull/10) passed required CI before merge.
- Previous release evidence is retained in the [0.10.0a2 archive](docs/history/release-0.10.0a2.md).

## Integration gates

- [ ] Final complete regression suite with a real Linux Tk display and cached full geography.
- [ ] Name editing/dirty state/save/recovery, project-scoped render/setup outcomes, fitted chart views, focus retention, and shutdown cleanup.
- [ ] Both themes inspected at 1920×1080, 1366×768, and 1000×650, including responsive controls and map-enabled previews.
- [ ] Hover, selected, pressed, focused, and disabled text/background states checked for theme controls, menus, fields, and tabs.
- [ ] Ruff, version consistency, dependency compatibility, byte-identical hashed dependency export, YAML, and Markdown links.
- [ ] Wheel/source builds, packaged sample equality, extracted artifact startup/sample/generation/CLI checks, and checksums.
- [ ] Final committed seven-job CI passes before integration merge; matching version/tag/prerelease artifacts.

## Explicit remaining platform/network verification

- [Native Windows smoke check #2](https://github.com/4caster-zay/CycloneAid/issues/2): repeat the redesigned workspace's editing, themes, map setup, chart/export, close-during-render, and recovery workflow on a native graphical desktop.
- [Native macOS smoke check #3](https://github.com/4caster-zay/CycloneAid/issues/3): the same desktop checks, including focus and keyboard behavior.
- [Tester-network OSM check #4](https://github.com/4caster-zay/CycloneAid/issues/4): online/slow/offline tile loading and retry, independently of cached Natural Earth charts.

These checks remain unperformed here and must be disclosed in alpha notes. Headless cross-platform CI and Linux screenshots do not substitute for them. Publication requires passing executable gates, no confirmed blocker, and tracked/disclosed outstanding checks. Scientific behavior, regional coverage, project schema 1, and CLI compatibility remain unchanged.
