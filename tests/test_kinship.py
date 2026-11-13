from pathlib import Path

import pytest

from gedgraph.kinship import describe, sentence
from gedgraph.parser import GedcomParser
from gedgraph.pathfinder import PathFinder, PathStep, RelationshipPath, is_half

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class _StubParser:
    """Individuals are their own xref strings; "@GONE@" is never found."""

    def __init__(self, sex=None, half=(), married=()):
        self.sex = sex
        self.half = {frozenset(pair) for pair in half}
        self.married = {frozenset(pair) for pair in married}
        self.half_calls = []

    def get_individual(self, xref):
        return None if xref == "@GONE@" else xref

    def get_sex(self, _individual):
        return self.sex

    def is_private(self, _individual):
        return False

    def half_blood(self, fam1, fam2):
        self.half_calls.append((fam1, fam2))
        return frozenset((fam1, fam2)) in self.half

    def is_couple_married(self, one, two):
        return frozenset((one, two)) in self.married


# move letter -> (is_parent, link)
_MOVES = {
    "U": (True, "birth"),
    "D": (False, "birth"),
    "A": (True, "adopted"),
    "a": (False, "adopted"),
    "F": (True, "foster"),
    "f": (False, "foster"),
    "T": (True, "step"),
    "t": (False, "step"),
    "S": (False, "spouse"),
}


def _path(moves, start="@S@"):
    """Step i lands on "@Pi@" and goes through the family "@F<child>@" of its lower person.

    U/D go up/down a birth link; for the other links upper case is up and lower
    case down: A/a adopted, F/f foster, T/t step. S is a spouse step.
    """
    steps = []
    here = start
    for i, move in enumerate(moves, 1):
        there = f"@P{i}@"
        up, link = _MOVES[move]
        family = None if link == "spouse" else "@F" + (here if up else there).strip("@") + "@"
        steps.append(PathStep(there, is_parent=up, via_male=True, link=link, family=family))
        here = there
    return RelationshipPath(steps=steps, start_id=start, end_id=here)


@pytest.mark.parametrize(
    ("moves", "sex", "expected"),
    [
        ("U", "M", "father"),
        ("U", "F", "mother"),
        ("U", None, "parent"),
        ("UU", "M", "grandfather"),
        ("UU", None, "grandparent"),
        ("UUU", "F", "great-grandmother"),
        ("UUU", None, "great-grandparent"),
        ("UUUU", "M", "2nd great-grandfather"),
        ("UUUU", None, "2nd great-grandparent"),
        ("D", "M", "son"),
        ("D", "F", "daughter"),
        ("D", None, "child"),
        ("DD", "F", "granddaughter"),
        ("DD", None, "grandchild"),
        ("DDD", "M", "great-grandson"),
        ("DDDD", None, "2nd great-grandchild"),
        ("UD", "M", "brother"),
        ("UD", "F", "sister"),
        ("UD", None, "sibling"),
        ("UUD", "M", "uncle"),
        ("UUD", "F", "aunt"),
        ("UUD", None, "parent's sibling"),
        ("UUUD", "M", "great-uncle"),
        ("UUUD", None, "grandparent's sibling"),
        ("UUUUD", "F", "2nd great-aunt"),
        ("UUUUD", None, "great-grandparent's sibling"),
        ("UDD", "M", "nephew"),
        ("UDD", "F", "niece"),
        ("UDD", None, "sibling's child"),
        ("UDDD", "M", "great-nephew"),
        ("UDDD", None, "sibling's grandchild"),
        ("UDDDD", "F", "2nd great-niece"),
        ("UDDDD", None, "sibling's great-grandchild"),
        ("UUDD", "M", "first cousin"),
        ("UUUDDD", None, "second cousin"),
        ("UUUUDDDD", "F", "third cousin"),
        ("U" * 11 + "D" * 11, None, "tenth cousin"),
        ("U" * 12 + "D" * 12, None, "11th cousin"),
        ("UUUDD", None, "first cousin once removed"),
        ("UUDDD", None, "first cousin once removed"),
        ("UUUUDD", None, "first cousin twice removed"),
        ("UUUUUUDDD", None, "second cousin 3 times removed"),
    ],
)
def test_blood_terms(moves, sex, expected):
    assert describe(_path(moves), _StubParser(sex=sex)) == expected


@pytest.mark.parametrize(
    ("greats", "expected"),
    [
        (2, "2nd"),
        (3, "3rd"),
        (4, "4th"),
        (11, "11th"),
        (12, "12th"),
        (13, "13th"),
        (21, "21st"),
        (22, "22nd"),
        (23, "23rd"),
        (111, "111th"),
    ],
)
def test_great_ordinals(greats, expected):
    path = _path("U" * (greats + 2))
    assert describe(path, _StubParser(sex="M")) == f"{expected} great-grandfather"


