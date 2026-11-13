"""Tests for relationship path finding."""

from pathlib import Path

import pytest

import gedgraph.pathfinder as pf_mod
from gedgraph.kinship import describe
from gedgraph.parser import GedcomParser
from gedgraph.pathfinder import PathFinder

FIXTURES_DIR = Path(__file__).parent / "fixtures"


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


def _trace(paths):
    return [
        [(s.individual_id, s.is_parent, s.via_male, s.link, s.family) for s in p.steps]
        for p in paths
    ]


# The cap counts search states. @I1@ -> @I7@ goes down through @I3@ and @I5@ (two
# states); @I7@'s sister @I8@ is the one state at the end's depth, and the cap may
# turn her away without costing the path found in that level.
@pytest.mark.parametrize(("cap", "found"), [(1, False), (2, True)])
def test_cap_only_cuts_a_search_before_any_path(pathfinder, monkeypatch, cap, found):
    monkeypatch.setattr(pf_mod, "_MAX_NODES", cap)
    paths = pathfinder.get_shortest_paths("@I1@", "@I7@")
    assert bool(paths) is found
    assert pathfinder.truncated is not found


def test_bfs_cap_does_not_affect_normal_search(pathfinder):
    """Default _MAX_NODES is large enough for the sample GEDCOM."""
    paths = pathfinder.find_relationship_paths("@I1@", "@I7@")
    assert {p.length() for p in paths} == {3}
    assert pathfinder.truncated is False


def test_cap_not_reached(pathfinder, monkeypatch):
    monkeypatch.setattr(pf_mod, "_MAX_NODES", 6)
    assert pathfinder.get_shortest_paths("@I1@", "@I7@")
    assert pathfinder.truncated is False


def test_truncated_resets_on_each_search(pathfinder, monkeypatch):
    monkeypatch.setattr(pf_mod, "_MAX_NODES", 0)
    pathfinder.find_relationship_paths("@I1@", "@I7@")
    assert pathfinder.truncated is True
    assert pathfinder.find_relationship_paths("@I1@", "@I1@")
    assert pathfinder.truncated is False
    pathfinder.find_relationship_paths("@I1@", "@I7@")
    assert pathfinder.find_relationship_paths("@I1@", "@NOPE@") == []
    assert pathfinder.truncated is False


def test_shortest_path_steps(pathfinder):
    paths = pathfinder.get_shortest_paths("@I7@", "@I1@")
    assert _trace(paths) == [
        [
            ("@I5@", True, True, "birth", "@F3@"),
            ("@I3@", True, True, "birth", "@F2@"),
            ("@I1@", True, True, "birth", "@F1@"),
        ]
    ]
    assert paths[0].ids() == ["@I7@", "@I5@", "@I3@", "@I1@"]


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [("I1", "@I1@", ("@I1@", "@I1@")), ("I6", "I5", ("@I6@", "@I5@"))],
)
def test_paths_carry_canonical_ids(pathfinder, start, end, expected):
    paths = pathfinder.get_shortest_paths(start, end)
    assert paths
    assert all((p.start_id, p.end_id) == expected for p in paths)


def test_links_are_symmetric(links):
    finder = PathFinder(links)
    people = sorted(links._individuals)
    for one in people:
        for two in people:
            there = finder.get_shortest_paths(one, two)
            back = finder.get_shortest_paths(two, one)
            assert bool(there) == bool(back), (one, two)
            if there:
                assert there[0].length() == back[0].length(), (one, two)


@pytest.mark.parametrize(
    ("person", "expected"),
    [
        (
            "@C5@",
            [
                ("@P1@", True, True, "birth", "@F1@"),
                ("@M1@", True, False, "birth", "@F1@"),  # not the step link via @F4@
                ("@SF@", True, True, "step", "@F4@"),
            ],
        ),
        (
            "@M1@",
            [
                ("@H7@", False, False, "birth", "@F1@"),
                ("@C1@", False, False, "birth", "@F1@"),
                ("@C5@", False, False, "birth", "@F1@"),
                ("@C9@", False, False, "birth", "@F1@"),
            ],
        ),
        ("@P6@", [("@C8@", False, True, "birth", "@F6@")]),
    ],
)
def test_one_neighbour_per_person(links, person, expected):
    neighbours = PathFinder(links)._get_neighbors(links.get_individual(person), spouses=False)
    steps = [(s.individual_id, s.is_parent, s.via_male, s.link, s.family) for _, s in neighbours]
    assert steps == expected


