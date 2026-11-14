# Changelog

All notable changes to this project will be documented in this file.

## [1.3.0] - 2026-11-13

### Fixed
- **A crafted GEDCOM name could put raw escape sequences into rendered charts.**
  Graphviz decodes HTML entities even in plain labels, so a name containing
  `&#27;` came out of `dot -Tplain` as a real ESC byte, and an SVG with such a
  name would not parse. `&` is now escaped. Bidi overrides, zero-width space,
  line separators and BOM are also stripped from names, so they cannot reorder
  or hide the rest of a summary line.
- An input or output path the file system rejects (too long, say) printed a
  Python traceback instead of a one-line error.
- **`ancestor-split` drew the mother's line on the father's side.** Hourglass
  and bowtie charts in this variant are supposed to put the two parental lines
  on opposite sides of the focal person; both ended up on the same side. The
  father's ancestors are now above (hourglass) or left (bowtie) of the focal
  person, and the mother's below or right.
- **Relationship descriptions were wrong for most relationships.** First
  cousins came out as "Collateral relatives (2th cousins)", a husband and wife
  as "Siblings", and an uncle and his nephew as "Ancestor via collateral (1 gen
  down)". The relationship is now named the way a genealogist would: father,
  grandmother, 2nd great-grandfather, son, sister, uncle, great-aunt, niece,
  first cousin once removed, and so on. Half-blood relationships get a `half-`
  prefix. Two people who are the couple of a family are husband/wife (or
  spouse) when it has a `MARR` record and partner when it does not, with or
  without children; any longer path through a marriage is a "relative by
  marriage". Sharing a child is not enough on its own: a child's birth father
  and adoptive father are relatives by marriage, not partners. When the sex of
  the person being described is not recorded, a neutral form is used: parent,
  sibling, parent's sibling, sibling's child.
- **Links recorded on only one side were ignored.** GEDCOM records each link
  twice, `CHIL` in the family and `FAMC` in the child, `HUSB`/`WIFE` in the
  family and `FAMS` in the spouse, and exporters do not always write both.
  1.2.1 took parents only from a child's first `FAMC` and children only from
  `CHIL` of the families in a parent's `FAMS`, so a child with no `FAMC` had no
  parents, a mother listed as `WIFE` but with no `FAMS` had no children, a father
  with `FAMS` but no `HUSB` line was missing as a parent, and a relationship
  could be found in one direction and not the other. Either side of a link is
  now enough.
- **Couples with no children were "No relationship found"**, and so was anyone
  related only through such a marriage. When there is no line of descent between
  the two people, a direct spouse is answered at once, and otherwise a second
  search also follows spouse links. Both happen only then, so no blood or
  adoptive result changes. The second search does not run when the first was
  cut off by the search limit or `--max-depth`, so an in-law route never stands
  in for a line of descent the search did not reach.
- **A couple with children was found through a child.** The search went down
  from one parent to a child and back up to the other, so the chart drew the
  child between them. A couple is now one step, "wife (1 step)" or "partner
  (1 step)", with the marriage line drawn. More generally, once a route goes
  down a generation it no longer climbs again: going down to a shared
  descendant and back up is not a line of descent, and `describe()` names such
  a path "relative by marriage". Two second cousins whose
  children married each other are "second cousin", not a 4-step route through
  their shared grandchild.
- When two people are related through a full-blood and a half-blood line of the
  same length, the chart could follow the half-blood line, and which line it
  took depended on the order the two ids were given. Equally short paths are now
  ranked by fewest adoptive, foster or step links, then a marriage line over a
  route down to a child and up to its other parent, then full blood before half
  blood, then male line.
- `-o` naming the input GEDCOM overwrote it with the chart. That is now a usage
  error (exit 2), including when the same file is named another way or through a
  hard link.
- A byte that is not valid in the file's encoding aborted the load with
  `UnicodeDecodeError`. It is now read as U+FFFD and the load continues.
- An empty `NAME` (`1 NAME` or `1 NAME //`) gave a blank label and summary; it
  now shows "Unknown", as a missing `NAME` already did.
- **Birth and death years were shown wrong or not at all.** `1 JAN 1950/51`
  showed no year, `BET 1900 AND 1910` showed 1910, and `ABT 1950` showed a bare
  1950 with nothing to say it was approximate. See *Changed* for how years are
  now displayed.
