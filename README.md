# GedGraph

[![Tests](https://github.com/kimon1230/gedgraph/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/kimon1230/gedgraph/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/kimon-gedgraph)](https://pypi.org/project/kimon-gedgraph/)
[![Python](https://img.shields.io/pypi/pyversions/kimon-gedgraph)](https://pypi.org/project/kimon-gedgraph/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)

Generate genealogical charts from GEDCOM files using GraphViz.

## Features

- **Pedigree Charts**: Visualize ancestors of an individual
- **Relationship Charts**: Find and visualize relationships between two individuals, and name the relationship (first cousin once removed, half-brother, great-aunt, ...)
- **Hourglass Charts**: Show ancestors and descendants or split by parental lines
- **Bowtie Charts**: Horizontal hourglass layout with left-right orientation
- **Smart Path Finding**: Automatically finds the shortest relationship path using breadth-first search
- **Relationship Prioritization**: Among equally short paths, prefers birth links over adoptive, foster or step links, a marriage line over a route through a shared child, full blood over half blood, then the male line
- **Multiple Path Detection**: Finds every equally short path and charts the preferred one
- **Spouse Visualization**: Shows spouses/partners alongside the direct bloodline
- **Marriage Status Indicators**: Solid lines for married couples, dashed lines for unmarried couples
- **Flexible Date Handling**: Uses birth/death dates with fallback to baptism/burial dates, and marks approximate or bounded years (`c. 1950`, `bef. 1900`)
- **Enhanced Name Formatting**: Supports GEDCOM name components (prefix, title, given, surname, suffix)
- **Progress Feedback**: Braille-spinner progress indicators with `--verbose`, `--quiet`, `--no-color`, and `--ascii` options
- **GraphViz Output**: Generates DOT files that can be rendered to various image formats

## Prerequisites

- Python 3.11+
- [GraphViz](https://graphviz.org/) (`dot` command) installed on your system to render DOT files to images

## Installation

```bash
pip install kimon-gedgraph
```

### Development Setup

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

## Usage

### Pedigree Chart

Generate a pedigree chart showing ancestors of an individual:

```bash
gedgraph pedigree family.ged @I10@ -o output.dot
```

Options:
- `-g, --generations`: Number of generations to include (default: 4)

Example:
```bash
gedgraph pedigree family.ged @I10@ -g 5 -o pedigree.dot
```

### Relationship Chart

Find and visualize the relationship between two individuals:

```bash
gedgraph relationship family.ged @I10@ @I20@ -o output.dot
```

Options:
- `-d, --max-depth`: Maximum search depth, 1-50 (default: 50)

Example:
```bash
gedgraph relationship family.ged @I1@ @I50@ -d 15 -o relationship.dot
```

The summary line names the second person's relationship to the first. Using
the test fixture:

```
$ gedgraph -q relationship tests/fixtures/sample.ged @I7@ @I8@ -o relationship.dot
Relationship: Emily Smith is David Smith's sister (2 steps) -> relationship.dot
```

Relationships are named in plain English: father, 2nd great-grandmother, niece,
first cousin once removed, and so on, with a `half-` prefix for half-blood
relationships. If the second person's sex is not recorded, neutral words are
used (parent, sibling, parent's sibling).

Adoptive, foster and step links (`PEDI adopted`, `PEDI foster`, `PEDI step`
under the child's `FAMC`) are followed and named as such. A child listed in a family's `CHIL`
with no `FAMC` to it, and a birth family elsewhere, is a stepchild there; English only has step- words for
parent, child and sibling. From `tests/fixtures/links.ged`:

```
$ gedgraph -q relationship tests/fixtures/links.ged @C2@ @AP@ -o r.dot
Relationship: Adam Ash is Clara Ash's adoptive father (1 step) -> r.dot
$ gedgraph -q relationship tests/fixtures/links.ged @C1@ @C2@ -o r.dot
Relationship: Clara Ash is Carl Birch's adoptive sister (2 steps) -> r.dot
$ gedgraph -q relationship tests/fixtures/links.ged @C5@ @SF@ -o r.dot
Relationship: Simon Spruce is Cora Birch's stepfather (1 step) -> r.dot
```

The two people in a family are husband and wife (or spouses) when it has a
marriage (`MARR`) record and partners otherwise, whether or not they had
children; the chart draws the marriage line between them, not a route through
a child. Marriages are only searched when there is no line of descent between
the two people. Any path through a marriage longer than one step is a
"relative by marriage":

```
$ gedgraph -q relationship tests/fixtures/links.ged @H7@ @W7@ -o r.dot
Relationship: Wendy Elm is Henry Birch's wife (1 step) -> r.dot
$ gedgraph -q relationship tests/fixtures/sample.ged @I3@ @I4@ -o r.dot
Relationship: Sarah Brown is Robert Smith's partner (1 step) -> r.dot
$ gedgraph -q relationship tests/fixtures/links.ged @C5@ @W7@ -o r.dot
Relationship: Wendy Elm is Cora Birch's relative by marriage (3 steps) -> r.dot
```

A line of descent goes up to a common ancestor and back down, never down and
then up again, so two cousins whose children married are still cousins, not
relatives by marriage through their shared grandchild.

If the search stops at `--max-depth` with people left unvisited, or at its
internal limit, gedgraph says so rather than reporting no relationship. A
direct spouse is still reported, with a note that a blood relationship may
have been missed:

```
$ gedgraph -q relationship tests/fixtures/sample.ged @I7@ @I1@ -d 2 -o r.dot
Error: --max-depth 2 reached looking for @I7@ -> @I1@
$ gedgraph -q relationship tests/fixtures/sample.ged @I1@ @I2@ -d 1 -o r.dot
Relationship: Mary Jones is John Smith's partner (1 step) (--max-depth reached; a blood relationship may have been missed) -> r.dot
```

### Hourglass Chart

Visualize ancestors and descendants or split by parental lines:

```bash
# Ancestors above, descendants below
gedgraph hourglass family.ged @I10@ -v descendants -o hourglass.dot

# Father's ancestors above, mother's ancestors below
gedgraph hourglass family.ged @I10@ -v ancestor-split -o hourglass.dot
```

Options:
- `-g, --generations`: Number of generations in each direction (default: 4)
- `-v, --variant`: Chart variant - `ancestor-split` or `descendants` (default: ancestor-split)

### Bowtie Chart

Horizontal hourglass layout with left-right orientation:

```bash
# Ancestors left, descendants right
gedgraph bowtie family.ged @I10@ -v descendants -o bowtie.dot

# Father's ancestors left, mother's ancestors right
gedgraph bowtie family.ged @I10@ -v ancestor-split -o bowtie.dot
```

Options:
- `-g, --generations`: Number of generations in each direction (default: 4)
- `-v, --variant`: Chart variant - `ancestor-split` or `descendants` (default: ancestor-split)

### Global Options

These flags must appear before the subcommand name:

```bash
# Suppress progress output
gedgraph --quiet pedigree family.ged @I10@ -o output.dot

# Show progress with timing
gedgraph --verbose relationship family.ged @I10@ @I20@ -o output.dot

# Disable colored output
gedgraph --no-color hourglass family.ged @I10@ -o output.dot

# Use ASCII decorations instead of braille/check marks
gedgraph --ascii pedigree family.ged @I10@ -o output.dot

# Print the installed version
gedgraph --version
```

| Flag | Description |
|------|-------------|
| `--version` | Print the version and exit |
| `--verbose` | Show detailed progress with timing |
| `-q, --quiet` | Suppress progress output |
| `--no-color` | Disable colored output |
| `--ascii` / `--no-ascii` | Use ASCII decorations (`[OK]`, `[!]`, `\|/-\`) instead of `✓`, `✗` and the braille spinner |

`--ascii` is for consoles whose fonts cannot draw braille — common on Windows,
where the spinner otherwise renders as a row of boxes. It can also be set with
`GEDGRAPH_ASCII=1`; the flag wins over the environment variable in both
directions.

### Output Encoding

Names are written to stdout in the console's own encoding. When output is
redirected to a file or a pipe, UTF-8 is used instead — there is no terminal on
the other end whose encoding matters, and this is what makes names with Greek,
Cyrillic or accented characters survive `gedgraph ... > out.txt`.

If you pin an encoding yourself with `PYTHONIOENCODING`, that choice is
respected. Characters it cannot represent are escaped (`\u0391`) rather than
causing the command to fail. Generated DOT files are always UTF-8, independent
of the console.

### Privacy

A GEDCOM record marked `RESN privacy` or `RESN confidential` (the standard way
genealogy software flags living or sensitive people) is drawn as "Private" with
no years, and named "Private" in the summary line, with a neutral relationship
word ("parent", not "father") and no sign of a marriage. A birth or death event that
carries its own `RESN` loses its year, without falling back to baptism or
burial. `RESN locked` only stops edits and hides nothing. Add
`--include-private` after the subcommand to show everything:

```bash
gedgraph pedigree family.ged @I10@ -o pedigree.dot --include-private
```

Output files are created readable by their owner only, since they hold real
people's names and dates. `-o` must name a regular file: a symlink, FIFO or
device such as `/dev/stdout` is refused, and the output's directory must allow
creating files. Names longer than 200 characters are cut short.

### Rendering DOT Files

Convert DOT files to images using GraphViz:

```bash
# PNG
dot -Tpng output.dot -o output.png

# PDF
dot -Tpdf output.dot -o output.pdf

# SVG
dot -Tsvg output.dot -o output.svg
```

## Relationship Path Sorting

When multiple equally short paths exist between two individuals, GedGraph prefers, in this order:

1. Fewer adoptive, foster or step links
2. A marriage line over a route down to a child and up to its other parent
3. Full blood over half blood (two first cousins related both ways are "first
   cousin", not "half-first cousin")
4. More steps through a father than through a mother

The chart and the summary line use the first path in this order.

## Example Output

The generated DOT files include:

- **Comments**: The focal person's name, plus the generation count for pedigree charts; for relationship charts, the summary sentence shown above
- **Color Coding**:
  - Start individual (coral)
  - End individual (light blue)
  - Direct bloodline (light green)
  - Spouses/partners (light yellow)
- **Labels**: Names with birth/death years as `(1950 - 2001)`, `(1950 - )` when there is no death year, or `(? - 2001)` when there is no birth year
- **Relationship Lines**:
  - Solid arrows for parent-child relationships
  - Dotted arrows for adoptive, foster and step links
  - Solid lines for married couples
  - Dashed lines for unmarried couples
- **Horizontal Alignment**: In relationship charts, spouses are positioned next to their partners using rank constraints

### Years in Labels

Birth years fall back to baptism (`BAPM`) and then christening (`CHR`); death
years fall back to burial (`BURI`). Inexact dates are marked:

| GEDCOM date | Shown as |
|-------------|----------|
| `1 JAN 1950` | `1950` |
| `1 JAN 1950/51` (dual year) | `1950/51` |
| `500 B.C.` | `500 BC` |
| `ABT 1950`, `EST 1950`, `CAL 1950` | `c. 1950` |
| `BET 1900 AND 1910` | `c. 1900` |
| `BEF 1900` | `bef. 1900` |
| `AFT 1900` | `aft. 1900` |
| `FROM 1800 TO 1850` | `c. 1800` |
| `TO 1910` | `bef. 1910` |
| `FROM 1900` | `aft. 1900` |
| `ABT @#DJULIAN@ 1700/01` | `c. 1700` |
| `(born 1902)`, `Abt. 1950` (free text) | `1902`, `c. 1950` |
| `Between 1840 and 1850`, `Mai 1950` (free text) | no year |
| Hebrew, French Republican or unrecognised calendar | no year; the fallback date is used |

Free text shows a year only when it ends in a three- or four-digit year and
every word before that is a qualifier (`abt`, `about`, `circa`, `ca`, `c`,
`approx`, `est`, `estimated`, `cal` give `c.`; `bef`, `before` give `bef.`;
`aft`, `after` give `aft.`), an English month name, its three-letter
abbreviation or `Sept`, a day number, or `born`/`b`. Anything else in the text
means no year, so a phone or reference number in a note is never shown as one.

## Error Handling

GedGraph will exit with an error if:

- The GEDCOM file doesn't exist
- `-o` names the input GEDCOM file (a usage error, exit 2)
- The input or output path cannot be checked (for example a name too long for
  the file system)
- An individual ID is not found in the GEDCOM file
- No relationship exists between two individuals (for relationship charts)
- The relationship search reached its internal limit, or `--max-depth`, without
  finding a path

## Development

See [DEVELOPER.md](DEVELOPER.md) for development setup and architecture details.

## License

MIT
