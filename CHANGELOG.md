# Changelog

All notable changes to this project will be documented in this file.

## [1.2.0] - 2026-07-28

### Fixed
- **`UnicodeEncodeError` when stdout is redirected.** On Windows a redirected
  stream defaults to the ANSI codepage, so printing a name containing Greek or
  accented characters killed the command. It worked interactively and failed
  only under `> out.txt`, which meant it only ever showed up in build scripts.
  All four subcommands were affected. Redirected streams are now reconfigured to
  UTF-8 with `backslashreplace`; a terminal keeps its own encoding and gains only
  the error handler.
- Encoding failures are no longer reported as parse errors. `UnicodeEncodeError`
  subclasses `ValueError`, so the existing handler caught it and printed a codec
  message *after* the DOT file had already been written — the command exited 1
  having actually succeeded.

### Added
- `--ascii` / `--no-ascii` (and `GEDGRAPH_ASCII`) to select ASCII decorations
  (`[OK]`, `[!]`, `|/-\`) for consoles whose fonts cannot draw braille or check
  marks. `GEDCOM_TOOLS_ASCII` is honoured as a fallback. Both flags must precede
  the subcommand.
- `.github/workflows/test.yml` — the project's first CI. Lint and format checks,
  a test matrix over Ubuntu × Windows and Python 3.11 × 3.13, a `pip-audit` job
  over runtime dependencies, and a job that specifically guards the redirected
  output bug above on both operating systems.
- Releases are now gated on that test suite: `publish.yml` calls the test
  workflow and will not build or publish if it fails.

### Changed
- **Dropped Python 3.10.** The floor is now 3.11.
- `ged4py` requirement widened from `~=0.4.4` to `>=0.5.2,<0.6`. The old pin
  forbade 0.5.x, which is what was actually installed and tested against.
- Dependabot groups GitHub Actions updates into a single pull request.

### Notes
- Gating the release adds roughly 4–6 minutes to a publish (previously ~43s).
  Nothing extra to do when cutting a release. Be aware, though, that GitHub
  creates the release object *before* the workflow runs, so if a gated release
  fails you are left with a published GitHub release and nothing on PyPI. Fix
  the cause, then re-run the failed jobs:
  `gh run list --workflow publish.yml` to find the run, then
  `gh run rerun <run-id> --failed`.

## [1.1.0] - 2026-03-05

### Added
- Braille-spinner progress feedback during CLI operations (`--verbose`, `-q/--quiet`, `--no-color` flags)
- `gedgraph/progress.py` — vendored progress module with `Colors`, `Spinner`, `PhaseTracker` classes
- `.github/dependabot.yml` — weekly GitHub Actions and pip dependency updates
- `.gitignore` entries for credential files (`*.pem`, `*.key`, `*.p12`, `*.env`)

### Changed
- Pinned `pypa/gh-action-pypi-publish` to immutable SHA in CI workflow
- `GedcomParser.load()` now properly cleans up on failure (fd leak fix)
- DOT label escaping fixed — components escaped individually, preventing double-escaping of `\n` line breaks
- DOT comment lines sanitized to strip control characters
- `write_text()` calls now specify `encoding="utf-8"` explicitly
- Pinned `ged4py~=0.4.4` (compatible release, 0.4.x only)
- Integration tests converted from `NamedTemporaryFile` to pytest `tmp_path` fixture

### Security
- Pinned CI action to SHA to prevent supply chain attacks
- Added Dependabot for automated dependency updates

## [1.0.0] - 2026-03-04

### Added
- Initial release as `kimon-gedgraph` on PyPI
- `pedigree` command — ancestor chart generation
- `relationship` command — shortest path between two individuals
- `hourglass` command — vertical ancestor/descendant or parental-split layout
- `bowtie` command — horizontal hourglass layout
- Smart path finding with BFS, prioritizing full-blood and male-line paths
- Spouse visualization with marriage status indicators (solid/dashed lines)
- GEDCOM name component support (NPFX, TITL, GIVN, SURN, NSFX)
- Date handling with fallback to baptism/burial dates
- GraphViz DOT output with color-coded nodes
- pip-installable package with `[dev]` extras
- CI workflow for automatic PyPI publishing on release
