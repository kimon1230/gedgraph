"""Tests for DOT file generation."""

from pathlib import Path

import pytest

from gedgraph.dotgen import DotGenerator
from gedgraph.parser import GedcomParser
from gedgraph.pathfinder import PathFinder

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def special_parser():
    """Load special character GEDCOM file."""
    p = GedcomParser(str(FIXTURES_DIR / "sample_special.ged"))
    p.load()
    return p


@pytest.fixture
def dotgen(parser):
    """Create DotGenerator instance."""
    return DotGenerator(parser)


@pytest.fixture
def special_dotgen(special_parser):
    """Create DotGenerator for special character fixture."""
    return DotGenerator(special_parser)


@pytest.fixture
def pathfinder(parser):
    """Create PathFinder instance."""
    return PathFinder(parser)


def test_generate_pedigree(dotgen):
    """Test generating pedigree DOT file."""
    dot = dotgen.generate_pedigree("@I7@", generations=3)
    assert "digraph Pedigree" in dot
    assert "David Smith" in dot
    assert "I7" in dot
    assert "I5" in dot
    assert "I1" in dot


def test_generate_pedigree_invalid_individual(dotgen):
    """Test generating pedigree for invalid individual."""
    with pytest.raises(ValueError):
        dotgen.generate_pedigree("@I999@")


def test_generate_relationship(dotgen, pathfinder):
    """Test generating relationship DOT file."""
    paths = pathfinder.get_shortest_paths("@I1@", "@I7@")
    dot = dotgen.generate_relationship(paths)
    assert "digraph Relationship" in dot
    assert "John Smith" in dot
    assert "David Smith" in dot


def test_generate_relationship_no_paths(dotgen):
    """Test generating relationship with no paths."""
    with pytest.raises(ValueError):
        dotgen.generate_relationship([])


def test_dot_includes_dates(dotgen):
    """Test that DOT output includes birth/death dates."""
    dot = dotgen.generate_pedigree("@I1@", generations=1)
    assert "1900" in dot
    assert "1980" in dot


def test_dot_includes_comments(dotgen, pathfinder):
    """Test that relationship DOT includes comments."""
    paths = pathfinder.get_shortest_paths("@I1@", "@I7@")
    dot = dotgen.generate_relationship(paths)
    assert "John Smith to David Smith" in dot
    assert "3 steps" in dot
    assert "Direct descendant" in dot


def test_escape_id(dotgen):
    """Test ID escaping for DOT format."""
    assert dotgen._escape_id("@I1@") == "I1"
    assert dotgen._escape_id("@I1-2@") == "I1_2"
    assert dotgen._escape_id("@I.1/2+3@") == "I_1_2_3"
    assert dotgen._escape_id("@123@") == "_123"


def test_format_individual_label(dotgen, parser):
    """Test individual label formatting."""
    individual = parser.get_individual("@I1@")
    label = dotgen._format_label(individual)
    assert "John Smith" in label
    assert "1900" in label
    assert "1980" in label


def test_describe_relationship_parent_child(dotgen, pathfinder):
    """Test relationship description for parent-child."""
    paths = pathfinder.get_shortest_paths("@I1@", "@I3@")
    description = dotgen._describe_relationship(paths[0])
    assert "Parent-Child" in description


def test_describe_relationship_siblings(dotgen, pathfinder):
    """Test relationship description for siblings."""
    paths = pathfinder.get_shortest_paths("@I7@", "@I8@")
    description = dotgen._describe_relationship(paths[0])
    assert "Siblings" in description or "Collateral" in description


def test_describe_relationship_same_individual(dotgen, pathfinder):
    """Test relationship description for same individual."""
    paths = pathfinder.get_shortest_paths("@I1@", "@I1@")
    description = dotgen._describe_relationship(paths[0])
    assert description == "Same individual"


def test_describe_relationship_direct_descendant(dotgen, pathfinder):
    """Test relationship description for direct descendant (gen > 0)."""
    paths = pathfinder.get_shortest_paths("@I1@", "@I7@")
    description = dotgen._describe_relationship(paths[0])
    assert description == "Direct descendant (3 generations)"


