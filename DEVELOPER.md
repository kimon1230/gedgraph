# Developer Documentation

## Architecture

GedGraph is structured as a modular Python application with clear separation of concerns:

```
gedgraph/
├── __init__.py       # Package metadata and version
├── __main__.py       # Entry point for `python -m gedgraph`
├── parser.py         # GEDCOM file parsing and queries
├── pathfinder.py     # Relationship path finding algorithms
├── kinship.py        # Plain-English names for a relationship path
├── dotgen.py         # GraphViz DOT file generation
├── progress.py       # Progress indicators, Unicode/ASCII glyph sets (vendored from gedcom_tools)
└── cli.py            # Command-line interface
```

## Core Modules

### parser.py - GEDCOM Parsing

**Purpose**: Parse GEDCOM files and provide query methods for individuals and relationships.

**Key Classes**:
- `GedcomParser`: Main parser class using ged4py library

**Key Methods**:
- `load()`: Parse GEDCOM file into memory. Each call starts from empty
  indexes, so loading again forgets the previous file; if loading fails (any
  exception, `KeyboardInterrupt` included) the reader is closed and the
  indexes are left empty rather than half built
- `get_individual(xref_id)`: Retrieve individual by ID. Accepts `str | None` and
  returns `None` for `None` — ged4py's `Record.xref_id` is optional, so callers
  routinely hold one that may be missing
- `GedcomParser(path, include_private=False)`: with `include_private` off, a
  person whose record has `RESN privacy` or `RESN confidential` (GEDCOM 7 lists
  such as `CONFIDENTIAL, LOCKED` count) is "Private" with no years, and a
  restricted birth or death event hides its year
- `is_private(individual)`: The rule above, for one person
- `get_name(individual)`: Format name using NPFX/TITL GIVN SURN NSFX sequence,
  cut to 200 characters
- `get_birth_year()`, `get_death_year()`: Display year of birth (falling back to
  BAPM, then CHR) or death (falling back to BURI), formatted by `_event_year()`.
  A restricted event stops the search: a baptism year would give away the birth
  year it stands in for
- `parent_family(individual)`: `(family xref, link)` of the preferred family of
  origin: the first birth family with at least one parent, else the first
  family of any kind with one; `None` if there is none
- `get_sex(individual)`: One upper-case letter (`SEX Male` and `SEX m` give
  `M`), or `None` when there is no SEX value
- `parent_links(individual)`, `child_links(individual)`: `(person, family xref,
  link)` for every parent in every family of origin, or every child of every
  family as spouse. `link` is `birth`, `adopted`, `foster` or `step`
- `spouses(individual)`: The other partner of each family as spouse
- `couple(fam_xref)`: `(husband, wife)` xrefs of the family's slots; the husband
  slot drives male-line ranking and both feed the relationship chart's other parent
- `is_couple_married(ind1, ind2)`: True if any family with the two as its
  couple has a MARR record; always False when either is private, since the
  marriage is that person's event too
- `half_blood(fam1, fam2)`: False when either is `None` or they are the same
  family (children of one family are never half-siblings, whatever parent it
  lacks); otherwise True when the parent sets overlap without being the same
  pair. Sets, not father-to-father, because one person can be HUSB in one
  family and WIFE in another; a couple split across duplicate FAM records still
  counts as full blood

**Link indexes** (`_build_links()`, run by `load()`): GEDCOM records each
link from both ends (`CHIL`/`FAMC`, `HUSB`/`WIFE`/`FAMS`), and either end alone
is enough. `_index_families()` reads the FAM records (HUSB/WIFE slots and CHIL
lists), `_index_individuals()` reads each INDI's FAMC, FAMS and SEX and seats
FAMS-only spouses, and `_build_links()` joins the two:
- `_couple[fam]`: `[husband, wife]`. Filled from HUSB/WIFE first (a second
  HUSB or WIFE line takes the other slot if it is free: a same-sex couple),
  then from FAMS: a spouse not already in the couple takes the slot for their
  SEX if it is empty. Spouses with no M/F sex, and a second spouse of the same
  sex, are placed last in whatever slot is free (wife slot if free, else the
  husband slot, so unknown sex counts as the male line only when partnered with
  a woman); anyone left over is left out. A FAMS whose slot the family's own
  HUSB/WIFE line already filled is a stale pointer and is ignored
