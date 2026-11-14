"""Shared test fixtures."""

from pathlib import Path

import pytest

from gedgraph.parser import GedcomParser
from gedgraph.pathfinder import PathFinder

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_gedcom():
    """Load sample GEDCOM file and return parser."""
    with GedcomParser(str(FIXTURES_DIR / "sample.ged")) as p:
        p.load()
        yield p


@pytest.fixture
def parser(sample_gedcom):
    """Alias for sample_gedcom — used by pathfinder and dotgen tests."""
    return sample_gedcom


@pytest.fixture
def pathfinder(parser):
    return PathFinder(parser)


@pytest.fixture(scope="module")
def links():
    with GedcomParser(str(FIXTURES_DIR / "links.ged")) as p:
        p.load()
        yield p


@pytest.fixture(scope="module")
def cousins():
    """Two male-line cousins, @A@ and @B@; @A@ married @B@'s sister @S@."""
    with GedcomParser(str(FIXTURES_DIR / "cousins.ged")) as p:
        p.load()
        yield p


@pytest.fixture
def load(tmp_path):
    """Write records to a GEDCOM file and load it; closed at teardown."""
    opened = []

    def _load(records):
        path = tmp_path / f"t{len(opened)}.ged"
        path.write_text("0 HEAD\n1 CHAR UTF-8\n" + records + "0 TRLR\n", encoding="utf-8")
        p = GedcomParser(str(path))
        opened.append(p)
        p.load()
        return p

    yield _load
    for p in opened:
        p.close()
