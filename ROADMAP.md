# CycloneAid roadmap

The current release is [0.11.0a1](https://github.com/4caster-zay/CycloneAid/releases/tag/v0.11.0a1). Feature development continues with required CI and focused checks for each change. Broad platform, network, and manual qualification are deferred until a release candidate. Issues hold the tasks and acceptance criteria; this page explains their order.

## Deferred: desktop and network qualification

The [alpha stabilization milestone](https://github.com/4caster-zay/CycloneAid/milestone/1) remains open for:

- [Windows desktop checks #2](https://github.com/4caster-zay/CycloneAid/issues/2).
- [macOS desktop checks #3](https://github.com/4caster-zay/CycloneAid/issues/3).
- [OSM behavior on tester networks #4](https://github.com/4caster-zay/CycloneAid/issues/4).

These checks cover editing, themes, map setup, preview and export, recovery, and online or offline tile loading. They remain open and do not block unrelated feature development. Revisit them when selecting a release candidate for broader testing. Each needs a recorded result from the relevant desktop or network; headless CI and cached chart maps do not replace that evidence. Reproduce any reported failure and open a focused bug before treating it as a release blocker.

## Delivered

| Work | Result | References |
| --- | --- | --- |
| Alpha baseline | Reconciled the historical review, verified the repaired application, and published 0.10.0a2. | [Issue #1](https://github.com/4caster-zay/CycloneAid/issues/1), [release records](RELEASE_CHECKLIST.md) |
| Repository maintenance | Added issue forms, contribution guidance, labels, required CI, and grouped monthly dependency updates. | [Issue #5](https://github.com/4caster-zay/CycloneAid/issues/5), [milestone](https://github.com/4caster-zay/CycloneAid/milestone/2) |
| Forecast row generation | Added timestamp-only rows with a range preview, validation, and one-step undo. | [Issue #6](https://github.com/4caster-zay/CycloneAid/issues/6), [milestone](https://github.com/4caster-zay/CycloneAid/milestone/3), [guide](docs/row-generation.md) |
| Forecast workspace | Added embedded chart tabs, map readiness and setup, blank-name editing, and shared light/dark controls in 0.11.0a1. | [Controls #9](https://github.com/4caster-zay/CycloneAid/pull/9), [maps #10](https://github.com/4caster-zay/CycloneAid/pull/10), [integration #11](https://github.com/4caster-zay/CycloneAid/pull/11), [guide](docs/workspace.md) |

## Ongoing maintenance

Review tester reports weekly during active testing, and dependencies and release readiness monthly. Keep the next task clear in Issues, use focused PRs, and merge after required CI passes. See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow.

## Possible later work

Spreadsheet paste and exporting all charts together are candidates for further development. Their priority can be refined as feedback arrives; they are not scheduled for a release.

Keep Python 3.12, Tkinter, project schema 1, current regional coverage, and the existing scientific calculations. Broader package changes, expanded geography, new scientific products, and live advisory retrieval need separate proposals and supporting evidence. Each change must pass the applicable development checks in [CONTRIBUTING.md](CONTRIBUTING.md#check-your-work); deferred qualification is revisited at release-candidate selection.
