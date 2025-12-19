"""Tests for GEDCOM parser."""

from pathlib import Path

import pytest

from gedgraph.parser import GedcomParser


@pytest.fixture
def sample_gedcom():
    """Load sample GEDCOM file."""
    gedcom_path = Path(__file__).parent / "fixtures" / "sample.ged"
    parser = GedcomParser(str(gedcom_path))
    parser.load()
    return parser


def test_load_gedcom(sample_gedcom):
    """Test loading GEDCOM file."""
    assert sample_gedcom.gedcom is not None
    assert len(sample_gedcom.gedcom) > 0


def test_get_individual(sample_gedcom):
    """Test retrieving individual by ID."""
    individual = sample_gedcom.get_individual("@I1@")
    assert individual is not None
    assert individual.xref_id == "@I1@"


def test_get_individual_without_at_symbols(sample_gedcom):
    """Test retrieving individual with ID without @ symbols."""
    individual = sample_gedcom.get_individual("I1")
    assert individual is not None
    assert individual.xref_id == "@I1@"


def test_get_nonexistent_individual(sample_gedcom):
    """Test retrieving non-existent individual."""
    individual = sample_gedcom.get_individual("@I999@")
    assert individual is None


def test_get_name(sample_gedcom):
    """Test getting individual name."""
    individual = sample_gedcom.get_individual("@I1@")
    name = sample_gedcom.get_name(individual)
    assert name == "John Smith"


def test_get_birth_year(sample_gedcom):
    """Test getting birth year."""
    individual = sample_gedcom.get_individual("@I1@")
    birth_year = sample_gedcom.get_birth_year(individual)
    assert birth_year == "1900"


def test_get_death_year(sample_gedcom):
    """Test getting death year."""
    individual = sample_gedcom.get_individual("@I1@")
    death_year = sample_gedcom.get_death_year(individual)
    assert death_year == "1980"


def test_get_parents(sample_gedcom):
    """Test getting parents."""
    individual = sample_gedcom.get_individual("@I3@")
    father, mother = sample_gedcom.get_parents(individual)
    assert father is not None
    assert mother is not None
    assert father.xref_id == "@I1@"
    assert mother.xref_id == "@I2@"


def test_get_parents_no_parents(sample_gedcom):
    """Test getting parents for individual without parents."""
    individual = sample_gedcom.get_individual("@I1@")
    father, mother = sample_gedcom.get_parents(individual)
    assert father is None
    assert mother is None


def test_get_children(sample_gedcom):
    """Test getting children."""
    individual = sample_gedcom.get_individual("@I1@")
    children = sample_gedcom.get_children(individual)
    assert len(children) == 1
    assert children[0].xref_id == "@I3@"


def test_get_children_multiple(sample_gedcom):
    """Test getting multiple children."""
    individual = sample_gedcom.get_individual("@I5@")
    children = sample_gedcom.get_children(individual)
    assert len(children) == 2
    child_ids = {child.xref_id for child in children}
    assert "@I7@" in child_ids
    assert "@I8@" in child_ids


def test_get_sex(sample_gedcom):
    """Test getting sex."""
    male = sample_gedcom.get_individual("@I1@")
    female = sample_gedcom.get_individual("@I2@")
    assert sample_gedcom.get_sex(male) == "M"
    assert sample_gedcom.get_sex(female) == "F"


def test_is_full_sibling(sample_gedcom):
    """Test checking full siblings."""
    david = sample_gedcom.get_individual("@I7@")
    emily = sample_gedcom.get_individual("@I8@")
    assert sample_gedcom.is_full_sibling(david, emily)


def test_is_not_full_sibling(sample_gedcom):
    """Test checking non-siblings."""
    robert = sample_gedcom.get_individual("@I3@")
    michael = sample_gedcom.get_individual("@I5@")
    assert not sample_gedcom.is_full_sibling(robert, michael)