def test_spouse_neighbours_only_in_second_search(links):
    finder = PathFinder(links)
    h7 = links.get_individual("@H7@")
    assert [s.link for _, s in finder._get_neighbors(h7, spouses=False)] == ["birth", "birth"]
    with_spouses = finder._get_neighbors(h7, spouses=True)
    assert [(s.individual_id, s.link, s.via_male) for _, s in with_spouses][-1] == (
        "@W7@",
        "spouse",
        True,
    )


def test_childless_couple_found_through_marriage(links):
    paths = PathFinder(links).get_shortest_paths("@H7@", "@W7@")
    assert _trace(paths) == [[("@W7@", False, True, "spouse", None)]]


def test_couple_with_a_child_is_one_spouse_step(links):
    # @M1@ is also the mother of @SF@'s stepdaughter, but going down to the
    # child and back up to her mother is not a line of descent.
    paths = PathFinder(links).get_shortest_paths("@SF@", "@M1@")
    assert _trace(paths) == [[("@M1@", False, True, "spouse", None)]]


def test_birth_and_adoptive_fathers_are_related_by_marriage(links):
    # @C1@ was born to @P1@ and adopted by @AP@; the fathers share no blood line.
    paths = PathFinder(links).find_relationship_paths("@P1@", "@AP@")
    assert _trace(paths) == [
        [("@C1@", False, True, "birth", "@F1@"), ("@AP@", True, True, "adopted", "@F2@")]
    ]
    assert describe(paths[0], links) == "relative by marriage"


def test_spouse_found_when_blood_search_hits_cap(links, monkeypatch):
    monkeypatch.setattr(pf_mod, "_MAX_NODES", 0)
    finder = PathFinder(links)
    assert _trace(finder.get_shortest_paths("@H7@", "@W7@")) == [
        [("@W7@", False, True, "spouse", None)]
    ]
    # Still set: a blood tie past the cap may have been missed.
    assert finder.truncated is True


def test_capped_blood_search_does_not_fall_back_to_in_laws(links, monkeypatch):
    # Uncapped, @P1@ reaches his son's wife through the marriage search.
    assert PathFinder(links).get_shortest_paths("@P1@", "@W7@")[0].steps[-1].link == "spouse"
    # The blood search from @P1@ holds just his four children; three is too few.
    monkeypatch.setattr(pf_mod, "_MAX_NODES", 3)
    finder = PathFinder(links)
    assert finder.get_shortest_paths("@P1@", "@W7@") == []
    assert finder.truncated is True


def test_depth_limit_does_not_fall_back_to_in_laws(cousins):
    finder = PathFinder(cousins)
    assert finder.get_shortest_paths("@A@", "@B@", max_depth=3) == []
    assert finder.truncated is False
    assert finder.depth_limited is True
    assert finder.get_shortest_paths("@A@", "@B@", max_depth=4)[0].length() == 4
    assert finder.depth_limited is False


def test_depth_limited_resets_on_each_search(cousins):
    finder = PathFinder(cousins)
    finder.find_relationship_paths("@A@", "@B@", max_depth=3)
    assert finder.depth_limited is True
    assert finder.find_relationship_paths("@A@", "@A@", max_depth=3)
    assert finder.depth_limited is False
    finder.find_relationship_paths("@A@", "@B@", max_depth=3)
    assert finder.find_relationship_paths("@A@", "@NOPE@", max_depth=3) == []
    assert finder.depth_limited is False


def test_spouse_kept_when_depth_limit_hides_blood_tie(cousins):
    finder = PathFinder(cousins)
    assert _trace(finder.get_shortest_paths("@A@", "@S@", max_depth=3)) == [
        [("@S@", False, True, "spouse", None)]
    ]
    assert finder.depth_limited is True


def test_cousin_marriage_is_a_blood_tie(cousins):
    paths = PathFinder(cousins).get_shortest_paths("@A@", "@S@")
    assert [p.ids() for p in paths] == [["@A@", "@P1@", "@G@", "@P2@", "@S@"]]
    assert describe(paths[0], cousins) == "first cousin"


