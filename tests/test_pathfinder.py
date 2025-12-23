"""Tests for relationship path finding."""

from pathlib import Path

import pytest

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
def pathfinder(parser):
    """Create PathFinder instance."""
    return PathFinder(parser)


def test_find_pedigree(pathfinder):
    """Test finding pedigree for an individual."""
    pedigree = pathfinder.find_pedigree("@I7@", generations=3)
    assert len(pedigree) > 0
    individual_ids = {ind.xref_id for ind in pedigree}
    assert "@I7@" in individual_ids
    assert "@I5@" in individual_ids
    assert "@I3@" in individual_ids
    assert "@I1@" in individual_ids


def test_find_pedigree_limited_generations(pathfinder):
    """Test pedigree with limited generations."""
    pedigree = pathfinder.find_pedigree("@I7@", generations=1)
    individual_ids = {ind.xref_id for ind in pedigree}
    assert "@I7@" in individual_ids
    assert "@I5@" in individual_ids
    assert "@I6@" in individual_ids


def test_find_direct_parent_child(pathfinder):
    """Test finding direct parent-child relationship."""
    paths = pathfinder.find_relationship_paths("@I1@", "@I3@")
    assert len(paths) > 0
    shortest = paths[0]
    assert shortest.length() == 1
    assert not shortest.steps[0].is_parent  # Going to child, not parent


def test_find_grandparent_grandchild(pathfinder):
    """Test finding grandparent-grandchild relationship."""
    paths = pathfinder.find_relationship_paths("@I1@", "@I5@")
    assert len(paths) > 0
    shortest = min(paths, key=lambda p: p.length())
    assert shortest.length() == 2


def test_find_great_grandparent(pathfinder):
    """Test finding great-grandparent relationship."""
    paths = pathfinder.find_relationship_paths("@I1@", "@I7@")
    assert len(paths) > 0
    shortest = min(paths, key=lambda p: p.length())
    assert shortest.length() == 3


def test_find_siblings(pathfinder):
    """Test finding sibling relationship."""
    paths = pathfinder.find_relationship_paths("@I7@", "@I8@")
    assert len(paths) > 0
    shortest = min(paths, key=lambda p: p.length())
    assert shortest.length() == 2


def test_no_relationship(pathfinder):
    """Test when no relationship exists."""
    paths = pathfinder.find_relationship_paths("@I1@", "@I10@")
    assert len(paths) == 0


def test_same_individual(pathfinder):
    """Test relationship to self."""
    paths = pathfinder.find_relationship_paths("@I1@", "@I1@")
    assert len(paths) > 0
    assert paths[0].length() == 0


def test_get_shortest_paths(pathfinder):
    """Test getting shortest paths with proper sorting."""
    paths = pathfinder.get_shortest_paths("@I1@", "@I7@")
    assert len(paths) > 0
    path = paths[0]
    assert path.length() == 3


def test_generation_distance_descendant(pathfinder):
    """Test generation distance for descendant."""
    paths = pathfinder.find_relationship_paths("@I1@", "@I7@")
    path = min(paths, key=lambda p: p.length())
    assert path.generation_distance() == 3


def test_generation_distance_ancestor(pathfinder):
    """Test generation distance for ancestor."""
    paths = pathfinder.find_relationship_paths("@I7@", "@I1@")
    path = min(paths, key=lambda p: p.length())
    assert path.generation_distance() == -3


def test_generation_distance_sibling(pathfinder):
    """Test generation distance for siblings."""
    paths = pathfinder.find_relationship_paths("@I7@", "@I8@")
    path = min(paths, key=lambda p: p.length())
    assert path.generation_distance() == 0
