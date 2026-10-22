# CycloneAid roadmap

Current audience: the maintainer and existing desktop testers. Work follows completion gates rather than calendar deadlines. GitHub Issues hold task status and acceptance criteria; this document records direction. Retain Python 3.12/Tkinter, project schema 1, regional coverage, and scientific contracts.

## 1. Trustworthy alpha baseline

[Milestone: Alpha stabilization](https://github.com/4caster-zay/CycloneAid/milestone/1)

- [Reconcile the baseline and publish verified 0.10.0a2](https://github.com/4caster-zay/CycloneAid/issues/1): archive historical findings, run current checks, and publish matching version/tag/prerelease with evidence and limitations. Release evidence lives in [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).
- [Native Windows smoke check](https://github.com/4caster-zay/CycloneAid/issues/2), [native macOS smoke check](https://github.com/4caster-zay/CycloneAid/issues/3), and [OSM on target networks](https://github.com/4caster-zay/CycloneAid/issues/4) remain separate evidence requests. Passing headless CI does not close them.

Gate: no reproducible release blocker remains; every outstanding verification item has evidence or a linked issue. Unperformed native/network checks stay disclosed in alpha notes. This milestone remains open until their outcomes are recorded.

## 2. Sustainable repository maintenance

[Milestone: Repository maintenance](https://github.com/4caster-zay/CycloneAid/milestone/2) · [Implementation issue](https://github.com/4caster-zay/CycloneAid/issues/5)

Use issue forms, a short PR template, type/priority labels, short-lived `codex/` branches, and required CI on `main`. Solo PRs do not require a second reviewer. Archive historical material under `docs/`; keep current setup and workflows in the README. Group dependency updates monthly and refresh the hashed requirements export before merging.

Gate: testers can file a useful report, the next unblocked task is identifiable from issues, and required CI protects merges. Follow the [contribution and maintenance guide](CONTRIBUTING.md): triage weekly during active testing, review dependencies and release readiness monthly.

## 3. Faster forecast row entry

[Milestone: Forecast row generation](https://github.com/4caster-zay/CycloneAid/milestone/3) · [Implementation issue](https://github.com/4caster-zay/CycloneAid/issues/6)

Generate timestamps from an explicit UTC start, interval (6 hours by default), and horizon (120 hours by default). Preview the inclusive range; append without replacing existing rows. Keep coordinates and winds blank, retain generated timestamp provenance, and make the entire addition one undoable action. See [operator instructions](docs/row-generation.md).

Gate: pure generation and session/GUI regressions pass, incomplete drafts cannot render, completed drafts can render, and existing project/CLI compatibility remains intact. Deliver after baseline reconciliation and repository checks are in place.

## Later candidates

Evaluate spreadsheet paste and exporting all three charts from one snapshot after testers evaluate row generation. Neither is committed to a release yet. Defer broad package restructuring, geography expansion, new scientific products, and live advisory ingestion until a separately scoped proposal has evidence and acceptance criteria.