# @K@ -> @P@ -> @G@, and @X@ unrelated. No marriages, so both searches walk the
# same three people.
LINE = (
    "0 @G@ INDI\n1 SEX M\n1 FAMS @F1@\n"
    "0 @P@ INDI\n1 SEX M\n1 FAMC @F1@\n1 FAMS @F2@\n"
    "0 @K@ INDI\n1 SEX M\n1 FAMC @F2@\n"
    "0 @X@ INDI\n1 SEX M\n"
    "0 @F1@ FAM\n1 HUSB @G@\n1 CHIL @P@\n"
    "0 @F2@ FAM\n1 HUSB @P@\n1 CHIL @K@\n"
)


@pytest.mark.parametrize(("max_depth", "limited"), [(1, True), (2, False), (3, False)])
def test_depth_limited_only_with_someone_left_to_reach(load, max_depth, limited):
    # At depth 2 the frontier is @G@, whose one step leads back down to @P@,
    # already reached by climbing: the tree has run out, not the depth.
    finder = PathFinder(load(LINE))
    assert finder.find_relationship_paths("@K@", "@X@", max_depth=max_depth) == []
    assert finder.depth_limited is limited
    assert finder.truncated is False


def _ladder(generations):
    """Each couple's son and daughter have one child each, and those cousins marry.

    @H0@ and @W0@ head the ladder; @Pi@ and @Qi@ are the son and daughter of the
    couple @H(i-1)@ + @W(i-1)@, and @Hi@ (son of @Pi@) married @Wi@ (daughter of
    @Qi@). The last couple has two children, @S@ and @T@.
    """
    people = ["0 @H0@ INDI\n1 SEX M\n1 FAMS @C0@\n", "0 @W0@ INDI\n1 SEX F\n1 FAMS @C0@\n"]
    families = []
    for i in range(1, generations + 1):
        people += [
            f"0 @P{i}@ INDI\n1 SEX M\n1 FAMC @C{i - 1}@\n1 FAMS @A{i}@\n",
            f"0 @Q{i}@ INDI\n1 SEX F\n1 FAMC @C{i - 1}@\n1 FAMS @B{i}@\n",
            f"0 @H{i}@ INDI\n1 SEX M\n1 FAMC @A{i}@\n1 FAMS @C{i}@\n",
            f"0 @W{i}@ INDI\n1 SEX F\n1 FAMC @B{i}@\n1 FAMS @C{i}@\n",
        ]
        j = i - 1
        families += [
            f"0 @C{j}@ FAM\n1 HUSB @H{j}@\n1 WIFE @W{j}@\n1 CHIL @P{i}@\n1 CHIL @Q{i}@\n",
            f"0 @A{i}@ FAM\n1 HUSB @P{i}@\n1 CHIL @H{i}@\n",
            f"0 @B{i}@ FAM\n1 WIFE @Q{i}@\n1 CHIL @W{i}@\n",
        ]
    k = generations
    people += [f"0 @S@ INDI\n1 SEX M\n1 FAMC @C{k}@\n", f"0 @T@ INDI\n1 SEX F\n1 FAMC @C{k}@\n"]
    families.append(f"0 @C{k}@ FAM\n1 HUSB @H{k}@\n1 WIFE @W{k}@\n1 CHIL @S@\n1 CHIL @T@\n")
    return "".join(people + families)


# Six generations: @S@ reaches @H0@ in 13 steps along 2**6 = 64 shortest routes.
# Searching from @S@, every ancestor is reached climbing, two per depth: @H6@ and
# @W6@ at 1, @P6@ and @Q6@ at 2, @H5@ and @W5@ at 3, ... @P1@ and @Q1@ at 12, so
# 2 * 12 = 24 states. Steps back down to someone already climbed to are dropped;
# the only state reached going down is @T@, at depth 2 (sister of @S@). That makes
# 25 states before the end's depth. At depth 13, @W0@ is the one other state; with
# a cap of 25 she is turned away, but @H0@ is found in that same level.
LADDER_STATES = 25


@pytest.fixture
def ladder(load):
    return load(_ladder(6))


@pytest.mark.parametrize(("cap", "found"), [(LADDER_STATES - 1, False), (LADDER_STATES, True)])
def test_cap_counts_each_state_once(ladder, monkeypatch, cap, found):
    monkeypatch.setattr(pf_mod, "_MAX_NODES", cap)
    finder = PathFinder(ladder)
    paths = finder.find_relationship_paths("@S@", "@H0@")
    assert bool(paths) is found
    assert finder.truncated is not found
    if found:
        assert len(paths) == 64


