"""Shared test fixtures."""

from pathlib import Path

import pytest

from gedgraph.parser import GedcomParser

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_gedcom():
    """Load sample GEDCOM file and return parser."""
    p = GedcomParser(str(FIXTURES_DIR / "sample.ged"))
    p.load()
    return p


@pytest.fixture
def parser(sample_gedcom):
    """Alias for sample_gedcom — used by pathfinder and dotgen tests."""
    return sample_gedcom
