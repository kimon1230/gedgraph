"""Tests for GEDCOM parser."""

from pathlib import Path
from unittest.mock import patch

import pytest
from ged4py import GedcomReader

from gedgraph.parser import GedcomParser, _phrase_year

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def special_gedcom():
    """Load special character GEDCOM file."""
    with GedcomParser(str(FIXTURES_DIR / "sample_special.ged")) as p:
        p.load()
        yield p


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


def _family(parser, xref):
    found = parser.parent_family(parser.get_individual(xref))
    return found[0] if found else None


def _parents(parser, xref):
    return parser.couple(_family(parser, xref))


def _children(parser, xref):
    return [child.xref_id for child, _, _ in parser.child_links(parser.get_individual(xref))]


def test_parents(sample_gedcom):
    assert _parents(sample_gedcom, "@I3@") == ("@I1@", "@I2@")
    assert _parents(sample_gedcom, "@I1@") == (None, None)


def test_children(sample_gedcom):
    assert _children(sample_gedcom, "@I1@") == ["@I3@"]
    assert set(_children(sample_gedcom, "@I5@")) == {"@I7@", "@I8@"}


def test_get_sex(sample_gedcom):
    """Test getting sex."""
    male = sample_gedcom.get_individual("@I1@")
    female = sample_gedcom.get_individual("@I2@")
    assert sample_gedcom.get_sex(male) == "M"
    assert sample_gedcom.get_sex(female) == "F"


def test_get_sex_normalises_spelling(tmp_path):
    path = tmp_path / "sex.ged"
    path.write_text(
        "0 HEAD\n1 CHAR UTF-8\n"
        "0 @A@ INDI\n1 SEX Male\n"
        "0 @B@ INDI\n1 SEX  m\n"
        "0 @C@ INDI\n1 SEX f\n"
        "0 @D@ INDI\n1 SEX U\n"
        "0 @E@ INDI\n1 SEX\n"
        "0 @G@ INDI\n1 NAME No /Sex/\n"
        "0 TRLR\n",
        encoding="utf-8",
    )
    with GedcomParser(str(path)) as p:
        p.load()
        sexes = {x: p.get_sex(p.get_individual(x)) for x in "ABCDEG"}
    assert sexes == {"A": "M", "B": "M", "C": "F", "D": "U", "E": None, "G": None}


def test_half_blood_returns_false_not_none(sample_gedcom):
    """@F4@ has a HUSB and no WIFE; `is False` fails on a falsy None."""
    david = _family(sample_gedcom, "@I7@")
    assert sample_gedcom.half_blood(david, _family(sample_gedcom, "@I10@")) is False
    assert sample_gedcom.half_blood(david, _family(sample_gedcom, "@I8@")) is False