- **One unparseable date aborted loading the whole file.** ged4py raises
  `ValueError` on dates such as `@#DJULIAN@ 1 JAN 1700/01` (a dual year in a
  Julian date) or an unknown calendar escape like `@#DROMAN@ 1950`, and that
  error escaped the loader. Such dates are now kept: the Julian example shows
  1700 and `ABT @#DJULIAN@ 1700/01` shows `c. 1700`; the unknown calendar shows
  no year.
- Hebrew dates showed the Hebrew year as if it were Gregorian (`@#DHEBREW@ 5700`
  showed 5700). Dates in any calendar other than Julian or Gregorian now show no
  year, and the label falls back to the baptism or christening date, as it does
  for a missing birth date.
- A family with two `HUSB` (or two `WIFE`) lines, or two FAMS-only spouses of
  the same sex, kept only the first; the second lost their children and spouse.
  Same-sex couples now keep both.
- Half-sibling detection. Two families give half blood when they share one
  parent but not both. Children listed in the same family are never
  half-siblings, even when that family lacks a father or mother. Parents are
  compared as a set rather than father-to-father and mother-to-mother, since one
  person can be `HUSB` in one family and `WIFE` in another, and the same couple
  recorded in two duplicate `FAM` records still counts as full blood.
- Pedigree collapse pushed whole generations onto the wrong rows. When an
  ancestor appears at two depths (an uncle marrying his niece, a woman marrying
  her sibling's grandson) they are placed by the shorter line; the edge from the
  longer line is still drawn but no longer affects which row anyone is on.
- An individual whose xref is a DOT keyword (`@Node@`, `@EDGE@`, `@subgraph@`,
  etc.) produced a file GraphViz refused to render.
- Two different xrefs that escape to the same DOT id, such as `@K-1@` and
  `@K.1@`, were merged into a single node. This affected every chart type,
  including relationship charts.
- `relationship` with ids given without the `@` signs (`I6 I5`) drew the start
  person twice and lost the end person's colour. `RelationshipPath.start_id` and
  `end_id` are now always the `@I6@` form, whichever form was passed in.
- The CLI never closed the GEDCOM file it opened.
- Control characters from a GEDCOM file reached the terminal. A crafted name
  containing escape sequences could drive the terminal through the stdout
  summary line or an error message (ged4py quotes the offending line in parse
  errors). C0, DEL and C1 characters are now stripped there; DOT labels and
  comments, which already stripped C0 and DEL, now strip C1 as well.
- `make venv` failed on Debian and Ubuntu, which ship `python3` and no bare
  `python`. The Makefile now uses `PYTHON ?= python3`.
- `.gitignore` ignores `*.ged`, `*.GED` and `*.gedcom` outside `tests/fixtures/`,
  so a real family file dropped into the checkout is not committed by accident.
  It also covers more credential file patterns. CI checkouts no longer persist
  the GitHub token (`persist-credentials: false`).

### Changed
- **People marked private stay private.** A record with `RESN privacy` or
  `RESN confidential` is drawn as "Private" with no years and named "Private"
  in the summary line, with a neutral relationship word ("parent", not
  "father") and no sign of whether they married; a restricted birth or death
  event hides its year. 1.2.1
  ignored `RESN` and printed everything. `--include-private` restores that.
- Output files are written through a temporary file and a rename, readable by
  their owner only (0600); a failed write leaves the old file whole, and the
  output's directory must allow creating files. `-o` naming a symlink, FIFO or
  device (`/dev/stdout`, `/dev/null`) is now a usage error: the chart would have
  gone wherever it pointed, and with `/dev/stdout` the summary line was mixed
  into the DOT anyway.
- Names longer than 200 characters are cut short in labels and summary lines.
- Years in chart labels now say when they are inexact:

  | GEDCOM date | Shown as |
  |---|---|
  | `1 JAN 1950` | `1950` |
  | `1 JAN 1950/51` | `1950/51` |
  | `500 B.C.` | `500 BC` |
  | `ABT`, `EST`, `CAL 1950` | `c. 1950` |
  | `BET 1900 AND 1910` | `c. 1900` |
  | `BEF 1900` | `bef. 1900` |
  | `AFT 1900` | `aft. 1900` |
  | `FROM 1800 TO 1850` | `c. 1800` |
  | `TO 1910` | `bef. 1910` |
  | `FROM 1900` | `aft. 1900` |
  | `INT 1850 (about)` | `1850` |

  `FROM 1800 TO 1850` showed 1850 before, `TO` and `FROM` showed a bare year,
  and `500 B.C.` showed nothing. Years outside 1–9999 are not shown.

  A free-text date shows a year only when it ends in a three- or four-digit
  year and every word before that is a qualifier (`abt`, `about`, `circa`,
  `ca`, `c`, `approx`, `est`, `estimated`, `cal` give `c.`; `bef`, `before`
  give `bef.`; `aft`, `after` give `aft.`), an English month name, its
  three-letter abbreviation or `Sept`, a day number, or `born`/`b`. So
  `(born 1902)` now shows 1902 and `Abt. 1950` shows `c. 1950`, where both
  showed nothing. Anything else means no year: `Between 1840 and 1850`,
  `1850 or 1851`, and `Mai 1950`, which used to show 1950. Other numbers typed
  into the text are never taken for a year.
- **The relationship summary line has a new format.** It is now a sentence
  naming the relationship:
  `Relationship: Emily Smith is David Smith's sister (2 steps) -> out.dot`.
  It was `Relationship: David Smith to Emily Smith (2 steps) -> out.dot`. A
  one-step path says "1 step". The relationship chart's DOT comment carries the
  same sentence, replacing the two comment lines it had before. Anything that
  parses gedgraph's stdout needs updating.
- The DOT written for pedigree, hourglass and bowtie charts is structured
  differently, which matters if you post-process it. In `ancestor-split`, edges
  on the mother's side are written `child -> parent [dir=back]`, which is how
  they end up on the other side of the focal person while the arrows still point
  at the child. The `rank=same` groups are gone. Pedigree-collapse edges carry
  `constraint=false`. Node ids get a `_2`, `_3` suffix when two xrefs collide or
  when an ancestor appears on both the father's and the mother's side, and an
  id that would be a DOT keyword gets a `_` prefix, as ids starting with a digit
  already did.
- **Adoptive, foster and step links are followed and named.** 1.2.1 took a
  child's first `FAMC` as the birth parents whatever its `PEDI`, and ignored any
  other. Every `FAMC` is now followed. `PEDI adopted` and `PEDI foster` (any
  case) give an adoptive or foster prefix: "adoptive father", "foster mother",
  "adoptive sister"; `PEDI step` is a step link. Other `PEDI` values (`birth`,
  `sealing`, none) count as birth. A child in a family's `CHIL` list who has no `FAMC` to that family and
  a birth family elsewhere is a stepchild there: stepdaughter, stepfather, stepbrother. English has step-
  words only for those, so a longer step path is a "relative by marriage".
  Neither prefix is combined with `half-`. A path with links of two kinds is
  named by the looser one (step, then foster, then adopted), so it reads the
  same from either end: a stepfather's adopted son is a stepbrother. These links are drawn as dotted
  arrows in every chart type. When a parent is linked to the same child both
  by birth and some other way, the arrow is solid.
- Pedigree, hourglass and bowtie charts take a person's parents from the first
  birth family rather than the first `FAMC`; adoptive or foster parents are
  used only when there is no birth family. They now trace the birth line where
  1.2.1 followed an adoptive `FAMC` that happened to be listed first.
- `DotGenerator.generate_relationship(paths, comment)` takes the summary line
  to put in the chart's comment. The chart used to build its own, without the
  caveat the CLI adds when the search was cut short, so the `.dot` file stated
  as fact what the summary line hedged. Breaking: a 1.2.1-style call with one
  argument raises `TypeError`.
- `generate_hourglass()` and `generate_bowtie()` raise `ValueError` for a
  variant other than `ancestor-split` or `descendants`; `pedigree` used to
  give an ancestors-only chart under an Hourglass or Bowtie heading.
- When the relationship search stops short, the CLI used to report "No
  relationship found". At the search limit it now exits with
  `Error: search limit reached looking for I1 -> I2`, and when `--max-depth`
  stopped it with people still unvisited one step further, with
  `Error: --max-depth 15 reached looking for I1 -> I2`. If either limit was hit
  but the two are spouses, the spouse is still reported and the summary line
  ends in `(search limit reached; a blood relationship may have been missed)`
  or `(--max-depth reached; a blood relationship may have been missed)`.
- The search limit is now 200,000 search states, each person counting at most
  twice (once on the way up, once after a step down). It was 100,000 queue
  entries, and a person was queued again for every shortest route to them, so a
  heavily intermarried tree could use up the limit long before it had looked
  at 100,000 people. Every equally short path is still kept, up to 10,000.
- `get_sex()` returns one upper-case letter whatever the file wrote: `SEX Male`
  and `SEX m` give `M`, and a `SEX` line with no value gives `None`. It used to
  return the value as written, so anything comparing it with `"M"` treated
  `SEX Male` as unknown.

### Added
- `--version`.
- `--include-private`, and `GedcomParser(path, include_private=False)` with
  `is_private()`.
- CodeQL and zizmor in CI, a gitleaks pre-commit hook, and a seven-day
  Dependabot cooldown.
- Python 3.14 support. CI now tests 3.11 and 3.14 on Linux and Windows.
- `GedcomParser.is_couple_married()` is public (was `_is_couple_married`). It
  is true when any family with the two as its couple has a `MARR` record; it
  used to check only the first such family.
- `gedgraph.kinship`: `describe()` names the relationship a path describes and
  `sentence()` builds the summary line.
- `pathfinder.is_half()`, which says whether a path is half blood.
- `GedcomParser.parent_links()` and `child_links()` (each person with the
  family and the kind of link: birth, adopted, foster or step), `spouses()`,
  `couple()`, `half_blood()`, and `parent_family()` (the family and link kind
  a person's parents are taken from).
- `RelationshipPath.ids()`, `PathFinder.truncated` (set when the last search
  hit the search limit), `PathFinder.depth_limited` (set when `max_depth`
  stopped it with someone unvisited one step further), and `PathStep.link` and
  `PathStep.family`.
- `dotgen.strip_control()`.

### Removed
- `PathFinder.find_pedigree()`, `find_pedigree_split()`,
  `find_pedigree_with_generations()` and `find_descendants()`, along with the
  private `_bfs_traverse()` behind them, and
  `RelationshipPath.generation_distance()`. This is a breaking change to public
  methods in a minor release. Chart generation stopped using them when it was
  rewritten to fix the `ancestor-split` layout, nothing else in the project
  calls them, and no outside code is known to. If you do use them, pin
  `kimon-gedgraph<1.3`.
- `PathStep.is_full_blood`, `RelationshipPath.sorting_key()` and
  `dotgen.COLOR_PATERNAL`, and `dotgen.COLOR_MATERNAL` is renamed
  `COLOR_SPOUSE` (it only ever coloured spouses). Breaking for the same reasons
  as above. Whether a path is half blood depends on the whole path, not on one
  step, so it is now `pathfinder.is_half()`, and paths are ranked inside
  `PathFinder`. `PathStep` takes `individual_id`, `is_parent` and `via_male`
  positionally, and `link` and `family` only as keywords, so a 1.2.1-style call
  with four positional arguments raises `TypeError`.
- `GedcomParser.get_parents()`, `get_children()`, `get_families_as_spouse()`,
  `is_half_sibling()`, `is_full_sibling()` and `get_spouse_for_child()`.
  Nothing in gedgraph used them any more, and `is_half_sibling()` could
  disagree with the half-blood naming the relationship search does. Use
  `parent_family()` with `couple()`, `child_links()`, `spouses()` and
  `half_blood()`. Breaking for the same reasons as above.

## [1.2.1] - 2026-07-28

### Fixed
- **Records with no cross-reference id silently discarded each other.** Every
  such record was indexed under the same `None` key, so in a file containing
  more than one, all but the last were dropped. They are now skipped at load —
  a record with no xref id cannot be referenced by any `FAM` link, so it can
  take part in no relationship and was never reachable to begin with.
- `is_half_sibling()` returned `None` instead of `False` when an individual had
  no recorded mother or father. Both values are falsy, so `if` checks behaved
  correctly, but `result is False` did not.
- `make clean` exited non-zero. `find -delete` implies `-depth`, which makes the
  preceding `-prune` a no-op; some `find` implementations reject the combination
  outright. It only surfaced when both `.venv` and a `.pyc` file were present.

### Changed
- `get_individual()`, `_get_family()` and `find_pedigree_with_generations()`
  accept `str | None` and return `None`/empty for `None`. ged4py's
  `Record.xref_id` is optional, so callers routinely hold an id that may be
  missing; this is a widening and no existing call breaks.
- `mypy` is now a CI gate, with `check_untyped_defs` enabled. New functions must
  be annotated — mypy skips the body of any function without annotations, which
  had left the CLI entry point and the GEDCOM loading routine unchecked.

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