- `_famc_links[indi]`: `(family, link)` for each family of origin. FAMC gives
  the link from its `PEDI`, case-insensitively; `adopted`, `foster` and `step`
  count as such, anything else is `birth`. A family that lists the person as CHIL with
  no FAMC back is `step` if they have a birth family elsewhere, else `birth`
- `_fam_children[fam]`: `(child, link)`, CHIL order first, then FAMC-only children
- `_spouse_fams[indi]`: families where the person is in `_couple`

Pointers to missing records are dropped. Read pointers as the xref string in
the `.value` of the unresolved pointer record, walking `sub_records` (or
`sub_tag(..., follow=False)`); ged4py's default `follow=True` re-reads the
target record from disk on every call.

**Year display** (`_event_year()`, module level): exact dates give the year
(`1950`, dual `1950/51`, `500 BC`); ABT/EST/CAL, BET...AND and FROM...TO give
`c.` and the first year; BEF and TO give `bef.`, AFT and FROM give `aft.`; INT
gives the bare year. Free text goes through `_phrase_year()`: the last word must
be a three- or four-digit year (an optional `/NN` dual suffix is dropped), and
every earlier word must be a qualifier (`abt`, `circa`, `bef`, `after`, ...,
which sets the `c.`/`bef.`/`aft.` prefix), an English month or its
abbreviation, `sept`, a day number, `born` or `b`; anything else gives `None`.
ged4py reads a short word before a year as a month (`Mai 1950`), so a simple
date whose month is not a GEDCOM one is sent through `_phrase_year()` too.
Hebrew, French Republican and unrecognised `@#D...@` calendars, and years
outside 1–9999, give `None`. `tests/test_parser.py::DATE_CASES` against
`fixtures/dates.ged` is the reference.

**Unparseable dates**: ged4py raises `ValueError` from `Date.freeze()` on dates
it cannot parse (a dual year in a Julian date, an unknown calendar escape),
which used to abort the whole load. `_Reader` overrides the private
`GedcomReader._make_record` to swap in `_TolerantDate`. For a Julian date it
drops the dual-year suffix and parses again, so `ABT @#DJULIAN@ 1700/01` keeps
its qualifier; anything still unparseable is kept as a phrase. Both hooks are
private ged4py API, which is why the `ged4py` pin stays `<0.6`. `_Reader` is
opened with `errors="replace"`, so a byte that is invalid in the file's
encoding becomes U+FFFD instead of aborting the load.

**Implementation Notes**:
- Individuals and families are loaded at initialization and kept in memory
- GedcomReader stays open to allow lazy resolution of references
- Records **without** an xref id are skipped at load. They cannot be referenced
  by any `FAM` link, so they can take part in no relationship; indexing them
  would collide every such record onto a single `None` key and silently discard
  all but the last
- Individuals cached in `_individuals` dict for O(1) lookup
- Families cached in `_families` dict
- Accepts IDs with or without @ symbols for convenience
- Name parsing checks GEDCOM sub-tags (NPFX, TITL, GIVN, SURN, NSFX) before
  falling back to parsed tuple; a missing or empty NAME gives "Unknown"
- Marriage detection checks for MARR tag in family records

### pathfinder.py - Relationship Path Finding

**Purpose**: Find relationship paths between individuals using graph traversal.

**Key Classes**:
- `PathFinder`: BFS-based path finding. Two flags describe the last search and
  are reset on every call. `truncated` is True when it stopped at the search
  limit (`_MAX_NODES`, 200,000 search states). The level that reaches the end
  person is always finished, so the cap only fires before any path is found.
  `depth_limited` is True when `max_depth` ran out with someone not yet reached
  one step further; running out with nobody left to reach does not set it.
  When either is set after the blood search, the marriage search does not run;
  only a direct spouse is still returned
- `RelationshipPath`: `steps`, `start_id`, `end_id`; `ids()` is the start id
  followed by each step's person