@pytest.fixture
def siblings_gedcom(tmp_path):
    """@H@ fathers every family but @FG@; @FA@ and @FB@ record no WIFE, and @FE@
    and @FF@ (also @FC@) are duplicate records of @H@ + @W1@."""
    path = tmp_path / "siblings.ged"
    path.write_text(
        "0 HEAD\n1 CHAR UTF-8\n"
        "0 @H@ INDI\n1 SEX M\n"
        "0 @W1@ INDI\n1 SEX F\n"
        "0 @W2@ INDI\n1 SEX F\n"
        "0 @X@ INDI\n1 SEX M\n"
        "0 @A1@ INDI\n1 FAMC @FA@\n"
        "0 @A2@ INDI\n1 FAMC @FA@\n"
        "0 @B1@ INDI\n1 FAMC @FB@\n"
        "0 @C1@ INDI\n1 FAMC @FC@\n"
        "0 @D1@ INDI\n1 FAMC @FD@\n"
        "0 @E1@ INDI\n1 FAMC @FE@\n"
        "0 @F1@ INDI\n1 FAMC @FF@\n"
        "0 @G1@ INDI\n1 FAMC @FG@\n"
        "0 @N1@ INDI\n"
        "0 @FA@ FAM\n1 HUSB @H@\n1 CHIL @A1@\n1 CHIL @A2@\n"
        "0 @FB@ FAM\n1 HUSB @H@\n1 CHIL @B1@\n"
        "0 @FC@ FAM\n1 HUSB @H@\n1 WIFE @W1@\n1 CHIL @C1@\n"
        "0 @FD@ FAM\n1 HUSB @H@\n1 WIFE @W2@\n1 CHIL @D1@\n"
        "0 @FE@ FAM\n1 HUSB @H@\n1 WIFE @W1@\n1 CHIL @E1@\n"
        "0 @FF@ FAM\n1 HUSB @H@\n1 WIFE @W1@\n1 CHIL @F1@\n"
        "0 @FG@ FAM\n1 HUSB @X@\n1 WIFE @W2@\n1 CHIL @G1@\n"
        "0 @S1@ INDI\n1 FAMC @FS@\n"
        "0 @FS@ FAM\n1 HUSB @W1@\n1 CHIL @S1@\n"
        "0 @R1@ INDI\n1 FAMC @FR@\n"
        "0 @FR@ FAM\n1 HUSB @W1@\n1 WIFE @H@\n1 CHIL @R1@\n"
        "0 TRLR\n",
        encoding="utf-8",
    )
    p = GedcomParser(str(path))
    p.load()
    yield p
    p.close()


@pytest.mark.parametrize(
    ("one", "two", "expected"),
    [
        ("@A1@", "@A2@", False),  # one FAMC with no WIFE
        ("@A1@", "@C1@", True),  # shared father, other FAMC has no WIFE
        ("@C1@", "@D1@", True),  # fully recorded, different mothers
        ("@D1@", "@G1@", True),  # shared mother only
        ("@E1@", "@F1@", False),  # same couple in duplicate FAM records
        ("@C1@", "@E1@", False),  # duplicate records again, fully recorded
        ("@C1@", "@G1@", False),  # different FAMCs, no parent in common
        ("@C1@", "@N1@", False),  # no FAMC at all
        ("@A1@", "@B1@", True),  # one father split over wife-less records: indistinguishable
        ("@C1@", "@S1@", True),  # @W1@ is WIFE in one family and HUSB in the other
        ("@C1@", "@R1@", False),  # same couple, HUSB and WIFE swapped
    ],
)
def test_half_blood_strict(siblings_gedcom, one, two, expected):
    fam1, fam2 = _family(siblings_gedcom, one), _family(siblings_gedcom, two)
    assert siblings_gedcom.half_blood(fam1, fam2) is expected


@pytest.fixture
def links_gedcom():
    """links.ged cases:

    @C1@  birth FAMC @F1@, then `PEDI Adopted` FAMC @F2@
    @C2@  only link is `PEDI adopted` to @F2@
    @C4@  `PEDI foster` to @F3@
    @C5@  birth FAMC @F1@; CHIL-only in @F4@ (mother's second family) -> step
    @C6@  CHIL-only in @F5@, no FAMC at all; @F5@ has a dangling HUSB before @P5@
    @C7@  FAMC @F5@ that @F5@ does not list as CHIL
    @C8@  child of @F6@: WIFE-only family, father @P6@ linked by FAMS alone
    @C9@  dangling FAMC listed before the real one
    @M5@  WIFE of @F5@ with no FAMS back-link
    @F7@  childless married couple; @H7@ is also a birth child of @F1@
    @F8@  childless unmarried couple
    @F9@/@F10@  duplicate records of @H9@ + @W9@, only the second with MARR
    """
    with GedcomParser(str(FIXTURES_DIR / "links.ged")) as p:
        p.load()
        yield p


def _ids(people):
    return [p.xref_id for p in people]


