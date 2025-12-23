"""Tests for DOT file generation."""

from pathlib import Path

import pytest

from gedgraph.dotgen import DotGenerator
from gedgraph.parser import GedcomParser
from gedgraph.pathfinder import PathFinder


@pytest.fixture
def parser():
    """Load sample GEDCOM file."""
    gedcom_path = Path(__file__).parent / "fixtures" / "sample.ged"
    p = GedcomParser(str(gedcom_path))
    p.load()
    return p


@pytest.fixture
def dotgen(parser):
    """Create DotGenerator instance."""
    return DotGenerator(parser)


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
    assert "Direct ancestor" in dot


def test_escape_id(dotgen):
    """Test ID escaping for DOT format."""
    escaped = dotgen._escape_id("@I1@")
    assert escaped == "I1"


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