@pytest.mark.parametrize(
    ("sex", "expected"),
    [("M", "brother"), ("F", "sister"), ("U", "sibling"), (None, "sibling")],
)
def test_sex_words(sex, expected):
    assert describe(_path("UD"), _StubParser(sex=sex)) == expected


def test_missing_end_individual_is_neutral():
    path = RelationshipPath([PathStep("@GONE@", is_parent=True, via_male=True)], "@S@", "@GONE@")
    assert describe(path, _StubParser(sex="M")) == "parent"


def test_path_step_link_is_keyword_only():
    with pytest.raises(TypeError):
        PathStep("@P1@", True, True, "adopted")


@pytest.mark.parametrize(
    ("moves", "pair", "expected"),
    [
        ("UD", ("@FS@", "@FP2@"), "half-brother"),
        ("UDD", ("@FS@", "@FP2@"), "half-nephew"),
        ("UUD", ("@FP1@", "@FP3@"), "half-uncle"),
        ("UUUD", ("@FP2@", "@FP4@"), "half-great-uncle"),
        ("UUDD", ("@FP1@", "@FP3@"), "half-first cousin"),
        ("UUUDD", ("@FP2@", "@FP4@"), "half-first cousin once removed"),
        ("UUDD", ("@FS@", "@FP3@"), "first cousin"),
        ("UU", ("@FS@", "@FP2@"), "grandfather"),
    ],
)
def test_half_blood(moves, pair, expected):
    assert describe(_path(moves), _StubParser(sex="M", half=[pair])) == expected


@pytest.mark.parametrize(
    ("moves", "pair", "expected"),
    [
        ("UUD", ("@FP1@", "@FP3@"), "parent's half-sibling"),
        ("UUUD", ("@FP2@", "@FP4@"), "grandparent's half-sibling"),
        ("UDD", ("@FS@", "@FP2@"), "half-sibling's child"),
    ],
)
def test_half_blood_neutral(moves, pair, expected):
    """With no recorded sex the half belongs to the sibling, not the parent."""
    assert describe(_path(moves), _StubParser(sex="", half=[pair])) == expected


@pytest.mark.parametrize(
    ("moves", "expected"),
    [
        ("UaD", "adoptive nephew"),
        ("UUfD", "foster first cousin"),
        ("Ta", "stepbrother"),
        ("At", "stepbrother"),
        ("Fa", "foster brother"),
        ("Af", "foster brother"),
        ("Ut", "stepbrother"),
        ("TD", "stepbrother"),
        ("UUtD", "relative by marriage"),
        ("SU", "relative by marriage"),
    ],
)
def test_non_birth_links(moves, expected):
    assert describe(_path(moves), _StubParser(sex="M")) == expected


def test_non_birth_link_is_never_half():
    stub = _StubParser(sex="M", half=[("@FS@", "@FP2@")])
    assert describe(_path("UaD"), stub) == "adoptive nephew"
    assert stub.half_calls == []


@pytest.mark.parametrize("moves", ["", "UU", "DD", "UDU", "UaD", "S"])
def test_is_half_needs_birth_apex(moves):
    stub = _StubParser(half=[("@FS@", "@FP2@")])
    assert is_half(_path(moves), stub) is False
    assert stub.half_calls == []


@pytest.mark.parametrize(
    ("sex", "married", "expected"),
    [
        ("M", True, "husband"),
        ("F", True, "wife"),
        (None, True, "spouse"),
        ("F", False, "partner"),
    ],
)
def test_spouse_or_partner(sex, married, expected):
    stub = _StubParser(sex=sex, married=[("@S@", "@P1@")] if married else [])
    assert describe(_path("S"), stub) == expected


def test_partner_when_start_missing():
    stub = _StubParser(sex="F", married=[("@GONE@", "@P1@")])
    assert describe(_path("S", start="@GONE@"), stub) == "partner"


# "DU" is what joins a birth father to an adoptive one; co-parents who are a
# couple come back as a single spouse step instead.
@pytest.mark.parametrize("moves", ["DU", "DUU", "DDU", "DUUD", "UDUD", "DUD"])
def test_relative_by_marriage(moves):
    assert describe(_path(moves), _StubParser(sex="M")) == "relative by marriage"


def test_same_person():
    assert describe(_path(""), _StubParser(sex="M")) is None