@pytest.mark.parametrize(
    ("child", "father", "mother"),
    [
        ("@C1@", "@P1@", "@M1@"),  # birth link preferred over the adoption
        ("@C2@", "@AP@", "@AM@"),
        ("@C4@", "@FP@", "@FM@"),
        ("@C5@", "@P1@", "@M1@"),  # birth link preferred over the step link
        ("@C6@", "@P5@", "@M5@"),
        ("@C7@", "@P5@", "@M5@"),
        ("@C8@", "@P6@", "@M6@"),
        ("@C9@", "@P1@", "@M1@"),
        ("@P1@", None, None),
    ],
)
def test_parents_links(links_gedcom, child, father, mother):
    assert _parents(links_gedcom, child) == (father, mother)


@pytest.mark.parametrize(
    ("child", "expected"),
    [
        (
            "@C1@",
            [
                ("@P1@", "@F1@", "birth"),
                ("@M1@", "@F1@", "birth"),
                ("@AP@", "@F2@", "adopted"),
                ("@AM@", "@F2@", "adopted"),
            ],
        ),
        ("@C4@", [("@FP@", "@F3@", "foster"), ("@FM@", "@F3@", "foster")]),
        (
            "@C5@",
            [
                ("@P1@", "@F1@", "birth"),
                ("@M1@", "@F1@", "birth"),
                ("@SF@", "@F4@", "step"),
                ("@M1@", "@F4@", "step"),
            ],
        ),
        ("@C6@", [("@P5@", "@F5@", "birth"), ("@M5@", "@F5@", "birth")]),
        ("@C9@", [("@P1@", "@F1@", "birth"), ("@M1@", "@F1@", "birth")]),
        ("@P1@", []),
    ],
)
def test_parent_links(links_gedcom, child, expected):
    links = links_gedcom.parent_links(links_gedcom.get_individual(child))
    assert [(p.xref_id, fam, link) for p, fam, link in links] == expected


@pytest.mark.parametrize(
    ("parent", "expected"),
    [
        (
            "@M1@",
            [
                ("@H7@", "@F1@", "birth"),
                ("@C1@", "@F1@", "birth"),
                ("@C5@", "@F1@", "birth"),
                ("@C9@", "@F1@", "birth"),
                ("@C5@", "@F4@", "step"),
            ],
        ),
        ("@AP@", [("@C1@", "@F2@", "adopted"), ("@C2@", "@F2@", "adopted")]),
        ("@M5@", [("@C6@", "@F5@", "birth"), ("@C7@", "@F5@", "birth")]),
        ("@H7@", []),
    ],
)
def test_child_links(links_gedcom, parent, expected):
    links = links_gedcom.child_links(links_gedcom.get_individual(parent))
    assert [(c.xref_id, fam, link) for c, fam, link in links] == expected


@pytest.mark.parametrize(
    ("one", "two", "expected"),
    [
        ("@H7@", "@W7@", True),
        ("@W7@", "@H7@", True),  # swapped order
        ("@H8@", "@W8@", False),  # no MARR
        ("@H7@", "@W8@", False),  # no shared family
        ("@H9@", "@W9@", True),  # only the second duplicate FAM has MARR
        ("@P6@", "@M6@", True),  # father linked by FAMS alone
        ("@H7@", "@H7@", False),
    ],
)
def test_is_couple_married(links_gedcom, one, two, expected):
    ind1, ind2 = links_gedcom.get_individual(one), links_gedcom.get_individual(two)
    assert links_gedcom.is_couple_married(ind1, ind2) is expected


@pytest.mark.parametrize(
    ("person", "expected"),
    [
        ("@H7@", ["@W7@"]),
        ("@W7@", ["@H7@"]),
        ("@P6@", ["@M6@"]),  # FAMS-only spouse
        ("@M6@", ["@P6@"]),
        ("@M5@", ["@P5@"]),  # WIFE line without a FAMS back-link
        ("@H9@", ["@W9@"]),  # duplicate families collapse to one spouse
        ("@M1@", ["@P1@", "@SF@"]),
        ("@C1@", []),
    ],
)
def test_spouses(links_gedcom, person, expected):
    assert _ids(links_gedcom.spouses(links_gedcom.get_individual(person))) == expected