def test_every_tied_route_comes_back(ladder):
    finder = PathFinder(ladder)
    paths = finder.find_relationship_paths("@S@", "@H0@")
    assert len(paths) == 64
    assert len({tuple(p.ids()) for p in paths}) == 64
    assert {p.length() for p in paths} == {13}
    male_line = ["@S@"] + [f"@{x}{i}@" for i in range(6, 0, -1) for x in "HP"] + ["@H0@"]
    assert [p.ids() for p in finder.get_shortest_paths("@S@", "@H0@")] == [male_line]


def test_path_budget_keeps_the_length(ladder, monkeypatch):
    # Past the budget the extra routes are dropped silently; the relationship is
    # still the shortest one.
    monkeypatch.setattr(pf_mod, "_MAX_PATHS", 4)
    paths = PathFinder(ladder).find_relationship_paths("@S@", "@H0@")
    assert len(paths) == 4
    assert {p.length() for p in paths} == {13}


def test_shared_grandchild_does_not_hide_second_cousins(load):
    # @X@ and @Y@ are second cousins whose children married each other.
    parser = load(
        "0 @Z@ INDI\n1 SEX M\n1 FAMS @FZ@\n"
        "0 @A1@ INDI\n1 SEX M\n1 FAMC @FZ@\n1 FAMS @FA1@\n"
        "0 @A2@ INDI\n1 SEX M\n1 FAMC @FA1@\n1 FAMS @FA2@\n"
        "0 @B1@ INDI\n1 SEX M\n1 FAMC @FZ@\n1 FAMS @FB1@\n"
        "0 @B2@ INDI\n1 SEX M\n1 FAMC @FB1@\n1 FAMS @FB2@\n"
        "0 @X@ INDI\n1 SEX M\n1 FAMC @FA2@\n1 FAMS @FX@\n"
        "0 @Y@ INDI\n1 SEX F\n1 FAMC @FB2@\n1 FAMS @FY@\n"
        "0 @C1@ INDI\n1 SEX M\n1 FAMC @FX@\n1 FAMS @FC@\n"
        "0 @C2@ INDI\n1 SEX F\n1 FAMC @FY@\n1 FAMS @FC@\n"
        "0 @GC@ INDI\n1 SEX M\n1 FAMC @FC@\n"
        "0 @FZ@ FAM\n1 HUSB @Z@\n1 CHIL @A1@\n1 CHIL @B1@\n"
        "0 @FA1@ FAM\n1 HUSB @A1@\n1 CHIL @A2@\n"
        "0 @FA2@ FAM\n1 HUSB @A2@\n1 CHIL @X@\n"
        "0 @FB1@ FAM\n1 HUSB @B1@\n1 CHIL @B2@\n"
        "0 @FB2@ FAM\n1 HUSB @B2@\n1 CHIL @Y@\n"
        "0 @FX@ FAM\n1 HUSB @X@\n1 CHIL @C1@\n"
        "0 @FY@ FAM\n1 WIFE @Y@\n1 CHIL @C2@\n"
        "0 @FC@ FAM\n1 HUSB @C1@\n1 WIFE @C2@\n1 CHIL @GC@\n"
    )
    paths = PathFinder(parser).get_shortest_paths("@X@", "@Y@")
    assert [p.ids() for p in paths] == [["@X@", "@A2@", "@A1@", "@Z@", "@B1@", "@B2@", "@Y@"]]
    assert describe(paths[0], parser) == "second cousin"


def test_wifes_father_is_reached_through_the_marriage(load):
    # @B@ is @A@'s father-in-law, and @G@ is a grandchild of both: @B@'s son @E@
    # married @A@'s daughter @D@. Down to @K@ and up through his mother is no line
    # of descent, and the route through @G@ is longer than the marriage.
    parser = load(
        "0 @A@ INDI\n1 SEX M\n1 FAMS @FA1@\n1 FAMS @FAW@\n"
        "0 @W@ INDI\n1 SEX F\n1 FAMC @FB@\n1 FAMS @FAW@\n"
        "0 @B@ INDI\n1 SEX M\n1 FAMS @FB@\n"
        "0 @K@ INDI\n1 SEX M\n1 FAMC @FAW@\n"
        "0 @D@ INDI\n1 SEX F\n1 FAMC @FA1@\n1 FAMS @FDE@\n"
        "0 @E@ INDI\n1 SEX M\n1 FAMC @FB@\n1 FAMS @FDE@\n"
        "0 @G@ INDI\n1 SEX M\n1 FAMC @FDE@\n"
        "0 @FA1@ FAM\n1 HUSB @A@\n1 CHIL @D@\n"
        "0 @FAW@ FAM\n1 HUSB @A@\n1 WIFE @W@\n1 MARR\n1 CHIL @K@\n"
        "0 @FB@ FAM\n1 HUSB @B@\n1 CHIL @W@\n1 CHIL @E@\n"
        "0 @FDE@ FAM\n1 HUSB @E@\n1 WIFE @D@\n1 CHIL @G@\n"
    )
    paths = PathFinder(parser).get_shortest_paths("@A@", "@B@")
    assert _trace(paths) == [
        [("@W@", False, True, "spouse", None), ("@B@", True, True, "birth", "@FB@")]
    ]
    assert describe(paths[0], parser) == "relative by marriage"


