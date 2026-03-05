# Changelog

All notable changes to this project will be documented in this file.

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