@pytest.mark.parametrize(
    ("person", "expected"),
    [
        ("@C1@", ("@F1@", "birth")),  # birth family preferred over the adoption
        ("@C5@", ("@F1@", "birth")),  # and over the step family
        ("@C2@", ("@F2@", "adopted")),  # no birth family: the adoptive one
        ("@C4@", ("@F3@", "foster")),
        ("@C6@", ("@F5@", "birth")),  # CHIL-only
        ("@C9@", ("@F1@", "birth")),  # dangling FAMC skipped
        ("@P1@", None),
    ],
)
def test_parent_family(links_gedcom, person, expected):
    assert links_gedcom.parent_family(links_gedcom.get_individual(person)) == expected


def _write(path, records):
    path.write_text("0 HEAD\n1 CHAR UTF-8\n" + records + "0 TRLR\n", encoding="utf-8")
    return str(path)


def test_parent_family_none_when_no_family_has_parents(tmp_path):
    ged = _write(
        tmp_path / "orphan.ged",
        "0 @K@ INDI\n1 FAMC @F1@\n2 PEDI adopted\n1 FAMC @F2@\n"
        "0 @F1@ FAM\n1 CHIL @K@\n0 @F2@ FAM\n",
    )
    with GedcomParser(ged) as p:
        p.load()
        kid = p.get_individual("@K@")
        assert p.parent_family(kid) is None


def test_full_word_sex_seats_fams_only_spouse(tmp_path):
    ged = _write(
        tmp_path / "sex.ged",
        "0 @H@ INDI\n1 SEX Male\n1 FAMS @F1@\n"
        "0 @K@ INDI\n1 FAMC @F1@\n"
        "0 @F1@ FAM\n1 CHIL @K@\n",
    )
    with GedcomParser(ged) as p:
        p.load()
        assert p.couple("@F1@") == ("@H@", None)


RELOAD = (
    "0 @A@ INDI\n1 SEX M\n1 FAMS @F1@\n"
    "0 @B@ INDI\n1 SEX F\n1 FAMS @F1@\n1 FAMS @F2@\n"
    "0 @C@ INDI\n1 SEX M\n1 FAMS @F2@\n"
    "0 @K@ INDI\n1 FAMC @F1@\n"
    "0 @F1@ FAM\n1 HUSB @A@\n1 WIFE @B@\n1 CHIL @K@\n"
    "0 @F2@ FAM\n1 HUSB @C@\n1 WIFE @B@\n"
)


def test_reload_forgets_the_previous_file(tmp_path):
    path = tmp_path / "reload.ged"
    with GedcomParser(_write(path, RELOAD)) as p:
        p.load()
        assert p.couple("@F2@") == ("@C@", "@B@")
        first_file = p._reader._file

        indi = "0 @C@ INDI\n1 SEX M\n1 FAMS @F2@\n"
        fam = "0 @F2@ FAM\n1 HUSB @C@\n1 WIFE @B@\n"
        _write(path, RELOAD.replace(indi, "").replace(fam, ""))
        p.load()

        assert first_file.closed
        assert p.get_individual("@C@") is None
        assert p.couple("@F2@") == (None, None)
        assert _ids(p.spouses(p.get_individual("@B@"))) == ["@A@"]
        assert _parents(p, "@K@") == ("@A@", "@B@")


def test_failed_reload_leaves_nothing_half_built(tmp_path, monkeypatch):
    p = GedcomParser(_write(tmp_path / "fail.ged", RELOAD))
    p.load()

    def fill_then_fail(self):
        self._couple["@F1@"] = ["@A@", None]
        raise KeyboardInterrupt

    monkeypatch.setattr(GedcomParser, "_build_links", fill_then_fail)
    with pytest.raises(KeyboardInterrupt):
        p.load()

    assert p.gedcom is None
    assert p._reader is None
    assert p.get_individual("@A@") is None
    assert p.couple("@F1@") == (None, None)
    for index in (
        p._individuals,
        p._families,
        p._couple,
        p._famc_links,
        p._fam_children,
        p._spouse_fams,
    ):
        assert index == {}


