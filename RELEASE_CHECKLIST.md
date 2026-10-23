# Release verification: 0.11.0a1

Released **22 October 2026** as an experimental alpha for testing and development, not operational use. Software verification does not establish forecast skill or calibrate the heuristic uncertainty envelope.

## Release and CI

[0.11.0a1](https://github.com/4caster-zay/CycloneAid/releases/tag/v0.11.0a1) was published from `55afe152a9f12513ef4edcd8ddddac25afc0623e`, with the matching tag `v0.11.0a1`. The release includes a wheel, source archive, 14 UI captures, and SHA-256 checksums. Uploaded asset digests were checked against the local files.

The work was delivered in [shared controls #9](https://github.com/4caster-zay/CycloneAid/pull/9), [map readiness #10](https://github.com/4caster-zay/CycloneAid/pull/10), and [workspace integration #11](https://github.com/4caster-zay/CycloneAid/pull/11). All seven required jobs passed on the [final PR commit](https://github.com/4caster-zay/CycloneAid/actions/runs/39758488849), [merged main](https://github.com/4caster-zay/CycloneAid/actions/runs/39758826146), and [release tag](https://github.com/4caster-zay/CycloneAid/actions/runs/39758941514). The main run needed a retry after an external package-server HTTP 403 stopped the initial GUI setup before tests ran.

Earlier records: [0.10.0a1](docs/history/release-0.10.0a1.md) and [0.10.0a2](docs/history/release-0.10.0a2.md).

## Completed checks

- [x] Passed 129 local regression tests with a real Linux Tk display and cached full geography. Repeated the six generator GUI tests after the final dialog-style change.
- [x] Checked name editing, pending saves, dirty state, recovery, undo/redo, project ownership of render and setup results, focus retention, and shutdown cleanup.
- [x] Inspected both themes at 1920×1080, 1366×768, and 1000×650. The 14 captures also cover map setup, session details, row generation, and control states.
- [x] Checked hover, selected, pressed, focused, and disabled appearances. All 96 tested theme/style/state combinations meet 4.5:1 text contrast. GUI tests cover keyboard selection and saved theme preferences.
- [x] Passed Ruff, version consistency, dependency compatibility, hashed-export comparison, YAML parsing, and local Markdown-link checks.
- [x] Matched wheel and source contents to the release checkout and the bundled sample to its documented example. Checked startup, sample opening, and row generation from extracted packages, plus source-archive CLI exports.
- [x] Merged after required CI passed and verified the tag, version, published assets, and checksums.

The UI archive uses real cached chart geography. Its missing-asset and unavailable-live-map examples are simulated; they are not evidence of OSM connectivity on tester networks. Scientific calculations, regional coverage, project schema 1, CLI commands, and export metadata were preserved.

## Checks still open

- [Windows #2](https://github.com/4caster-zay/CycloneAid/issues/2): native desktop editing, themes, map setup, charts, exports, recovery, and closing during rendering.
- [macOS #3](https://github.com/4caster-zay/CycloneAid/issues/3): the same workflow, including native focus and keyboard behavior.
- [Tester-network OSM #4](https://github.com/4caster-zay/CycloneAid/issues/4): online, slow, and offline tile loading and retry, separately from cached Natural Earth charts.

These results have not yet been recorded and remain disclosed in the alpha notes. As agreed on 23 October 2026, broad native-platform, tester-network, and manual qualification is deferred until release-candidate selection and does not block unrelated feature development. Required CI and focused checks protecting data integrity, calculations, and changed workflows continue. Linux screenshots and headless cross-platform CI do not substitute for the deferred results. The [contribution guide](CONTRIBUTING.md#check-your-work) defines the development checks, and its [release guidance](CONTRIBUTING.md#releases-and-maintenance) describes the evidence required for later releases.
