# Developer Documentation

## Architecture

GedGraph is structured as a modular Python application with clear separation of concerns:

```
gedgraph/
├── __init__.py       # Package metadata
├── parser.py         # GEDCOM file parsing and queries
├── pathfinder.py     # Relationship path finding algorithms
├── dotgen.py         # GraphViz DOT file generation
└── cli.py            # Command-line interface
```

## Core Modules

### parser.py - GEDCOM Parsing

**Purpose**: Parse GEDCOM files and provide query methods for individuals and relationships.

**Key Classes**:
- `GedcomParser`: Main parser class using ged4py library

**Key Methods**:
- `load()`: Parse GEDCOM file into memory
- `get_individual(xref_id)`: Retrieve individual by ID
- `get_name(individual)`: Format name using NPFX/TITL GIVN SURN NSFX sequence
- `get_birth_year()`, `get_death_year()`: Get vital dates with fallback to baptism/burial
- `get_parents(individual)`: Get father and mother
- `get_children(individual)`: Get all children
- `get_spouse_for_child()`: Get spouse in context of specific child, with marriage status
- `is_full_sibling()`, `is_half_sibling()`: Determine sibling relationships
- `_extract_year()`: Extract year from GEDCOM event tag (used by birth/death methods)

**Implementation Notes**:
- Individuals and families are loaded at initialization and kept in memory
- GedcomReader stays open to allow lazy resolution of references
- Individuals cached in `_individuals` dict for O(1) lookup
- Families cached in `_families` dict
- Accepts IDs with or without @ symbols for convenience
- Name parsing checks GEDCOM sub-tags (NPFX, TITL, GIVN, SURN, NSFX) before falling back to parsed tuple
- Marriage detection checks for MARR tag in family records

### pathfinder.py - Relationship Path Finding

**Purpose**: Find relationship paths between individuals using graph traversal.

**Key Classes**:
- `PathFinder`: BFS-based path finding
- `RelationshipPath`: Represents a complete path with metadata
- `PathStep`: Represents a single parent/child relationship with boolean flags

**Algorithm**:
- Uses breadth-first search (BFS) to find shortest paths
- Explores both upward (parents) and downward (children) relationships
- Tracks visited nodes to avoid infinite loops
- Continues searching until all paths of minimum length are found

**Path Sorting**:
Paths are sorted by a tuple key:
1. Length (number of steps)
2. Blood score (count of half-blood relationships)
3. Male preference score (count of female-line steps)

This prioritizes: shorter paths, full blood over half blood, male line over female line.

**Key Methods**:
- `find_pedigree()`: BFS to find ancestors up to N generations
- `find_pedigree_with_generations()`: Find ancestors with generation tracking
- `find_pedigree_split()`: Find paternal and maternal pedigrees separately
- `find_descendants()`: Find descendants with generation tracking
- `find_relationship_paths()`: BFS to find all paths between two individuals
- `get_shortest_paths()`: Find and sort shortest paths
- `_bfs_traverse()`: Generic BFS traversal used by all find methods
- `_get_neighbors()`: Get all adjacent individuals in the graph
- `_is_full_blood()`: Check if parent-child relationship is full blood

### dotgen.py - GraphViz Generation

**Purpose**: Generate DOT format files for visualization.

**Key Classes**:
- `DotGenerator`: Creates DOT syntax for charts

**Key Methods**:
- `generate_pedigree()`: Create pedigree chart DOT file (ancestors only)
- `generate_hourglass()`: Create hourglass chart DOT file (vertical split)
- `generate_bowtie()`: Create bowtie chart DOT file (horizontal split)
- `generate_relationship()`: Create relationship chart DOT file with spouse nodes
- `_format_label()`: Format names with dates in (YYYY - YYYY) format
- `_describe_relationship()`: Generate human-readable relationship description
- `_build_generation_map()`: Build generation map for hourglass/bowtie charts
- `_render_chart()`: Generic chart renderer for all chart types

**Chart Types**:
- **Pedigree**: Ancestors only, top-to-bottom layout
- **Hourglass**: Two variants with vertical layout (rankdir=TB)
  - `ancestor-split`: Father's line above root, mother's line below root
  - `descendants`: Ancestors above root, descendants below root
- **Bowtie**: Two variants with horizontal layout (rankdir=LR)
  - `ancestor-split`: Father's line left of root, mother's line right of root
  - `descendants`: Ancestors left of root, descendants right of root
- **Relationship**: Path between two individuals with spouses