def test_ancestor_and_collateral_routes_of_one_length_are_both_kept(load):
    # @E@ is @S@'s paternal great-grandfather and also his maternal grandmother's
    # son. The climbing route reaches @E@ first in the level; the route that turns
    # down at @MM@ arrives in the same level and must not be dropped for it.
    parser = load(
        "0 @S@ INDI\n1 SEX M\n1 FAMC @FS@\n"
        "0 @F@ INDI\n1 SEX M\n1 FAMC @FF@\n1 FAMS @FS@\n"
        "0 @M@ INDI\n1 SEX F\n1 FAMC @FM@\n1 FAMS @FS@\n"
        "0 @GF@ INDI\n1 SEX M\n1 FAMC @FE@\n1 FAMS @FF@\n"
        "0 @MM@ INDI\n1 SEX F\n1 FAMS @FM@\n1 FAMS @FMM@\n"
        "0 @E@ INDI\n1 SEX M\n1 FAMC @FMM@\n1 FAMS @FE@\n"
        "0 @FS@ FAM\n1 HUSB @F@\n1 WIFE @M@\n1 CHIL @S@\n"
        "0 @FF@ FAM\n1 HUSB @GF@\n1 CHIL @F@\n"
        "0 @FM@ FAM\n1 WIFE @MM@\n1 CHIL @M@\n"
        "0 @FE@ FAM\n1 HUSB @E@\n1 CHIL @GF@\n"
        "0 @FMM@ FAM\n1 WIFE @MM@\n1 CHIL @E@\n"
    )
    paths = PathFinder(parser).find_relationship_paths("@S@", "@E@")
    assert sorted(p.ids() for p in paths) == [
        ["@S@", "@F@", "@GF@", "@E@"],
        ["@S@", "@M@", "@MM@", "@E@"],
    ]


def test_male_line_breaks_a_tie(pathfinder):
    assert [p.ids() for p in pathfinder.get_shortest_paths("@I7@", "@I8@")] == [
        ["@I7@", "@I5@", "@I8@"]
    ]


# @A@ married @W@; his son @C@ is also a son of @W@'s father @WF@ (two birth
# families), and @T@ is @WF@'s son. Neither is a blood tie, and @A@ reaches @T@
# in three steps either through his wife or down to @C@ and up to @WF@.
IN_LAW_ROUTES = (
    "0 @A@ INDI\n1 SEX M\n1 FAMS @F1@\n1 FAMS @F2@\n"
    "0 @W@ INDI\n1 SEX F\n1 FAMC @F3@\n1 FAMS @F1@\n"
    "0 @C@ INDI\n1 SEX M\n1 FAMC @F2@\n1 FAMC @F3@\n"
    "0 @WF@ INDI\n1 SEX M\n1 FAMS @F3@\n"
    "0 @T@ INDI\n1 SEX M\n1 FAMC @F3@\n"
    "0 @F1@ FAM\n1 HUSB @A@\n1 WIFE @W@\n1 MARR\n"
    "0 @F2@ FAM\n1 HUSB @A@\n1 CHIL @C@\n"
    "0 @F3@ FAM\n1 HUSB @WF@\n1 CHIL @W@\n1 CHIL @C@\n1 CHIL @T@\n"
)


@pytest.mark.parametrize(
    ("start", "end", "route"),
    [
        ("@A@", "@T@", ["@A@", "@W@", "@WF@", "@T@"]),
        ("@T@", "@A@", ["@T@", "@WF@", "@W@", "@A@"]),
    ],
)
def test_marriage_route_beats_down_and_up_route(load, start, end, route):
    finder = PathFinder(load(IN_LAW_ROUTES))
    assert len(finder.find_relationship_paths(start, end)) == 2
    assert [p.ids() for p in finder.get_shortest_paths(start, end)] == [route]