- `PathStep`: One step. Positional: `individual_id` (the person stepped to),
  `is_parent` (True going up to a parent), `via_male` (the parent in this step
  holds the family's husband slot). Keyword-only: `link` (`birth`, `adopted`,
  `foster`, `step` or `spouse`) and `family` (the FAM xref the step went
  through; `None` for a spouse step)

**Algorithm**:
- Breadth-first search, one level at a time, up to parents and down to children
  through `parent_links()`/`child_links()`, so adoptive, foster and step links
  are steps too. Where the same neighbour is reachable by several links, the
  birth link is kept
- The search runs over states `(person, descended)`, where `descended` says
  whether the route has gone down a generation yet. Each state is expanded
  once, so a person costs at most two states however many shortest routes lead
  to them. Every predecessor at the previous level is recorded, and
  `_unwind()` rebuilds every tied shortest path from those lists, up to
  `_MAX_PATHS` (10,000)
- The blood search never climbs after a step down: up, down, or up then down
  are the only shapes it produces. A route down to a shared descendant and up
  again (two people whose children married) is not a line of descent. A
  descended state is also dropped when the same person was already reached by
  climbing at an earlier level, since that copy can do everything the
  descended one can; a tie in the same level is kept as another route
- Two phases. The first search follows parent and child links only. If it
  finds nothing, a direct spouse is returned as a one-step path, keeping
  `truncated` and `depth_limited` if the first search was cut off. That covers
  every couple, with or without children, since the blood search cannot go
  down to a child and back up. Otherwise, unless the first search was cut off,
  a second search also steps to spouses (`link="spouse"`) and may go up and
  down freely. That is what finds in-laws; because it runs only when there is
  no line of descent, it cannot change a blood or adoptive result

**Path ranking** (`_rank()`), lowest first:
1. Length
2. Number of adopted, foster or step steps (spouse steps do not count)
3. Turns from a child step straight into a parent step, so a marriage edge
   beats a route down to a child and up to its other parent
4. `is_half()`: full blood before half blood
5. Number of steps not via the husband slot (male line first)

**Key Methods**:
- `find_relationship_paths()`: Every path found between two individuals.
  Accepts ids with or without `@`; the returned paths carry the canonical
  `@X@` xref in `start_id`/`end_id`
- `get_shortest_paths()`: The paths that tie for the best `_rank()`
- `_get_neighbors()`: One step per neighbouring person; spouses are added only
  in the second phase
- `is_half(path, parser)` (module level): True for a birth-only path that goes
  up then down when `parser.half_blood()` says the families of the last
  up-step and the first down-step (the two lines from the common ancestor) are
  half blood. Used by `_rank()` and `kinship.describe()`

### dotgen.py - GraphViz Generation

**Purpose**: Generate DOT format files for visualization.

**Key Classes**:
- `DotGenerator`: Creates DOT syntax for charts

**Key Methods**:
- `generate_pedigree()`: Create pedigree chart DOT file (ancestors only)
- `generate_hourglass()`: Create hourglass chart DOT file (vertical split)
- `generate_bowtie()`: Create bowtie chart DOT file (horizontal split)
- `generate_relationship(paths, comment)`: Relationship chart for `paths[0]`, with the
  other parent beside each step up; `comment` is the CLI's summary line, caveats included
- `_format_label()`: Name plus `(birth - death)`, with `?` for a missing birth year
- `_build_chart()`: Breadth-first walk around the focal person for pedigree,
  hourglass and bowtie. Returns `_Node` and `_Edge` lists. Each node is one
  (side, person) pair, so in `ancestor-split` someone on both the father's
  (`"p"`) and mother's (`"m"`) side gets two nodes. Each edge keeps its link
  kind (`birth`, `adopted`, `foster`, `step`). When the same parent-to-child
  edge comes up through two families (a birth child in one, an implied step
  child in another), the birth link wins
- `_render_chart()`: Writes the DOT for pedigree/hourglass/bowtie from those lists
- `_header()`, `_couple_lines()`, `_require()`: The shared graph preamble, the
  couple edge plus its `rank=same` line, and the individual lookup that raises
  `ValueError` for an unknown id
