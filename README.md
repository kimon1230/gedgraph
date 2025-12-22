# GedGraph

Generate genealogical charts from GEDCOM files using GraphViz.

## Features

- **Pedigree Charts**: Visualize ancestors of an individual
- **Relationship Charts**: Find and visualize relationships between two individuals
- **Hourglass Charts**: Show ancestors and descendants or split by parental lines
- **Bowtie Charts**: Horizontal hourglass layout with left-right orientation
- **Smart Path Finding**: Automatically finds the shortest relationship path using breadth-first search
- **Relationship Prioritization**: Prefers blood relationships via male line, then female line, then half-blood relationships
- **Multiple Path Detection**: Identifies when multiple equally short paths exist
- **Spouse Visualization**: Shows spouses/partners alongside the direct bloodline
- **Marriage Status Indicators**: Solid lines for married couples, dashed lines for unmarried couples
- **Flexible Date Handling**: Uses birth/death dates with fallback to baptism/burial dates
- **Enhanced Name Formatting**: Supports GEDCOM name components (prefix, title, given, surname, suffix)
- **GraphViz Output**: Generates DOT files that can be rendered to various image formats

## Installation

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Pedigree Chart

Generate a pedigree chart showing ancestors of an individual:

```bash
python gedgraph.py pedigree family.ged @I10@ -o output.dot
```

Options:
- `-g, --generations`: Number of generations to include (default: 4)

Example:
```bash
python gedgraph.py pedigree family.ged @I10@ -g 5 -o pedigree.dot
```

### Relationship Chart

Find and visualize the relationship between two individuals:

```bash
python gedgraph.py relationship family.ged @I10@ @I20@ -o output.dot
```

Options:
- `-d, --max-depth`: Maximum search depth (default: 50)

Example:
```bash
python gedgraph.py relationship family.ged @I1@ @I50@ -d 15 -o relationship.dot
```

### Hourglass Chart

Visualize ancestors and descendants or split by parental lines:

```bash
# Ancestors above, descendants below
python gedgraph.py hourglass family.ged @I10@ -v descendants -o hourglass.dot

# Father's line above, mother's line below
python gedgraph.py hourglass family.ged @I10@ -v ancestor-split -o hourglass.dot
```

Options:
- `-g, --generations`: Number of generations in each direction (default: 4)
- `-v, --variant`: Chart variant - `ancestor-split` or `descendants` (default: ancestor-split)

### Bowtie Chart

Horizontal hourglass layout with left-right orientation:

```bash
# Ancestors left, descendants right
python gedgraph.py bowtie family.ged @I10@ -v descendants -o bowtie.dot

# Father's line left, mother's line right
python gedgraph.py bowtie family.ged @I10@ -v ancestor-split -o bowtie.dot
```

Options:
- `-g, --generations`: Number of generations in each direction (default: 4)
- `-v, --variant`: Chart variant - `ancestor-split` or `descendants` (default: ancestor-split)

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

When multiple equally short paths exist between two individuals, GedGraph prioritizes them in this order:

1. Full blood relationships via male line
2. Full blood relationships via female line
3. Half-blood relationships via male line
4. Half-blood relationships via female line

The tool will generate charts for all paths of equal shortest length.

## Example Output

The generated DOT files include:

- **Comments**: Generation distance, path length, and relationship description
- **Color Coding**:
  - Start individual (coral)
  - End individual (light blue)
  - Direct bloodline (light green)
  - Spouses/partners (light yellow)
- **Labels**: Names with birth/death years in (YYYY - YYYY) format
- **Relationship Lines**:
  - Solid arrows for parent-child relationships
  - Solid lines for married couples
  - Dashed lines for unmarried couples
- **Horizontal Alignment**: Spouses are positioned next to their partners using rank constraints

## Error Handling

GedGraph will exit with an error if:

- The GEDCOM file doesn't exist
- An individual ID is not found in the GEDCOM file
- No relationship exists between two individuals (for relationship charts)

## Development

See [DEVELOPER.md](DEVELOPER.md) for development setup and architecture details.

## License

MIT