def test_birth_route_outranks_male_route(tmp_path):
    """Equal-length routes: a birth one through the mother beats an adoptive one through a man."""
    ged = tmp_path / "rank.ged"
    ged.write_text(
        "0 HEAD\n1 CHAR UTF-8\n"
        "0 @A@ INDI\n1 SEX M\n1 FAMS @F2@\n"
        "0 @B@ INDI\n1 SEX F\n1 FAMS @F1@\n"
        "0 @T@ INDI\n1 SEX M\n1 FAMC @F1@\n1 FAMC @F2@\n2 PEDI adopted\n"
        "0 @Q@ INDI\n1 SEX M\n1 FAMC @F1@\n1 FAMC @F2@\n2 PEDI adopted\n"
        "0 @F1@ FAM\n1 WIFE @B@\n1 CHIL @T@\n1 CHIL @Q@\n"
        "0 @F2@ FAM\n1 HUSB @A@\n1 CHIL @T@\n1 CHIL @Q@\n"
        "0 TRLR\n",
        encoding="utf-8",
    )
    with GedcomParser(str(ged)) as parser:
        parser.load()
        finder = PathFinder(parser)
        assert len(finder.find_relationship_paths("@T@", "@Q@")) == 2
        paths = finder.get_shortest_paths("@T@", "@Q@")
        assert [p.ids() for p in paths] == [["@T@", "@B@", "@Q@"]]


def test_birth_link_replaces_earlier_adoption(tmp_path):
    """Step-parent adoption: the mother is in both families, the adoptive one listed first."""
    ged = tmp_path / "stepadopt.ged"
    ged.write_text(
        "0 HEAD\n1 CHAR UTF-8\n"
        "0 @A@ INDI\n1 SEX M\n1 FAMS @F2@\n"
        "0 @B@ INDI\n1 SEX F\n1 FAMS @F1@\n1 FAMS @F2@\n"
        "0 @K@ INDI\n1 SEX M\n1 FAMC @F2@\n2 PEDI adopted\n1 FAMC @F1@\n"
        "0 @F1@ FAM\n1 WIFE @B@\n1 CHIL @K@\n"
        "0 @F2@ FAM\n1 HUSB @A@\n1 WIFE @B@\n1 CHIL @K@\n"
        "0 TRLR\n",
        encoding="utf-8",
    )
    with GedcomParser(str(ged)) as parser:
        parser.load()
        neighbours = PathFinder(parser)._get_neighbors(parser.get_individual("@K@"), False)
        steps = [(s.individual_id, s.link, s.family) for _, s in neighbours]
        assert steps == [("@A@", "adopted", "@F2@"), ("@B@", "birth", "@F1@")]
        assert describe(PathFinder(parser).get_shortest_paths("@K@", "@B@")[0], parser) == "mother"


def test_no_longer_paths_after_the_shortest(tmp_path):
    """@X@ is queued at depth 2 before @Q@ reaches @T@; expanding it would add a 3-step path."""
    ged = tmp_path / "depth.ged"
    ged.write_text(
        "0 HEAD\n1 CHAR UTF-8\n"
        "0 @S@ INDI\n1 FAMC @F1@\n"
        "0 @P@ INDI\n1 SEX M\n1 FAMS @F1@\n1 FAMS @F2@\n"
        "0 @Q@ INDI\n1 SEX F\n1 FAMS @F1@\n1 FAMS @F3@\n"
        "0 @X@ INDI\n1 SEX M\n1 FAMC @F2@\n1 FAMS @F3@\n"
        "0 @T@ INDI\n1 FAMC @F3@\n"
        "0 @F1@ FAM\n1 HUSB @P@\n1 WIFE @Q@\n1 CHIL @S@\n"
        "0 @F2@ FAM\n1 HUSB @P@\n1 CHIL @X@\n"
        "0 @F3@ FAM\n1 HUSB @X@\n1 WIFE @Q@\n1 CHIL @T@\n"
        "0 TRLR\n",
        encoding="utf-8",
    )
    with GedcomParser(str(ged)) as parser:
        parser.load()
        paths = PathFinder(parser).find_relationship_paths("@S@", "@T@")
    assert {p.length() for p in paths} == {2}
