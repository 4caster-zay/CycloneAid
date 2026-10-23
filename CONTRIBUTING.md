# Contributing to CycloneAid

Thanks for helping improve CycloneAid. It is an experimental desktop application, so changes should keep the workflow reliable and its [scientific limitations](README.md#scientific-scope-and-limitations) clear.

## Set up

Use Python 3.12 with Tk support and [uv](https://docs.astral.sh/uv/). On Debian or Ubuntu, install `python3-tk`; Linux GUI tests also need `xvfb`.

```bash
git clone https://github.com/4caster-zay/CycloneAid.git
cd CycloneAid
uv sync --locked --extra desktop
uv run --no-sync cycloneaid
```

Omit `--extra desktop` when checking the base installation. Full chart maps need Natural Earth assets; the sample opens without a basemap and can render offline. The README explains map setup and diagnostics.

## Propose a change

Check [existing issues](https://github.com/4caster-zay/CycloneAid/issues) before opening a report. Use the bug or feature form, or a blank issue for maintenance and documentation. Explain the problem, the expected result, how to verify it, and any related work. The [roadmap](ROADMAP.md) describes current priorities.

Use one type label: `bug`, `feature`, `maintenance`, or `documentation`. Add `priority:high` for a release blocker or serious regression, `priority:normal` for planned work, or `priority:low` for later improvements. Use `needs-information` when a report needs more detail. Issues and milestones track progress; a separate project board is not used.

Create a short-lived `codex/` branch from the latest `main`, such as `codex/forecast-row-generation`. Keep the PR focused and link its issue. Explain what changed, why, and how it was checked. Required CI must pass before merging; a second reviewer is not required for solo maintenance. Resolve conflicts and rerun the affected checks before merging, then delete the merged branch.

## Check your work

During active feature development, keep required CI and focused verification for each change. Protect input validation, scientific calculations, saved projects and recovery, undo/redo, project ownership of background results, and export correctness with relevant regression checks. Smoke-check the workflow changed by the PR. Documentation-only changes need documentation and consistency checks rather than a repeated manual application qualification.

Defer broad native Windows/macOS checks, tester-network coverage, exhaustive theme/window-size inspection, and repeated full manual release checklists until a release candidate is selected for broader testing. Keep those follow-ups open; they do not block unrelated feature work. Existing automated cross-platform CI remains required. Deferral does not waive checks needed to verify the behavior changed by a PR.

After syncing the locked environment, run:

```bash
uv run --no-sync python -m unittest discover -s tests -v
uv run --no-sync ruff check .
uv run --no-sync python tools/check_release.py
```

For Tkinter or session changes, also run the Linux GUI tests with a display:

```bash
CYCLONEAID_GUI_TESTS=1 xvfb-run -a uv run --no-sync python -m unittest discover -s tests -v
```

Normal tests use synthetic geography and do not download maps. For geography changes, run the affected cached-map and download/offline checks in the README and record the results. Broad native Windows/macOS and tester-network qualification remains deferred as described above.

Run `uv build` for packaging or release changes. Check that the wheel and source archive contain the needed files and that the installed application opens the sample. If you cannot run a relevant check, say so in the PR and link a follow-up issue. The [release record](RELEASE_CHECKLIST.md) lists the remaining platform and network checks.

Keep generated charts, build output, logs, caches, and scratch files out of commits. Remove local verification files when finished. Keep useful map assets and development environments locally; they are ignored by Git.

## Compatibility

- Keep Python 3.12, Tkinter, the supported region, and existing chart products unless a proposal explicitly changes them.
- Preserve project schema 1, incomplete drafts, provenance, atomic saves, and undo/redo. Document a migration before changing the project format.
- Preserve script commands and installed CLI entry points. CSV exchanges forecast rows; project files back up the complete session.
- Keep UTC handling, coordinate and wind validation, averaging assumptions, uncertainty qualifications, and estimated-result labels clear. Changes to calculations need a rationale and regression tests that demonstrate the intended result.

## Dependencies

`pyproject.toml` declares dependencies, `uv.lock` records their versions, and `requirements.txt` is the hashed desktop export. Do not edit the export by hand.

For an intentional update, adjust constraints only if needed, then run:

```bash
uv lock --upgrade-package PACKAGE
uv sync --locked --extra desktop
uv export --locked --extra desktop --no-dev --no-emit-project --no-header --output-file requirements.txt
```

Replace `PACKAGE` with the dependency name. Review the lock and export together, and check both base and desktop installations through CI. To verify the export without replacing it, write to `requirements.check.txt`, compare it with `requirements.txt`, then delete the check file. CI performs the same comparison.

Dependabot groups Python and GitHub Actions updates monthly. A Python dependency PR also needs the regenerated requirements export. Review major-version and scientific-library changes carefully. Merge only after CI passes; dependency updates are not merged automatically.

## Releases and maintenance

Keep the version in `cycloneaid/metadata.py` and record user-visible changes in the changelog. Use patch versions for compatible fixes and minor versions for substantial changes during 0.x. Prereleases use `aN`, `bN`, then `rcN`; tags match the version, such as `v0.11.0a1`. Version 1.0 requires a dependable, documented workflow and compatibility policy; scientific calibration remains a separate question.

During active testing, review issues weekly. Reproduce reports, ask for missing details, assign a type, priority, and milestone, and close fixed reports with a link to the change and its verification. Review dependencies and release readiness monthly, and update the roadmap when priorities change.

Before publishing, record the tested commit, CI results, package checksums, and known limitations. Keep unfinished native-desktop and OSM-network checks open and disclose them in the release notes. Do not describe a check as passed until its result has been recorded.