@pytest.fixture
def slots_gedcom(tmp_path):
    """@FX@ has HUSB @B@ then a second HUSB @A@ (same-sex couple); @A@, @U@ and @E@
    also name it by FAMS. @V@ and @G@ name the spouseless @FY@ by FAMS alone."""
    path = tmp_path / "slots.ged"
    path.write_text(
        "0 HEAD\n1 CHAR UTF-8\n"
        "0 @B@ INDI\n1 SEX M\n"
        "0 @A@ INDI\n1 SEX M\n1 FAMS @FX@\n"
        "0 @U@ INDI\n1 SEX U\n1 FAMS @FX@\n"
        "0 @V@ INDI\n1 FAMS @FY@\n1 FAMS @FY@\n"
        "0 @G@ INDI\n1 SEX F\n1 FAMS @FY@\n"
        "0 @E@ INDI\n1 SEX M\n1 FAMS @FX@\n"
        "0 @K@ INDI\n1 FAMC @FZ@\n1 FAMC @FX@\n2 PEDI Sealing\n1 FAMC @FX@\n"
        "0 @FX@ FAM\n1 HUSB @B@\n1 HUSB @A@\n1 CHIL @K@\n1 CHIL @K@\n"
        "0 @FY@ FAM\n1 NOTE not a pointer\n"
        "0 @FZ@ FAM\n"
        "0 TRLR\n",
        encoding="utf-8",
    )
    with GedcomParser(str(path)) as p:
        p.load()
        yield p


@pytest.mark.parametrize(
    ("person", "expected"),
    [
        ("@B@", ["@A@"]),  # two HUSB lines: a same-sex couple
        ("@A@", ["@B@"]),
        ("@E@", []),  # FAMS-only, but both slots are taken
        ("@V@", ["@G@"]),  # unknown sex takes the first empty slot
        ("@G@", ["@V@"]),
    ],
)
def test_couple_slots(slots_gedcom, person, expected):
    ind = slots_gedcom.get_individual(person)
    assert _ids(slots_gedcom.spouses(ind)) == expected


def test_parents_skip_empty_family_and_unknown_pedigree(slots_gedcom):
    child = slots_gedcom.get_individual("@K@")
    assert _parents(slots_gedcom, "@K@") == ("@B@", "@A@")
    links = slots_gedcom.parent_links(child)
    assert [(p.xref_id, fam, link) for p, fam, link in links] == [
        ("@B@", "@FX@", "birth"),
        ("@A@", "@FX@", "birth"),
    ]
    assert _children(slots_gedcom, "@B@") == ["@K@"]


def test_half_blood_needs_two_families(links_gedcom):
    assert links_gedcom.half_blood("@F1@", "@F1@") is False
    assert links_gedcom.half_blood("@F1@", None) is False
    assert links_gedcom.half_blood("@F1@", "@F4@") is True
    assert links_gedcom.half_blood("@F9@", "@F10@") is False


def test_birth_year_bapm_fallback(special_gedcom):
    """I22 has no BIRT but has BAPM — birth year should fall back to BAPM."""
    ind = special_gedcom.get_individual("@I22@")
    assert special_gedcom.get_birth_year(ind) == "1900"