@pytest.fixture(scope="module")
def layout():
    p = GedcomParser(str(FIXTURES_DIR / "layout.ged"))
    p.load()
    yield p
    p.close()


def _describe_shortest(parser, start, end):
    return describe(PathFinder(parser).get_shortest_paths(start, end)[0], parser)


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("@G0@", "@GC@", "first cousin"),
        ("@G0@", "@GU@", "uncle"),
        ("@GU@", "@G0@", "nephew"),
        ("@G0@", "@GW@", "wife"),
        ("@GW@", "@G0@", "husband"),
        ("@G0@", "@K.1@", "daughter"),
        ("@G0@", "@KC@", "grandson"),
        ("@KC@", "@G0@", "grandfather"),
        ("@G0@", "@GPM@", "grandmother"),
        ("@G0@", "@GUW@", "relative by marriage"),
    ],
)
def test_layout_end_to_end(layout, start, end, expected):
    assert _describe_shortest(layout, start, end) == expected


def test_half_sibling_end_to_end(tmp_path):
    path = tmp_path / "half.ged"
    path.write_text(
        "0 HEAD\n1 CHAR UTF-8\n"
        "0 @H@ INDI\n1 SEX M\n1 FAMS @F1@\n1 FAMS @F2@\n"
        "0 @W1@ INDI\n1 SEX F\n1 FAMS @F1@\n"
        "0 @W2@ INDI\n1 SEX F\n1 FAMS @F2@\n"
        "0 @A@ INDI\n1 SEX M\n1 FAMC @F1@\n"
        "0 @B@ INDI\n1 SEX M\n1 FAMC @F2@\n"
        "0 @F1@ FAM\n1 HUSB @H@\n1 WIFE @W1@\n1 CHIL @A@\n"
        "0 @F2@ FAM\n1 HUSB @H@\n1 WIFE @W2@\n1 CHIL @B@\n"
        "0 TRLR\n",
        encoding="utf-8",
    )
    with GedcomParser(str(path)) as parser:
        parser.load()
        assert _describe_shortest(parser, "@A@", "@B@") == "half-brother"


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("@AP@", "@C1@", "adoptive son"),
        ("@C1@", "@AP@", "adoptive father"),
        ("@AM@", "@C2@", "adoptive daughter"),
        ("@C2@", "@AM@", "adoptive mother"),
        ("@FM@", "@C4@", "foster son"),
        ("@C4@", "@FP@", "foster father"),
        ("@SF@", "@C5@", "stepdaughter"),
        ("@C5@", "@SF@", "stepfather"),
        ("@P5@", "@C6@", "son"),  # CHIL-only
        ("@C6@", "@P5@", "father"),
        ("@M5@", "@C7@", "daughter"),  # FAMC-only
        ("@C7@", "@P5@", "father"),
        ("@C1@", "@C5@", "sister"),
        ("@C1@", "@C2@", "adoptive sister"),
        ("@H7@", "@W7@", "wife"),  # childless: found only through the marriage
        ("@W7@", "@H7@", "husband"),
        ("@H8@", "@W8@", "partner"),
        ("@W8@", "@H8@", "partner"),
        ("@H9@", "@W9@", "wife"),
        ("@W7@", "@P1@", "relative by marriage"),
        ("@SF@", "@M1@", "partner"),
        ("@SF@", "@P1@", "relative by marriage"),
        ("@AP@", "@P1@", "relative by marriage"),
    ],
)
def test_links_end_to_end(links, start, end, expected):
    paths = PathFinder(links).get_shortest_paths(start, end)
    assert describe(paths[0], links) == expected


@pytest.mark.parametrize(
    ("start", "end"), [("@SF@", "@M1@"), ("@H8@", "@W8@"), ("@W8@", "@H8@"), ("@P1@", "@M1@")]
)
def test_couples_are_one_spouse_step(links, start, end):
    [path] = PathFinder(links).get_shortest_paths(start, end)
    assert [s.link for s in path.steps] == ["spouse"]


def test_full_route_beats_half_route():
    with GedcomParser(str(FIXTURES_DIR / "fullhalf.ged")) as parser:
        parser.load()
        assert _describe_shortest(parser, "@X@", "@Y@") == "first cousin"
        assert _describe_shortest(parser, "@Y@", "@X@") == "first cousin"