**DOT Generation**:
- Uses `rankdir=TB` (top-to-bottom) for pedigree, hourglass, and relationship charts
- Uses `rankdir=LR` (left-to-right) for bowtie charts
- Color codes nodes: lightcoral (start/root), lightblue (end), lightgreen (bloodline), lightyellow (spouses)
- Spouse nodes positioned using `{rank=same; ...}` constraints
- Marriage status indicated by line style: solid (married), dashed (unmarried)
- Spouse lines use `dir=none` and `constraint=false` to avoid affecting layout
- Includes metadata as comments (generations, path length, etc.)

### cli.py - Command Line Interface

**Purpose**: Provide user-friendly CLI using argparse.

**Commands**:
- `pedigree`: Generate ancestor chart
- `relationship`: Generate relationship chart between two individuals
- `hourglass`: Generate hourglass chart (vertical split layout)
- `bowtie`: Generate bowtie chart (horizontal split layout)

**Common Options**:
- `-o, --output`: Output DOT file path (required for all commands)
- `-g, --generations`: Number of generations (default: 4, used by pedigree/hourglass/bowtie)
- `-d, --max-depth`: Maximum search depth (default: 50, used by relationship)
- `-v, --variant`: Chart variant (used by hourglass/bowtie)
  - `ancestor-split`: Split by parental lines
  - `descendants`: Split by ancestors/descendants

**Error Handling**:
- Validates GEDCOM file exists
- Validates individual IDs exist
- Reports when no relationship found
- Exits with appropriate error codes

## Development Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

## Testing

### Test Structure

```
tests/
├── fixtures/
│   └── sample.ged       # Sample GEDCOM for testing
├── test_parser.py       # Parser unit tests
├── test_pathfinder.py   # Path finding unit tests
├── test_dotgen.py       # DOT generation unit tests
└── test_integration.py  # End-to-end CLI tests
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

### Test Fixtures

The `sample.ged` file contains:
- 10 individuals across 4 generations
- Various relationships (parent-child, siblings, cousins)
- Birth and death dates for testing date parsing
- Both connected and disconnected individuals

## Code Quality

```bash
# Format code
make fmt

# Check formatting and linting
make lint

# Audit dependencies for security vulnerabilities
make audit
```

### Tools

- **black**: Code formatting (line length: 100)
- **ruff**: Fast Python linter
- **pip-audit**: Dependency vulnerability scanning
- **pytest**: Testing framework

## Adding New Features

### Adding a New Chart Type

1. Add new generation method in `dotgen.py` (e.g., `generate_newchart()`)
   - Use PathFinder methods to gather individuals
   - Organize individuals by generation or other criteria
   - Generate DOT syntax with appropriate rankdir and constraints
2. Add new subcommand in `cli.py`
   - Create subparser with appropriate arguments
   - Handle command in main() function
   - Add error handling and user feedback
3. Add tests in `tests/test_dotgen.py`
   - Test successful generation
   - Test error cases
   - Verify DOT output contains expected elements
4. Update README.md and DEVELOPER.md with usage examples

**Example**: The hourglass and bowtie charts share common infrastructure:
- Both use `_build_generation_map()` to organize individuals by generation
- Both use `_render_chart()` for DOT generation
- They differ only in rankdir: TB (hourglass) or LR (bowtie)
- Both support `ancestor-split` and `descendants` variants

### Adding New Relationship Metrics

1. Add new method to `PathFinder` class
2. Update `RelationshipPath` dataclass if needed
3. Add tests in `tests/test_pathfinder.py`
4. Use in `dotgen.py` for chart annotations

## Performance Considerations

- **Parser**: GEDCOM files are loaded entirely into memory for fast access
- **GedcomReader**: Kept open during program execution to allow lazy reference resolution
- **Path Finding**: BFS is optimal for finding shortest paths; max_depth prevents infinite searches
- **Caching**: Individuals and families are cached to avoid repeated parsing
- **Spouse Detection**: For relationship charts, spouses are identified by examining family records in the context of specific children

## Common Issues

### Memory Usage

For very large GEDCOM files (>100K individuals), consider:
- Streaming parsing instead of loading all individuals
- Limiting search depth
- Using iterative deepening for path finding

### Path Finding Performance

- Default max_depth of 50 handles most genealogies
- Increase max_depth for very distant relationships
- Very large families may have many equally short paths

## Dependencies

- **ged4py**: GEDCOM parsing library
- **graphviz**: Python bindings for GraphViz (optional for rendering)

The program only requires ged4py; graphviz package is optional and only needed if rendering DOT files programmatically.