def test_load_calls_close_on_failure():
    """If records0() raises mid-load, close() must release the file descriptor."""
    sample = str(FIXTURES_DIR / "sample.ged")
    gp = GedcomParser(sample)
    opened = []
    original_init = GedcomReader.__init__

    def init_and_remember(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        opened.append(self)

    with (
        patch.object(GedcomReader, "__init__", init_and_remember),
        patch.object(GedcomReader, "records0", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError, match="boom"),
    ):
        gp.load()

    assert len(opened) == 1
    assert opened[0]._file.closed
    assert gp._reader is None


def test_extract_year_malformed_date(special_gedcom):
    """I23 has 'ABT UNKNOWN' as birth date, which carries no year."""
    ind = special_gedcom.get_individual("@I23@")
    year = special_gedcom.get_birth_year(ind)
    assert year is None


DATE_CASES = {
    "@D1@": ("1950", None),
    "@D2@": ("1950/51", None),
    "@D3@": ("500 BC", None),
    "@D4@": ("c. 1950", None),
    "@D5@": ("bef. 1900", None),
    "@D6@": ("aft. 1900", None),
    "@D7@": ("c. 1900", None),
    "@D8@": ("1850", None),
    "@D9@": ("c. 1800", None),
    "@D10@": ("c. 1950", None),
    "@D11@": ("1950", None),
    "@D12@": (None, None),
    "@D13@": ("1700", None),
    "@D14@": (None, None),
    "@D15@": ("1940", None),
    "@D16@": ("1940", None),
    "@D17@": ("1940", None),
    "@D18@": ("1940", None),
    "@D19@": ("1802", None),
    "@D20@": (None, "aft. 1990"),
    "@D21@": (None, "c. 1985"),
    "@D22@": (None, "2001"),
    "@D23@": (None, None),
    # Only a trailing year in free text counts; other numbers are not dates.
    "@D24@": (None, None),
    "@D25@": (None, None),
    "@D26@": ("1940", None),
    "@D27@": (None, None),
    "@D28@": ("1902", None),
    "@D29@": ("c. 1950", None),
    "@D30@": ("c. 1950", None),
    "@D31@": (None, None),
    "@D32@": ("1777", None),
    "@D33@": ("bef. 1850", None),
    "@D34@": ("aft. 1850", None),
    "@D35@": ("c. 1950", None),
    "@D36@": ("1950", None),
    "@D37@": (None, None),
    "@D38@": (None, None),
    "@D39@": (None, None),
    "@D40@": ("c. 1700", None),
    "@D41@": ("c. 1700", None),
    "@D42@": ("1700", None),
    "@D43@": ("bef. 1910", None),
    "@D44@": ("aft. 1900", None),
    # ged4py reads a short word before the year as a month, not as a phrase.
    "@D45@": ("1902", None),
    "@D46@": ("1950", None),
    "@D47@": (None, None),
    "@D48@": ("bef. 1850", None),
    "@D49@": ("1950", None),
}


@pytest.fixture(scope="module")
def dates_gedcom():
    # Loading at all is the regression test for unparseable dates: @D13@ and
    # @D14@ used to raise ValueError out of ged4py and abort the whole file. It
    # also guards the private ged4py hooks (_make_record, Date.freeze) we rely on.
    p = GedcomParser(str(FIXTURES_DIR / "dates.ged"))
    p.load()
    yield p
    p.close()


@pytest.mark.parametrize(("xref", "expected"), DATE_CASES.items())
def test_display_years(dates_gedcom, xref, expected):
    ind = dates_gedcom.get_individual(xref)
    assert (dates_gedcom.get_birth_year(ind), dates_gedcom.get_death_year(ind)) == expected


def test_date_cases_cover_fixture(dates_gedcom):
    assert {ind.xref_id for ind in dates_gedcom.gedcom} == set(DATE_CASES)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Abt. Jan. 1950", "c. 1950"),
        ("circa 3 March 1950", "c. 1950"),
        ("about 03 mar 1950", "c. 1950"),
        ("Before 1850", "bef. 1850"),
        ("after 1850", "aft. 1850"),
        ("b. 1850/51", "1850"),
        ("abt bef 1850", "c. 1850"),
        ("32 Jan 1950", None),
        ("Sept 1950", "1950"),
        ("@#DGREGORIAN@ approx 1950", "c. 1950"),
        ("@#DHEBREW@ abt 5700", None),
        ("1950 abt", None),
        ("abt", None),
        ("", None),
    ],
)
def test_phrase_year(text, expected):
    assert _phrase_year(text) == expected


def _load_names(tmp_path, data: bytes) -> list[str]:
    path = tmp_path / "names.ged"
    path.write_bytes(b"0 HEAD\n1 CHAR UTF-8\n" + data + b"0 TRLR\n")
    with GedcomParser(str(path)) as p:
        p.load()
        assert p.gedcom is not None
        return [p.get_name(ind) for ind in p.gedcom]