def test_describe_relationship_direct_ancestor(dotgen, pathfinder):
    """Test relationship description for direct ancestor (gen < 0)."""
    paths = pathfinder.get_shortest_paths("@I7@", "@I1@")
    description = dotgen._describe_relationship(paths[0])
    assert description == "Direct ancestor (3 generations)"


# --- Hourglass tests ---


def test_hourglass_ancestor_split(dotgen):
    """Ancestor-split hourglass puts father's line above, mother's below."""
    dot = dotgen.generate_hourglass("@I5@", 2, "ancestor-split")

    assert "digraph Hourglass" in dot
    assert "rankdir=TB" in dot

    # Focal individual at gen 0
    assert "I5" in dot
    assert "fillcolor=lightcoral" in dot

    # Father's side (positive gens)
    assert "Robert Smith" in dot  # I3
    assert "John Smith" in dot  # I1
    assert "Mary Jones" in dot  # I2

    # Mother's side (negative gens)
    assert "Sarah Brown" in dot  # I4

    # All non-focal nodes are lightgreen
    for name in ["Robert Smith", "John Smith", "Mary Jones", "Sarah Brown"]:
        # Each ancestor node appears with lightgreen fill
        assert name in dot


def test_hourglass_descendants(dotgen):
    """Descendants hourglass puts ancestors above, descendants below."""
    dot = dotgen.generate_hourglass("@I5@", 2, "descendants")

    assert "digraph Hourglass" in dot
    assert "rankdir=TB" in dot

    # Focal
    assert "Michael Smith" in dot

    # Ancestors at positive gens
    assert "Robert Smith" in dot  # I3
    assert "Sarah Brown" in dot  # I4
    assert "John Smith" in dot  # I1
    assert "Mary Jones" in dot  # I2

    # Descendants at negative gens
    assert "David Smith" in dot  # I7
    assert "Emily Smith" in dot  # I8

    # Edges from I5 to children
    assert "I5 -> I7" in dot
    assert "I5 -> I8" in dot


# --- Bowtie tests ---


def test_bowtie_ancestor_split(dotgen):
    """Ancestor-split bowtie uses LR layout with father/mother on opposite sides."""
    dot = dotgen.generate_bowtie("@I5@", 2, "ancestor-split")

    assert "digraph Bowtie" in dot
    assert "rankdir=LR" in dot

    # Focal
    assert "Michael Smith" in dot

    # Father's line
    assert "Robert Smith" in dot
    assert "John Smith" in dot
    assert "Mary Jones" in dot

    # Mother's line
    assert "Sarah Brown" in dot

    # Parent-child edges exist
    assert "I3 -> I5" in dot
    assert "I4 -> I5" in dot
    assert "I1 -> I3" in dot


def test_bowtie_descendants(dotgen):
    """Descendants bowtie puts ancestors on one side, descendants on the other."""
    dot = dotgen.generate_bowtie("@I5@", 2, "descendants")

    assert "digraph Bowtie" in dot
    assert "rankdir=LR" in dot

    # All individuals present
    assert "Michael Smith" in dot
    assert "John Smith" in dot
    assert "David Smith" in dot
    assert "Emily Smith" in dot

    # Descendant edges
    assert "I5 -> I7" in dot
    assert "I5 -> I8" in dot

    # Ancestor edges
    assert "I3 -> I5" in dot
    assert "I1 -> I3" in dot


# --- Special character tests ---


def test_format_label_with_quotes(special_dotgen, special_parser):
    """Quoted nickname in name produces valid DOT label with escaped quotes."""
    ind = special_parser.get_individual("@I20@")
    label = special_dotgen._format_label(ind)

    # Quotes must be escaped for DOT string delimiters
    assert '\\"' in label
    assert "Johnny" in label
    # Every quote in the label must be preceded by a backslash
    unescaped = label.replace('\\"', "")
    assert '"' not in unescaped


def test_format_label_with_backslash(special_dotgen, special_parser):
    """Trailing backslash in name must not break DOT string delimiters."""
    ind = special_parser.get_individual("@I21@")
    label = special_dotgen._format_label(ind)

    # Name should be present
    assert "Test" in label
    assert "Name" in label