- `strip_control()`: Removes C0, DEL and C1 control characters; used for DOT
  text and for anything the CLI prints

The relationship chart's comment is the summary line the CLI passes to
`generate_relationship()`: `kinship.sentence()` plus any search-limit caveat.

**Node ids**: `_NodeIds` turns xrefs into DOT ids (`@I1@` -> `I1`). Ids that
start with a digit or are a DOT keyword (`node`, `edge`, `graph`, `digraph`,
`subgraph`, `strict`, any case) get a `_` prefix; when two xrefs escape to the
same id (`@K-1@`, `@K.1@`), or one person appears on both sides of a split
chart, later ones get `_2`, `_3`, ...

**Chart Types**:
- **Pedigree**: Ancestors only, top-to-bottom layout
- **Hourglass**: Two variants with vertical layout (rankdir=TB)
  - `ancestor-split`: Father's ancestors above root, mother's ancestors below root
  - `descendants`: Ancestors above root, descendants below root
- **Bowtie**: Two variants with horizontal layout (rankdir=LR)
  - `ancestor-split`: Father's ancestors left of root, mother's ancestors right of root
  - `descendants`: Ancestors left of root, descendants right of root
- **Relationship**: Path between two individuals with spouses

**DOT Generation**:
- Uses `rankdir=TB` (top-to-bottom) for pedigree, hourglass, and relationship charts
- Uses `rankdir=LR` (left-to-right) for bowtie charts
- Color codes nodes: lightcoral (start/root), lightblue (end), lightgreen (bloodline), lightyellow (spouses)
- Pedigree, hourglass and bowtie charts have no `rank=same` groups; rows come
  from the parent-child edges alone
- In `ancestor-split`, the mother's side is drawn by reversing its edges:
  `child -> parent [dir=back]`. dot ranks an edge's tail before its head, so
  the parent lands below/right of the child while the arrow still points at the
  child
- Pedigree collapse: an edge whose parent is not exactly one generation above
  the child (an ancestor reached first by a shorter line) gets
  `constraint=false`, so it is drawn but does not drag whole generations onto
  the wrong row
- Relationship charts: spouse nodes (`COLOR_SPOUSE`) positioned using
  `{rank=same; ...}`; marriage status shown by line style, solid (married) or
  dashed (unmarried); spouse lines use `dir=none` and `constraint=false`. A
  spouse step on the path itself is drawn the same way. The spouse shown next
  to a parent on the path comes from the family that step went through, which
  for an adoptive or step link is not the child's birth family
- Adoptive, foster and step links are drawn `style=dotted` in every chart type
- Comments: the focal person's name (hourglass/bowtie), the name and
  ` - N generations` (pedigree), or the caller's summary line, caveats
  included (relationship)

### kinship.py - Relationship Names

**Purpose**: Name the relationship a `RelationshipPath` describes.