def test_get_name_empty_is_unknown(tmp_path):
    assert _load_names(tmp_path, b"0 @I1@ INDI\n1 NAME /\n0 @I2@ INDI\n1 NAME //\n") == [
        "Unknown",
        "Unknown",
    ]


def test_stray_byte_in_name_is_replaced(tmp_path):
    [name] = _load_names(tmp_path, b"0 @I1@ INDI\n1 NAME Jo\xffn /Smith/\n")
    assert "�" in name
    assert name.endswith("Smith")


def test_unknown_sex_spouse_does_not_take_a_sexed_slot(tmp_path):
    path = tmp_path / "order.ged"
    path.write_text(
        "0 HEAD\n1 CHAR UTF-8\n"
        "0 @U@ INDI\n1 FAMS @F1@\n"
        "0 @M@ INDI\n1 SEX M\n1 FAMS @F1@\n"
        "0 @C@ INDI\n1 FAMC @F1@\n"
        "0 @F1@ FAM\n1 CHIL @C@\n"
        "0 TRLR\n",
        encoding="utf-8",
    )
    with GedcomParser(str(path)) as p:
        p.load()
        assert p.couple("@F1@") == ("@M@", "@U@")
        assert _ids(p.spouses(p.get_individual("@M@"))) == ["@U@"]


@pytest.mark.parametrize(("pedi", "link"), [("Step", "step"), ("OTHER", "birth")])
def test_pedigree_kinds(tmp_path, pedi, link):
    path = tmp_path / "pedi.ged"
    path.write_text(
        "0 HEAD\n1 CHAR UTF-8\n"
        "0 @D@ INDI\n1 SEX M\n1 FAMS @F1@\n"
        f"0 @K@ INDI\n1 FAMC @F1@\n2 PEDI {pedi}\n"
        "0 @F1@ FAM\n1 HUSB @D@\n1 CHIL @K@\n"
        "0 TRLR\n",
        encoding="utf-8",
    )
    with GedcomParser(str(path)) as p:
        p.load()
        assert [
            (par.xref_id, fam, kind) for par, fam, kind in p.parent_links(p.get_individual("@K@"))
        ] == [("@D@", "@F1@", link)]


@pytest.mark.parametrize(
    "records",
    [
        "0 @A@ INDI\n1 SEX M\n1 FAMS @F1@\n0 @B@ INDI\n1 SEX M\n1 FAMS @F1@\n",
        "0 @A@ INDI\n1 SEX M\n0 @B@ INDI\n1 SEX M\n0 @F1@ FAM\n1 HUSB @A@\n1 HUSB @B@\n",
    ],
)
def test_same_sex_couple_keeps_both(tmp_path, records):
    path = tmp_path / "same.ged"
    fam = "" if "@F1@ FAM" in records else "0 @F1@ FAM\n"
    path.write_text(f"0 HEAD\n1 CHAR UTF-8\n{records}{fam}0 TRLR\n", encoding="utf-8")
    with GedcomParser(str(path)) as p:
        p.load()
        assert set(p.couple("@F1@")) == {"@A@", "@B@"}
        assert _ids(p.spouses(p.get_individual("@B@"))) == ["@A@"]


@pytest.mark.parametrize(("sex", "expected"), [("1 SEX M\n", ("@A@", None)), ("", (None, "@A@"))])
def test_lone_fams_only_spouse_slot(tmp_path, sex, expected):
    path = tmp_path / "lone.ged"
    path.write_text(
        f"0 HEAD\n1 CHAR UTF-8\n0 @A@ INDI\n{sex}1 FAMS @F1@\n0 @F1@ FAM\n0 TRLR\n",
        encoding="utf-8",
    )
    with GedcomParser(str(path)) as p:
        p.load()
        assert p.couple("@F1@") == expected


