"""Tests for GEDCOM parser."""

from pathlib import Path
from unittest.mock import patch

import pytest
from ged4py import GedcomReader

from gedgraph.parser import GedcomParser

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def special_gedcom():
    """Load special character GEDCOM file."""
    p = GedcomParser(str(FIXTURES_DIR / "sample_special.ged"))
    p.load()
    return p


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


def test_get_families_as_spouse(sample_gedcom):
    """Test getting families where individual is a spouse."""
    i1 = sample_gedcom.get_individual("@I1@")
    families = sample_gedcom.get_families_as_spouse(i1)
    fam_ids = [f.xref_id for f in families]
    assert "@F1@" in fam_ids


def test_get_spouse_for_child(sample_gedcom):
    """Test finding spouse via shared child."""
    i1 = sample_gedcom.get_individual("@I1@")
    i3 = sample_gedcom.get_individual("@I3@")
    spouse, is_married = sample_gedcom.get_spouse_for_child(i1, i3)
    assert spouse is not None
    assert spouse.xref_id == "@I2@"
    # No MARR tag in sample.ged F1, so is_married is False
    assert is_married is False


def test_birth_year_bapm_fallback(special_gedcom):
    """I22 has no BIRT but has BAPM — birth year should fall back to BAPM."""
    ind = special_gedcom.get_individual("@I22@")
    assert special_gedcom.get_birth_year(ind) == "1900"


def test_load_calls_close_on_failure():
    """If records0() raises mid-load, close() must release the file descriptor."""
    sample = str(FIXTURES_DIR / "sample.ged")
    gp = GedcomParser(sample)

    original_enter = GedcomReader.__enter__

    def enter_then_sabotage(self):
        result = original_enter(self)
        self.records0 = _boom_records0
        return result

    with (
        patch.object(GedcomParser, "close", wraps=gp.close) as mock_close,
        patch.object(GedcomReader, "__enter__", enter_then_sabotage),
        pytest.raises(RuntimeError, match="boom"),
    ):
        gp.load()

    mock_close.assert_called_once()


def _boom_records0(_tag):
    raise RuntimeError("boom")


def test_extract_year_malformed_date(special_gedcom):
    """I23 has 'ABT UNKNOWN' as birth date — _extract_year returns None after S1-extra fix."""
    ind = special_gedcom.get_individual("@I23@")
    year = special_gedcom.get_birth_year(ind)
    assert year is None