- `describe(path, parser)`: The end person's relationship to the start person,
  or `None` for an empty path. The path is reduced to runs of up-steps and
  down-steps. Up only, down only, or up then down is a blood relationship:
  father/grandmother/2nd great-grandfather, son/granddaughter, brother/sister,
  uncle/great-aunt, nephew/niece, and cousins with degree and removal ("first
  cousin once removed", "second cousin 3 times removed").
  `pathfinder.is_half()` decides a
  `half-` prefix. A path with an adopted or foster step gets an "adoptive" or
  "foster" prefix on any term; a step-link path is stepfather/stepson/
  stepbrother when it is one parent, child or sibling step and "relative by
  marriage" when longer. Neither is ever combined with `half-`. A path mixing
  link kinds is named by the loosest (step, then foster, then adopted), so it
  reads the same from both ends. A single spouse
  step is husband/wife/spouse if `is_couple_married()`, otherwise partner; any
  longer path with a spouse step is "relative by marriage". Any other shape,
  including down then up (two people sharing a child), is "relative by
  marriage"; `PathFinder` returns a couple as a one-step spouse path, so such
  a path joins two people who are not a couple, such as a child's birth father
  and adoptive father. With no recorded sex the neutral words are
  parent, child, sibling, spouse, and "parent's sibling" / "sibling's child"
  for uncle/aunt and nephew/niece, which have no single neutral word
- `sentence(start, end, term, steps)`: The summary line, e.g.
  `Emily Smith is David Smith's sister (2 steps)` with the *end* person as the
  subject. Used for both the CLI output and the relationship chart's comment

### cli.py - Command Line Interface

**Purpose**: Provide user-friendly CLI using argparse.

**Commands**:
- `pedigree`: Generate ancestor chart
- `relationship`: Generate relationship chart between two individuals
- `hourglass`: Generate hourglass chart (vertical split layout)
- `bowtie`: Generate bowtie chart (horizontal split layout)

**Common Options**:
- `-o, --output`: Output DOT file path (required for all commands). Written by
  `_write_output()` through a temporary file in the same directory and a rename,
  so the directory must allow creating files. `main()` refuses a path that is a
  symlink or an existing non-regular file (`/dev/stdout`, `/dev/null`, a FIFO):
  the chart would go wherever it points. A link planted after that check is
  replaced by the rename, not followed. A failed write keeps the old file, and
  the new file is owner-only (0600)
- `--include-private`: Show `RESN`-restricted people and events
- `-g, --generations`: Number of generations (default: 4, used by pedigree/hourglass/bowtie)
- `-d, --max-depth`: Maximum search depth, 1-50 (default: 50, used by relationship)
- `-v, --variant`: Chart variant (used by hourglass/bowtie)
  - `ancestor-split`: Split by parental lines
  - `descendants`: Split by ancestors/descendants

**Global Flags** (must precede the subcommand name):
- `--version`: Print `gedgraph <version>` and exit
- `--verbose`: Show detailed progress with timing
- `-q, --quiet`: Suppress progress output (spinner phases on stderr)
- `--no-color`: Disable colored output
- `--ascii` / `--no-ascii`: Select ASCII or Unicode decorations

**Progress Feedback**:
- Each command runs through 3 phases: Loading GEDCOM, Generating/Finding chart, Writing output
- Progress is displayed on stderr via `PhaseTracker` from `progress.py`
- In quiet mode, all spinner output is suppressed; the stdout summary line is always emitted
- Names in the summary line and error messages go through `strip_control()`, so
  escape sequences in a crafted GEDCOM cannot reach the terminal. It also drops
  bidi controls, zero-width space, line/paragraph separators and BOM, which
  could reorder or hide the rest of a line; ZWNJ/ZWJ stay for the scripts that
  need them. DOT labels additionally escape `&`, because Graphviz decodes HTML
  entities even in plain labels and `&#27;` would otherwise come out as ESC
- The `GedcomParser` is closed in a `finally` block whatever the outcome
- Non-TTY environments (pipes, redirects) degrade gracefully — no animation, just final status

**Stream Hardening** (`_harden_streams()`):

Called as the first statement of `main()`, before the parser is built, because
argparse writes `--help` and usage errors from inside `parse_args()` and then
exits.

- A redirected stream is reconfigured to UTF-8 with `backslashreplace`. Windows
  picks the ANSI codepage for redirected streams, which cannot encode most
  non-Latin names.
- A TTY keeps its own encoding and gains only the error handler — forcing UTF-8
  onto a cp1252 console produces mojibake.
- `PYTHONIOENCODING` is respected. The bail-out tests whether the *error handler
  field* is non-empty, not whether the string contains a colon: `cp1252:` names
  no handler and still needs hardening.
- Only the real interpreter streams are touched (`sys.stdout is sys.__stdout__`),
  so pytest's capture is never mutated session-wide.
- Idempotence is tracked per stream, so a call that hardens stdout cannot lock
  stderr out of a later one.

`UnicodeEncodeError` subclasses `ValueError`, so `cli.py` catches it *before* the
broad handler — otherwise an encoding failure is reported as a parse error.

**Glyph Selection** (`progress.py`):

`GlyphSet` pairs a Unicode and an ASCII rendering of the check, cross, arrow and
spinner frames. Selection is a switch rather than a detection: nothing about a
stream reveals whether the terminal's font can draw braille. `_ascii_forced` is
tri-state (`None` defers to `GEDGRAPH_ASCII`, then `GEDCOM_TOOLS_ASCII`), which
is what lets `--no-ascii` override an exported environment variable.

Note that the ASCII frame string is shorter than the Unicode one, so the frame
counter must be bounded by the *active* set (`len(self.glyphs.frames)`).

**Error Handling**:
- Validates GEDCOM file exists
- Rejects an `-o` that is the input GEDCOM, by `Path.samefile()` so another
  spelling or a hard link is caught too (argparse usage error, exit 2)
- Validates individual IDs exist
- With no path, reports `search limit reached` when `PathFinder.truncated` is
  set, else `--max-depth N reached` when `PathFinder.depth_limited` is set, else
  that no relationship was found. A path found despite a limit (only the
  direct-spouse shortcut can do this) gets
  `(search limit reached; a blood relationship may have been missed)` or
  `(--max-depth reached; a blood relationship may have been missed)` on the
  summary line
- Exits with appropriate error codes

## Development Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

## Testing

### Test Structure

```
tests/
├── fixtures/
│   ├── sample.ged            # Sample GEDCOM for testing
│   ├── sample_special.ged    # Names with characters needing DOT escaping
│   ├── non_ascii_names.ged   # Greek names — encoding regression fixture
│   ├── dates.ged             # One individual per date form (see DATE_CASES)
│   ├── layout.ged            # Families for chart layout and node-id tests
│   ├── collapse.ged          # Pedigree collapse at uneven depths
│   ├── links.ged             # One-sided links, PEDI, step children, childless couples
│   └── fullhalf.ged          # Cousins related through both a full and a half line
├── conftest.py               # Shared fixtures
├── test_parser.py            # Parser unit tests, including year display
├── test_pathfinder.py        # Path finding unit tests
├── test_kinship.py           # Relationship naming
├── test_dotgen.py            # DOT generation unit tests
├── test_layout.py            # Renders charts with GraphViz and checks placement
├── test_progress.py          # Progress indicators and glyph selection
├── test_cli.py               # CLI flag parsing and wiring tests
├── test_stream_hardening.py  # stdout/stderr encoding behaviour
└── test_integration.py       # End-to-end CLI tests (subprocess)
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_parser.py -v

# With coverage
pytest tests/ --cov=gedgraph --cov-report=html

# Single test
pytest tests/test_parser.py::test_get_individual -v
```

**Check the exit code, not just the summary.** pytest is configured
(`filterwarnings` in `pyproject.toml`) to turn `ResourceWarning` and unraisable
exceptions into errors, which catches an unclosed GEDCOM reader. The warning
fires at garbage collection, so it can fail whichever test happens to be
running, or appear as an internal error below an all-passed summary. Rerun the
suspect module with `PYTHONTRACEMALLOC=10` to see where the object was created.

**Layout tests** (`test_layout.py`) render charts with GraphViz `dot -Tplain` and
check where nodes end up: father's side opposite mother's, parents on the
correct side of their child, one row per generation. The tests that render
(those taking the `dot_bin` fixture) are skipped when `dot` is not on `PATH`;
the rest of the module (checks on the DOT text, and tests of the skip logic
itself) always runs. Set
`GEDGRAPH_REQUIRE_DOT=1` to make a missing `dot` a failure instead; CI does
this on its Linux legs.

### Test Fixtures

The `sample.ged` file contains:
- 10 individuals across 4 generations
- Various relationships (parent-child, siblings, cousins)
- Birth and death dates for testing date parsing
- Both connected and disconnected individuals

The `non_ascii_names.ged` file contains 5 individuals and 2 families with Greek
names (surname `Ανδρέου`), arranged so `@I1@` is a grandchild of `@I5@` — which
gives every subcommand something to walk, including a known 2-step relationship
path. Greek specifically, not accented Latin: a name like `Müller` encodes
cleanly in cp1252 and would not reproduce the bug this fixture exists for.

Tests that exercise encoding install stream doubles built as `TextIOWrapper`
subclasses over `BytesIO` with `write_through=True` — never `Mock`, since the
helpers read `.buffer.getvalue()` and a live `.encoding`. They must patch both
`sys.stdout` **and** `sys.__stdout__`, or the identity guard in
`_harden_streams()` skips the stream and the assertions pass vacuously.

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make venv` | Create virtual environment in `.venv/` with `python3` (override with `make venv PYTHON=...`) |
| `make install` | Upgrade pip and install package in editable mode with dev deps |
| `make test` | Run test suite with pytest |
| `make lint` | Check linting (ruff), formatting (black) and types (mypy) |
| `make fmt` | Auto-format code with black |
| `make audit` | Audit dependencies for known vulnerabilities |
| `make build` | Build distribution packages |
| `make clean` | Remove build artifacts and `__pycache__` directories |
| `make distclean` | Run `clean` and also remove the virtual environment |

## Code Quality

### Tools

- **black**: Code formatting (line length: 100) — capped in the `dev` extra
- **ruff**: Fast Python linter — capped in the `dev` extra
- **pip-audit**: Dependency vulnerability scanning — capped in the `dev` extra
- **pytest**: Testing framework — capped in the `dev` extra, with pytest-cov and build
- **zizmor**: Workflow linter, run by the `quality` job (installed there, capped)
- **gitleaks**: Secret scanner, as a pre-commit hook in `.pre-commit-config.yaml`.
  Enable it once with `pip install pre-commit && pre-commit install`
- **mypy**: A CI gate — capped in the `dev` extra. Configured in
  `[tool.mypy]` with `files = ["gedgraph"]`, so run it as bare `mypy`; passing a
  path on the command line overrides that config and lets local and CI diverge.

black, ruff, mypy, pip-audit and zizmor are version-capped because CI gates on them, and
pytest, pytest-cov and build because they run inside the release workflow
(`publish.yml` installs build with the same cap). A new lint
rule, formatting release or sharper type inference should be adopted
deliberately, not arrive as a red build on an unrelated change.

**`check_untyped_defs` is enabled**, which matters when adding code: mypy
normally skips the body of any function with no annotations, so an unannotated
helper would be exempt from checking entirely. That is how `cli.main()` and
`GedcomParser.load()` — the CLI entry point and the routine that reads every
record — went unchecked for as long as they did. Annotate new functions, or the
gate will reject them.

## Continuous Integration

`.github/workflows/test.yml` runs on pull requests and pushes to `main`:

| Job | Coverage |
|-----|----------|
| `quality` | `ruff check .`, `black --check .`, `mypy`, and zizmor over the workflows, on Python 3.13 |
| `audit` | `pip-audit` over runtime dependencies only, on 3.11 and 3.14 |
| `test` | pytest on Ubuntu × Windows, Python 3.11 × 3.14; GraphViz is installed and `GEDGRAPH_REQUIRE_DOT=1` set on Ubuntu only, so the Windows legs skip the layout tests that render with `dot` |
| `redirected-output` | Real shell redirection on both operating systems |

**Why `redirected-output` is a separate job**: it reproduces the original bug the
way a user hit it — a real `>` redirect, not a pipe from pytest. The steps use
`shell: bash` deliberately, because `windows-latest` defaults to PowerShell,
which decodes a native command's stdout through the OEM codepage and re-encodes
it into the redirect target. Under PowerShell the UTF-8 assertion would fail
against perfectly correct code.

**Why `audit` installs runtime dependencies only**: auditing the `[dev]` tree
would turn an unrelated pull request red whenever a test-only package publishes
a CVE, and this job is meant to block. `pip-audit .` (project-path mode) resolves
from `pyproject.toml` rather than auditing the installed environment, which would
otherwise include pip-audit's own dependency tree.

`.github/workflows/codeql.yml` runs CodeQL on Python for pull requests, pushes to
`main` and weekly. It is a workflow of its own because `publish.yml` calls
`test.yml`, and a called workflow cannot hold `security-events: write` unless the
release job grants it too.

Dependabot waits seven days before proposing a new release (`cooldown`), and
proposes `pypa/gh-action-pypi-publish` in a PR of its own: that action mints the
PyPI upload credential.

`.github/workflows/publish.yml` calls `test.yml` and gates `release-build` on it,
so a release cannot ship untested. Note that GitHub creates the release object
before the workflow runs: if a gated release fails, the release exists but
nothing reached PyPI. Fix the cause, then
`gh run list --workflow publish.yml` and `gh run rerun <run-id> --failed`.

## Adding New Features

### Adding a New Chart Type

1. Add new generation method in `dotgen.py` (e.g., `generate_newchart()`)
   - Build the node and edge lists through `_build_chart()`, adding a variant
     there if the existing walks don't fit
   - Render with `_render_chart()`, choosing rankdir
2. Add new subcommand in `cli.py`
   - Create the subparser in `_build_arg_parser()`
   - Generate and print the summary line in `_chart()` (or a function of its
     own, as `_relationship()` is), which `main()` dispatches to
   - Add error handling and user feedback
3. Add tests in `tests/test_dotgen.py`
   - Test successful generation
   - Test error cases
   - Verify DOT output contains expected elements
4. If the chart is built by `_build_chart()`, add rows to `CHARTS` in
   `tests/test_layout.py`. Each row is `(fixture, chart, focal, variant,
   generations)` and runs the structural checks (edge direction, no duplicate
   nodes or edges, the focal person drawn once) and the rendered check that
   parents land on the correct side of their child.
   The `_chart()` helper there picks the rankdir and comment from the chart
   name (LR only for `bowtie`) and the `parsers` fixture loads only
   `sample`, `layout` and `collapse`, so a new chart type or fixture may need
   those updated too
5. Update README.md and DEVELOPER.md with usage examples

**Example**: The hourglass and bowtie charts share common infrastructure:
- Both use `_build_chart()` to collect nodes and edges, each node tagged with
  its side and generation
- Both use `_render_chart()` for DOT generation, which flips the mother's-side
  edges (`child -> parent [dir=back]`) and marks collapse edges
  `constraint=false`
- They differ only in rankdir: TB (hourglass) or LR (bowtie)
- Both support `ancestor-split` and `descendants` variants

### Adding New Relationship Metrics

1. Add new method to `PathFinder` class, or a function in `kinship.py` if it
   only interprets an existing path
2. Update `RelationshipPath` dataclass if needed
3. Add tests in `tests/test_pathfinder.py` or `tests/test_kinship.py`
4. Use in `dotgen.py` for chart annotations

## Performance Considerations

- **Parser**: GEDCOM files are loaded entirely into memory for fast access
- **GedcomReader**: Kept open during program execution to allow lazy reference resolution
- **Path Finding**: BFS finds shortest paths level by level and expands each
  `(person, descended)` state once, so the work is bounded by twice the number
  of people reachable within `--max-depth`, and by the 200,000-state cap
- **Caching**: Individuals and families are cached to avoid repeated parsing
- **Spouse Detection**: In relationship charts, the spouse drawn next to a
  parent on the path is the other member of the couple of the family that
  step went through, read from the link indexes

## Common Issues

### Memory Usage

For very large GEDCOM files (>100K individuals), consider:
- Streaming parsing instead of loading all individuals
- Limiting search depth
- Using iterative deepening for path finding

### Path Finding Performance

- `--max-depth` is 50 by default and at most 50; lower it to make a search on a
  large file give up sooner. When it is the reason nothing was found, the CLI
  says `--max-depth N reached` rather than that there is no relationship
- Heavily intermarried trees can have many equally short paths; only the first
  10,000 (`_MAX_PATHS`) are rebuilt and ranked

## Dependencies

- **ged4py**: GEDCOM parsing library (runtime dependency), `>=0.5.2,<0.6`. Note
  that 0.5.2 requires Python >=3.11, which is why this project's floor is 3.11.
  It pulls in `ansel`, `convertdate` and (transitively) `pymeeus`, so the audited
  runtime surface is four packages, not one.
- **GraphViz**: System tool (`dot` command) for rendering DOT files to images — not a Python package dependency, must be installed separately via your OS package manager