def test_stale_fams_does_not_join_the_couple(tmp_path):
    # @Z@ claims @F1@ but the family names @H@ as its husband.
    path = tmp_path / "stale.ged"
    path.write_text(
        "0 HEAD\n1 CHAR UTF-8\n"
        "0 @H@ INDI\n1 SEX M\n1 FAMS @F1@\n"
        "0 @Z@ INDI\n1 SEX M\n1 FAMS @F1@\n"
        "0 @F1@ FAM\n1 HUSB @H@\n"
        "0 TRLR\n",
        encoding="utf-8",
    )
    with GedcomParser(str(path)) as p:
        p.load()
        assert p.couple("@F1@") == ("@H@", None)
        assert p.spouses(p.get_individual("@H@")) == []


# @P@ is restricted; @C@'s birth alone is; @L@ is only LOCKED; @V@ uses a GEDCOM 7 list.
RESTRICTED = (
    "0 @P@ INDI\n1 NAME Secret /Parent/\n1 RESN privacy\n1 BIRT\n2 DATE 1985\n1 FAMS @F1@\n"
    "0 @C@ INDI\n1 NAME Kid /Parent/\n1 BIRT\n2 DATE 2015\n2 RESN confidential\n"
    "1 BAPM\n2 DATE 2015\n1 FAMC @F1@\n"
    "0 @L@ INDI\n1 NAME Locked /Record/\n1 RESN locked\n1 BIRT\n2 DATE 1950\n"
    "0 @V@ INDI\n1 NAME Seven /Style/\n1 RESN CONFIDENTIAL, LOCKED\n1 DEAT\n2 DATE 2001\n"
    "0 @F1@ FAM\n1 HUSB @P@\n1 CHIL @C@\n"
)


@pytest.mark.parametrize(
    ("xref", "name", "born", "died"),
    [
        ("@P@", "Private", None, None),
        ("@C@", "Kid Parent", None, None),  # no baptism year standing in for the birth
        ("@L@", "Locked Record", "1950", None),
        ("@V@", "Private", None, None),
    ],
)
def test_restricted_records_are_hidden(tmp_path, xref, name, born, died):
    with GedcomParser(_write(tmp_path / "resn.ged", RESTRICTED)) as p:
        p.load()
        ind = p.get_individual(xref)
        assert (p.get_name(ind), p.get_birth_year(ind), p.get_death_year(ind)) == (
            name,
            born,
            died,
        )


def test_include_private_shows_restricted_records(tmp_path):
    with GedcomParser(_write(tmp_path / "resn.ged", RESTRICTED), include_private=True) as p:
        p.load()
        parent, kid = p.get_individual("@P@"), p.get_individual("@C@")
        assert not p.is_private(parent)
        assert (p.get_name(parent), p.get_birth_year(parent)) == ("Secret Parent", "1985")
        assert p.get_birth_year(kid) == "2015"


def test_long_names_are_cut(tmp_path):
    with GedcomParser(
        _write(tmp_path / "long.ged", f"0 @I1@ INDI\n1 NAME {'x' * 5000} /Y/\n")
    ) as p:
        p.load()
        name = p.get_name(p.get_individual("@I1@"))
    assert len(name) == 200
    assert name.endswith("…")


@pytest.mark.parametrize(("include_private", "married"), [(False, False), (True, True)])
def test_a_private_persons_marriage_is_hidden(tmp_path, include_private, married):
    ged = _write(
        tmp_path / "marr.ged",
        "0 @H@ INDI\n1 SEX M\n1 FAMS @F1@\n"
        "0 @W@ INDI\n1 SEX F\n1 RESN privacy\n1 FAMS @F1@\n"
        "0 @F1@ FAM\n1 HUSB @H@\n1 WIFE @W@\n1 MARR\n2 DATE 2010\n",
    )
    with GedcomParser(ged, include_private=include_private) as p:
        p.load()
        husband, wife = p.get_individual("@H@"), p.get_individual("@W@")
        assert p.is_couple_married(husband, wife) is married
        assert p.is_couple_married(wife, husband) is married