def test_half_route_alone_stays_half(tmp_path):
    path = tmp_path / "halfonly.ged"
    path.write_text(
        "0 HEAD\n1 CHAR UTF-8\n"
        "0 @GP@ INDI\n1 NAME Gordon /Green/\n1 SEX M\n1 FAMS @B1@\n1 FAMS @B2@\n"
        "0 @W1@ INDI\n1 NAME Wanda /Green/\n1 SEX F\n1 FAMS @B1@\n"
        "0 @W2@ INDI\n1 NAME Willa /Green/\n1 SEX F\n1 FAMS @B2@\n"
        "0 @F2@ INDI\n1 NAME Felix /Green/\n1 SEX M\n1 FAMC @B1@\n1 FAMS @XF@\n"
        "0 @M2@ INDI\n1 NAME Mona /Green/\n1 SEX F\n1 FAMC @B2@\n1 FAMS @YF@\n"
        "0 @X@ INDI\n1 NAME Xena /X/\n1 SEX F\n1 FAMC @XF@\n"
        "0 @Y@ INDI\n1 NAME Yuri /Y/\n1 SEX M\n1 FAMC @YF@\n"
        "0 @B1@ FAM\n1 HUSB @GP@\n1 WIFE @W1@\n1 CHIL @F2@\n"
        "0 @B2@ FAM\n1 HUSB @GP@\n1 WIFE @W2@\n1 CHIL @M2@\n"
        "0 @XF@ FAM\n1 HUSB @F2@\n1 CHIL @X@\n"
        "0 @YF@ FAM\n1 WIFE @M2@\n1 CHIL @Y@\n"
        "0 TRLR\n",
        encoding="utf-8",
    )
    with GedcomParser(str(path)) as parser:
        parser.load()
        assert _describe_shortest(parser, "@X@", "@Y@") == "half-first cousin"


@pytest.mark.parametrize(
    ("term", "steps", "expected"),
    [
        ("son", 1, "Bo is Al's son (1 step)"),
        ("first cousin", 4, "Bo is Al's first cousin (4 steps)"),
        (None, 0, "Al and Bo are the same person"),
    ],
)
def test_sentence(term, steps, expected):
    assert sentence("Al", "Bo", term, steps) == expected


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("@I1@", "@I3@", "Robert Smith is John Smith's son (1 step)"),
        ("@I3@", "@I1@", "John Smith is Robert Smith's father (1 step)"),
        ("@I7@", "@I8@", "Emily Smith is David Smith's sister (2 steps)"),
        ("@I1@", "@I7@", "David Smith is John Smith's great-grandson (3 steps)"),
        ("@I7@", "@I1@", "John Smith is David Smith's great-grandfather (3 steps)"),
        ("@I1@", "@I2@", "Mary Jones is John Smith's partner (1 step)"),
        ("@I2@", "@I4@", "Sarah Brown is Mary Jones's relative by marriage (2 steps)"),
        ("@I9@", "@I10@", "Lisa Williams is James Williams's daughter (1 step)"),
        ("@I1@", "@I1@", "John Smith and John Smith are the same person"),
    ],
)
def test_sample_sentences(parser, start, end, expected):
    path = PathFinder(parser).get_shortest_paths(start, end)[0]
    one, two = (parser.get_name(parser.get_individual(x)) for x in (start, end))
    assert sentence(one, two, describe(path, parser), path.length()) == expected


# @P@ adopted @A@ in @F1@ and is the stepfather of @X@, whose birth family is @F3@.
_MIXED = (
    "0 @A@ INDI\n1 SEX M\n1 FAMC @F1@\n2 PEDI adopted\n"
    "0 @P@ INDI\n1 SEX M\n1 FAMS @F1@\n1 FAMS @F2@\n"
    "0 @Q@ INDI\n1 SEX F\n1 FAMS @F1@\n"
    "0 @R@ INDI\n1 SEX F\n1 FAMS @F2@\n1 FAMS @F3@\n"
    "0 @S@ INDI\n1 SEX M\n1 FAMS @F3@\n"
    "0 @X@ INDI\n1 SEX M\n1 FAMC @F3@\n"
    "0 @F1@ FAM\n1 HUSB @P@\n1 WIFE @Q@\n1 CHIL @A@\n"
    "0 @F2@ FAM\n1 HUSB @P@\n1 WIFE @R@\n1 CHIL @X@\n"
    "0 @F3@ FAM\n1 HUSB @S@\n1 WIFE @R@\n1 CHIL @X@\n"
)


@pytest.mark.parametrize(("start", "end"), [("@A@", "@X@"), ("@X@", "@A@")])
def test_mixed_links_name_the_same_tie_from_both_ends(load, start, end):
    parser = load(_MIXED)
    path = PathFinder(parser).get_shortest_paths(start, end)[0]
    assert {step.link for step in path.steps} == {"adopted", "step"}
    assert describe(path, parser) == "stepbrother"
