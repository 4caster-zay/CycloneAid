# Contributing to CycloneAid

CycloneAid is an experimental desktop application for testing and development. Preserve the scientific limitations described in [README.md](README.md); release maturity does not establish forecast skill or calibration.

## Set up a development environment

Use Python 3.12 with Tk support and [uv](https://docs.astral.sh/uv/). On Debian/Ubuntu, install `python3-tk`; the Linux GUI tests also need `xvfb`.

```bash
git clone https://github.com/4caster-zay/CycloneAid.git
cd CycloneAid
uv sync --locked --extra desktop
uv run --no-sync cycloneaid
```

Omit `--extra desktop` to test the supported environment without optional desktop dependencies. Full geography needs separately prepared Natural Earth assets; the sample project uses degraded geography and can render without downloading them. See the README for map preparation and diagnostics.

## Choose and propose work

[ROADMAP.md](ROADMAP.md) describes direction and milestone order. GitHub Issues hold actionable work and its status. Before starting, look for an existing issue; use the bug or feature form for a new report. Maintenance and documentation issues can use a blank issue. Each implementation issue should state the problem, intended behavior, acceptance criteria, and dependencies (or “None”).

Use one primary type label: `bug`, `feature`, `maintenance`, or `documentation`. Add one priority: `priority:high` for release blockers or serious regressions, `priority:normal` for planned work, or `priority:low` for later improvements. Use `needs-information` when a report needs input before it can be reproduced or implemented. Milestones group alpha stabilization, repository maintenance, and forecast row generation; avoid duplicating status in a separate project board.

Create a short-lived `codex/` branch from current `main`, such as `codex/forecast-row-generation`. Keep each PR focused on a reviewable behavior or maintenance task and link its issue. Describe the resulting behavior, checks, and remaining limitations. Required CI must pass before merging into `main`; solo maintenance does not require a second reviewer. Resolve conflicts and rerun affected checks before merging.

## Verify a change

Run these from the repository root after syncing the locked environment:

```bash
uv run --no-sync python -m unittest discover -s tests -v
uv run --no-sync ruff check .
uv run --no-sync python tools/check_release.py
uv export --locked --extra desktop --no-dev --no-emit-project --no-header --output-file /tmp/cycloneaid-requirements.check.txt
```

Compare the exported file with `requirements.txt`; they must match exactly. On Windows, choose a temporary output path appropriate to your system. The cross-platform CI performs the same comparison.

For changes to Tkinter or session workflows, also run the Linux GUI suite with a display:

```bash
CYCLONEAID_GUI_TESTS=1 xvfb-run -a uv run --no-sync python -m unittest discover -s tests -v
```

Tests normally use synthetic geography and require no map downloads. For changes affecting geography, use the cached-geography and download/offline checks documented in the README and record their results. Verify native Windows/macOS behavior separately when platform behavior changes; passing Linux GUI tests does not establish native GUI compatibility.

Use `uv build` to verify packaging for release or packaging changes. Follow [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) for release evidence and outstanding native/network checks. Record checks you could not run in the PR with a linked follow-up issue.

## Preserve compatibility and scientific behavior

- Retain Python 3.12, Tkinter, supported regional coverage, and the existing chart products unless an issue explicitly changes that contract.
- Preserve project schema version 1, editable incomplete drafts, provenance, atomic saves, and session undo/redo. Introduce a documented migration before changing the project-file contract.
- Keep the existing script commands and installed CLI entry points compatible. CSV is forecast interchange; project files are the complete session backup.
- Keep UTC normalization, finite coordinate/wind validation, wind averaging assumptions, uncertainty qualifications, and estimated-result markings visible. Changes to scientific calculations need explicit rationale and meaningful regression cases.
- Keep application version metadata in `cycloneaid/metadata.py`. Update the changelog for user-visible changes and use a matching version tag for releases.

## Update dependencies

`pyproject.toml` declares dependencies; `uv.lock` records the resolved environment. `requirements.txt` is a generated, hashed export with the desktop extra. Do not edit the export by hand or add a separate pip updater.

For an intentional update, adjust constraints only when needed, then run:

```bash
uv lock --upgrade-package PACKAGE
uv sync --locked --extra desktop
uv export --locked --extra desktop --no-dev --no-emit-project --no-header --output-file requirements.txt
```

Replace `PACKAGE` with the dependency name. Review the lock and export together, run the checks above, and test both base and desktop environments through CI. Dependabot proposes grouped Python and GitHub Actions updates monthly. A Python update PR must also contain the regenerated `requirements.txt`; add that export to the PR before merging if the bot did not produce it. Review major-version and scientific-stack changes carefully and merge updates only after required CI passes. No dependency PR merges automatically.

## Maintain the repository

During active testing, triage issues weekly: reproduce tester reports, request missing information, set type/priority/milestone, and identify the next unblocked task. Close resolved reports with a linked fix and verification result. Update the roadmap when direction or milestone completion changes.

Monthly, review grouped dependency PRs, stale issues, and release readiness. Keep release evidence tied to a committed revision and successful CI run. Record outstanding native GUI and target-network OSM checks as issues instead of implying they passed. Publish alpha releases only after the release checklist's completion gates are satisfied.
