"""Tests for DOT file generation."""

from pathlib import Path

import pytest

from gedgraph.dotgen import DotGenerator, _escape_dot_text, _escape_id, strip_control
from gedgraph.parser import GedcomParser
from gedgraph.pathfinder import PathFinder, RelationshipPath

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def special_parser():
    """Load special character GEDCOM file."""
    with GedcomParser(str(FIXTURES_DIR / "sample_special.ged")) as p:
        p.load()
        yield p


@pytest.fixture
def dotgen(parser):
    """Create DotGenerator instance."""
    return DotGenerator(parser)


@pytest.fixture
def special_dotgen(special_parser):
    """Create DotGenerator for special character fixture."""
    return DotGenerator(special_parser)


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
    dot = dotgen.generate_relationship(paths, "summary")
    assert "digraph Relationship" in dot
    assert "John Smith" in dot
    assert "David Smith" in dot


def test_generate_relationship_no_paths(dotgen):
    """Test generating relationship with no paths."""
    with pytest.raises(ValueError):
        dotgen.generate_relationship([], "summary")


def test_generate_relationship_unknown_individual(dotgen):
    path = RelationshipPath(steps=[], start_id="@NOPE@", end_id="@I1@")
    with pytest.raises(ValueError, match="Invalid start or end"):
        dotgen.generate_relationship([path], "summary")


@pytest.mark.parametrize("chart", ["hourglass", "bowtie"])
def test_split_charts_reject_unknown_individual(dotgen, chart):
    with pytest.raises(ValueError, match="not found"):
        getattr(dotgen, f"generate_{chart}")("@NOPE@")


@pytest.mark.parametrize("chart", ["hourglass", "bowtie"])
@pytest.mark.parametrize("variant", ["pedigree", "sideways"])
def test_split_charts_reject_other_variants(dotgen, chart, variant):
    with pytest.raises(ValueError, match=f"Unknown variant: {variant}"):
        getattr(dotgen, f"generate_{chart}")("@I1@", 2, variant)


def test_dot_includes_dates(dotgen):
    """Test that DOT output includes birth/death dates."""
    dot = dotgen.generate_pedigree("@I1@", generations=1)
    assert "1900" in dot
    assert "1980" in dot


def test_relationship_comment_is_the_summary_line(dotgen, pathfinder):
    paths = pathfinder.get_shortest_paths("@I1@", "@I3@")
    dot = dotgen.generate_relationship(paths, "Robert is John's son (1 step) (caveat)")
    comments = [line.strip() for line in dot.splitlines() if line.strip().startswith("//")]
    assert comments == ["// Robert is John's son (1 step) (caveat)"]


def test_relationship_chart_couple_with_children_is_one_edge(dotgen, pathfinder):
    dot = dotgen.generate_relationship(pathfinder.get_shortest_paths("@I6@", "@I5@"), "")
    lines = [line.strip() for line in dot.splitlines()]
    assert "I6 -> I5 [dir=none, style=dashed, constraint=false];" in lines
    assert [line.split()[0] for line in lines if "[label=" in line] == ["I6", "I5"]


def test_relationship_comment_strips_control_characters(dotgen, pathfinder):
    paths = pathfinder.get_shortest_paths("@I1@", "@I3@")
    dot = dotgen.generate_relationship(paths, "Ev\x1bil\x07\x9b\nX")
    assert "  // EvilX\n" in dot


def test_relationship_chart_marriage_and_adoption_edges(links):
    paths = PathFinder(links).get_shortest_paths("@W7@", "@AP@")
    dot = DotGenerator(links).generate_relationship(paths, "")
    lines = [line.strip() for line in dot.splitlines()]
    assert "W7 -> H7 [dir=none, style=solid, constraint=false];" in lines
    assert "{rank=same; W7; H7;}" in lines
    assert "AP -> C1 [style=dotted];" in lines
    assert "P1 -> C1;" in lines
    defined = [line.split()[0] for line in lines if "[label=" in line]
    # AM is drawn beside AP because the step went through the adoptive family.
    assert defined == ["W7", "H7", "P1", "M1", "C1", "AP", "AM"]


def test_relationship_chart_unmarried_spouse_edge_is_dashed(links):
    paths = PathFinder(links).get_shortest_paths("@H8@", "@W8@")
    dot = DotGenerator(links).generate_relationship(paths, "")
    assert "  H8 -> W8 [dir=none, style=dashed, constraint=false];" in dot


def test_relationship_chart_keeps_punctuation_twins_apart():
    with GedcomParser(str(FIXTURES_DIR / "layout.ged")) as layout:
        layout.load()
        paths = PathFinder(layout).get_shortest_paths("@K-1@", "@K.1@")
        dot = DotGenerator(layout).generate_relationship(paths, "")
    defined = [line.split()[0] for line in dot.splitlines() if "[label=" in line]
    # Father, his wife drawn as the other parent, and both children.
    assert len(defined) == len(set(defined)) == 4
    assert {"K_1", "K_1_2"} <= set(defined)


@pytest.mark.parametrize(
    ("xref", "expected"),
    [
        ("@I1@", "I1"),
        ("@I1-2@", "I1_2"),
        ("@I.1/2+3@", "I_1_2_3"),
        ("@123@", "_123"),
        ("@Node@", "_Node"),
        ("@EDGE@", "_EDGE"),
        ("@subgraph@", "_subgraph"),
        ("@Nodes@", "Nodes"),
        (None, "_"),
    ],
)
def test_escape_id(xref, expected):
    assert _escape_id(xref) == expected


def test_format_individual_label(dotgen, parser):
    """Test individual label formatting."""
    individual = parser.get_individual("@I1@")
    label = dotgen._format_label(individual)
    assert "John Smith" in label
    assert "1900" in label
    assert "1980" in label


# --- Hourglass tests ---


def test_hourglass_ancestor_split(dotgen):
    """Ancestor-split hourglass puts father's line above, mother's below."""
    dot = dotgen.generate_hourglass("@I5@", 2, "ancestor-split")

    assert "digraph Hourglass" in dot
    assert "rankdir=TB" in dot

    assert "I5" in dot
    assert "fillcolor=lightcoral" in dot

    # Father's side
    assert "Robert Smith" in dot  # I3
    assert "John Smith" in dot  # I1
    assert "Mary Jones" in dot  # I2
    assert "I3 -> I5;" in dot

    # Mother's side
    assert "Sarah Brown" in dot  # I4
    assert "I5 -> I4 [dir=back]" in dot
    assert "I4 -> I5" not in dot


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
    assert "I5 -> I4 [dir=back]" in dot
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
    """A name ending in a backslash must not swallow the DOT line break after it."""
    ind = special_parser.get_individual("@I21@")
    assert special_parser.get_name(ind) == "Test Name\\"
    assert special_dotgen._format_label(ind) == "Test Name\\\\\\n(1925 - )"


def test_pedigree_comment_no_control_chars(special_dotgen):
    """DOT comment lines must not contain raw control characters."""
    dot = special_dotgen.generate_pedigree("@I20@", generations=1)
    for line in dot.split("\n"):
        if "//" in line:
            comment_part = line[line.index("//") :]
            assert "\n" not in comment_part
            assert "\r" not in comment_part
            # No control chars in the range 0x00-0x1f or 0x7f
            for ch in comment_part:
                assert ord(ch) >= 0x20
                assert ord(ch) != 0x7F


def test_strip_control_removes_c0_del_and_c1():
    assert strip_control("hello\x00world") == "helloworld"
    assert strip_control("line\nbreak") == "linebreak"
    assert strip_control("tab\there") == "tabhere"
    assert strip_control("del\x7fchar") == "delchar"
    assert strip_control("csi\x9b31m") == "csi31m"
    assert strip_control("clean text") == "clean text"
    # Printable non-ASCII passes through
    assert strip_control("caf\u00e9") == "caf\u00e9"


# --- _escape_dot_text unit tests ---


def test_escape_dot_text_backslash():
    """Backslash is doubled for DOT string escaping."""
    assert _escape_dot_text("a\\b") == "a\\\\b"


def test_escape_dot_text_quote():
    """Double-quote is escaped with a preceding backslash."""
    assert _escape_dot_text('a"b') == 'a\\"b'


def test_escape_dot_text_control_chars():
    """Control characters (newline, carriage return, null) are stripped."""
    assert _escape_dot_text("a\nb\rc\x00d") == "abcd"


def test_escape_dot_text_clean_passthrough():
    """Clean text passes through unchanged."""
    assert _escape_dot_text("John Smith") == "John Smith"


def test_escape_dot_text_ampersand():
    """Graphviz decodes entities in plain labels; & must reach it as &amp;."""
    assert _escape_dot_text("&#27;x AT&T") == "&amp;#27;x AT&amp;T"


@pytest.mark.parametrize(
    "char", ["\u202e", "\u2066", "\u2069", "\u200b", "\u200f", "\u2028", "\u2029", "\ufeff"]
)
def test_strip_control_drops_invisible_reordering_characters(char):
    assert strip_control(f"Ev{char}il") == "Evil"


def test_strip_control_keeps_joiners():
    # Persian and Indic names, and emoji, need ZWNJ and ZWJ.
    assert strip_control("\u0645\u06cc\u200c\u0631\u0648\u062f \u0915\u094d\u200d\u0937") == (
        "\u0645\u06cc\u200c\u0631\u0648\u062f \u0915\u094d\u200d\u0937"
    )


def test_escape_dot_text_angle_brackets_passthrough():
    """Angle brackets are not special in shape=box labels and pass through."""
    assert _escape_dot_text("<b>Title</b>") == "<b>Title</b>"


# --- _format_label integration test ---


def test_format_label_preserves_newline(parser):
    """DOT newline \\n in label must not be double-escaped."""
    dotgen = DotGenerator(parser)
    # I1 has birth + death dates, so the label will contain \\n
    ind = parser.get_individual("@I1@")
    label = dotgen._format_label(ind)

    # The Python string should contain the two-char sequence backslash + n
    assert "\\n" in label
    # Must NOT contain double-escaped \\\\n
    assert "\\\\n" not in label
    # Must not contain an actual newline character
    assert chr(10) not in label


@pytest.mark.parametrize(("xref", "year"), [("@D4@", "c. 1950"), ("@D5@", "bef. 1900")])
def test_qualified_year_in_label(xref, year):
    with GedcomParser(str(FIXTURES_DIR / "dates.ged")) as p:
        p.load()
        dot = DotGenerator(p).generate_pedigree(xref, generations=1)
    assert f"\\n({year} - )" in dot


# --- _build_chart ---


def _chart(parser, xref, generations, variant):
    gen = DotGenerator(parser)
    return gen._build_chart(parser.get_individual(xref), generations, variant)


TWINS = """\
0 @I_1@ INDI
1 NAME Focal /Person/
1 FAMC @F1@
0 @I-1@ INDI
1 NAME Dad /Person/
1 FAMC @F2@
1 FAMS @F1@
0 @I.1@ INDI
1 NAME Mum /Other/
1 FAMS @F1@
0 @I_1_2@ INDI
1 NAME Granddad /Person/
1 FAMS @F2@
0 @F1@ FAM
1 HUSB @I-1@
1 WIFE @I.1@
1 CHIL @I_1@
0 @F2@ FAM
1 HUSB @I_1_2@
1 CHIL @I-1@
"""


def test_build_chart_suffixes_colliding_ids(load):
    """Xrefs that escape to the same id get _2, _3, ... in BFS order."""
    nodes, edges = _chart(load(TWINS), "@I_1@", 2, "pedigree")
    ids = {n.individual.xref_id: n.node_id for n in nodes}
    assert ids == {
        "@I_1@": "I_1",
        "@I-1@": "I_1_2",
        "@I.1@": "I_1_3",
        # Its natural id was handed out as a suffix, so the loop moves past it.
        "@I_1_2@": "I_1_2_2",
    }
    assert len(set(ids.values())) == len(ids)
    assert {(e.parent, e.child) for e in edges} == {
        ("I_1_2", "I_1"),
        ("I_1_3", "I_1"),
        ("I_1_2_2", "I_1_2"),
    }


def test_build_chart_rendered_ids_are_distinct(load):
    dot = DotGenerator(load(TWINS)).generate_pedigree("@I_1@", 2)
    assert "I_1_2 -> I_1;" in dot
    assert "I_1_3 -> I_1;" in dot
    assert "I_1_2_2 -> I_1_2;" in dot


COUSINS = """\
0 @ME@ INDI
1 NAME Me /X/
1 FAMC @F1@
0 @DAD@ INDI
1 NAME Dad /X/
1 FAMC @F2@
1 FAMS @F1@
0 @MUM@ INDI
1 NAME Mum /Y/
1 FAMC @F3@
1 FAMS @F1@
0 @UNC@ INDI
1 NAME Uncle /X/
1 FAMC @F4@
1 FAMS @F2@
0 @AUN@ INDI
1 NAME Aunt /X/
1 FAMC @F4@
1 FAMS @F3@
0 @GP@ INDI
1 NAME Grandpa /X/
1 FAMS @F4@
0 @F1@ FAM
1 HUSB @DAD@
1 WIFE @MUM@
1 CHIL @ME@
0 @F2@ FAM
1 HUSB @UNC@
1 CHIL @DAD@
0 @F3@ FAM
1 WIFE @AUN@
1 CHIL @MUM@
0 @F4@ FAM
1 HUSB @GP@
1 CHIL @UNC@
1 CHIL @AUN@
"""


def test_build_chart_split_shares_only_focal(load):
    """A common ancestor gets one node per side; the focal person gets one in total."""
    nodes, edges = _chart(load(COUSINS), "@ME@", 3, "ancestor-split")
    by_id = {n.node_id: n for n in nodes}

    assert [n.node_id for n in nodes if n.individual.xref_id == "@ME@"] == ["ME"]
    assert nodes[0].focal
    assert (nodes[0].side, nodes[0].generation) == ("", 0)
    assert not any(n.focal for n in nodes[1:])

    assert (by_id["GP"].side, by_id["GP"].generation) == ("p", 3)
    assert (by_id["GP_2"].side, by_id["GP_2"].generation) == ("m", 3)
    assert (by_id["DAD"].side, by_id["MUM"].side) == ("p", "m")

    flips = {(e.parent, e.child): e.flip for e in edges}
    assert flips == {
        ("DAD", "ME"): False,
        ("UNC", "DAD"): False,
        ("GP", "UNC"): False,
        ("MUM", "ME"): True,
        ("AUN", "MUM"): True,
        ("GP_2", "AUN"): True,
    }


def test_build_chart_pedigree_collapse_is_one_node(load):
    """Reached twice on one side: one node, both edges."""
    nodes, edges = _chart(load(COUSINS), "@ME@", 3, "pedigree")
    assert [n.node_id for n in nodes].count("GP") == 1
    assert "GP_2" not in {n.node_id for n in nodes}
    pairs = [(e.parent, e.child) for e in edges]
    assert ("GP", "UNC") in pairs
    assert ("GP", "AUN") in pairs
    assert not any(e.flip for e in edges)


def test_build_chart_dedupes_edges(load):
    """A child listed under two of its parent's families yields one edge."""
    records = """\
0 @P@ INDI
1 NAME Parent /X/
1 FAMS @F1@
1 FAMS @F2@
0 @C@ INDI
1 NAME Child /X/
1 FAMC @F1@
0 @F1@ FAM
1 HUSB @P@
1 CHIL @C@
0 @F2@ FAM
1 HUSB @P@
1 CHIL @C@
"""
    nodes, edges = _chart(load(records), "@P@", 1, "descendants")
    assert [(n.node_id, n.generation) for n in nodes] == [("P", 0), ("C", -1)]
    assert [(e.parent, e.child, e.flip) for e in edges] == [("P", "C", False)]


@pytest.fixture
def links_dotgen():
    with GedcomParser(str(FIXTURES_DIR / "links.ged")) as p:
        p.load()
        yield DotGenerator(p)


def _edge_lines(dot):
    return {line.strip() for line in dot.splitlines() if "->" in line}


def test_hourglass_descendants_dot_adopted_children(links_dotgen):
    dot = links_dotgen.generate_hourglass("@M1@", 2, "descendants")
    edges = _edge_lines(dot)
    assert "M1 -> C5;" in edges  # birth child of F1, step child of F4: birth wins
    assert "M1 -> H7;" in edges
    dot = links_dotgen.generate_hourglass("@AP@", 2, "descendants")
    assert {"AP -> C1 [style=dotted];", "AP -> C2 [style=dotted];"} <= _edge_lines(dot)


def test_pedigree_of_adoptee_without_birth_family_is_dotted(links_dotgen):
    edges = _edge_lines(links_dotgen.generate_pedigree("@C2@", 2))
    assert edges == {"AP -> C2 [style=dotted];", "AM -> C2 [style=dotted];"}
    edges = _edge_lines(links_dotgen.generate_pedigree("@C1@", 2))
    assert edges == {"P1 -> C1;", "M1 -> C1;"}


def test_ancestor_split_with_adopted_focal(links_dotgen):
    edges = _edge_lines(links_dotgen.generate_bowtie("@C4@", 2))
    assert edges == {"FP -> C4 [style=dotted];", "C4 -> FM [dir=back, style=dotted];"}


def test_build_chart_birth_link_upgrades_earlier_step_edge(load):
    """C is first reached as an implied step child of F1, then as P's birth child."""
    records = """\
0 @P@ INDI
1 NAME Parent /X/
1 FAMS @F1@
1 FAMS @F2@
0 @C@ INDI
1 NAME Child /X/
1 FAMC @F2@
0 @F1@ FAM
1 HUSB @P@
1 CHIL @C@
0 @F2@ FAM
1 HUSB @P@
1 CHIL @C@
"""
    parser = load(records)
    links = parser.child_links(parser.get_individual("@P@"))
    assert [(fam, link) for _, fam, link in links] == [("@F1@", "step"), ("@F2@", "birth")]
    _, edges = _chart(parser, "@P@", 1, "descendants")
    assert [(e.parent, e.child, e.link) for e in edges] == [("P", "C", "birth")]
    assert "  P -> C;" in DotGenerator(parser).generate_hourglass("@P@", 1, "descendants")


def test_build_chart_step_edge_stays_step_without_birth_link(load):
    records = """\
0 @P@ INDI
1 NAME Parent /X/
1 FAMS @F1@
1 FAMS @F3@
0 @F3@ FAM
1 HUSB @P@
1 CHIL @C@
0 @Q@ INDI
1 NAME Other /Y/
1 FAMS @F2@
0 @C@ INDI
1 NAME Child /X/
1 FAMC @F2@
0 @F1@ FAM
1 HUSB @P@
1 CHIL @C@
0 @F2@ FAM
1 HUSB @Q@
1 CHIL @C@
"""
    _, edges = _chart(load(records), "@P@", 1, "descendants")
    assert [(e.parent, e.child, e.link) for e in edges] == [("P", "C", "step")]


def test_build_chart_unknown_variant(dotgen, parser):
    with pytest.raises(ValueError, match="Unknown variant: sideways"):
        dotgen._build_chart(parser.get_individual("@I5@"), 2, "sideways")


def test_collapse_edge_to_shallower_parent_is_not_ranked():
    """@P@ is reached at generation 2 through @M2@ but also fathered @A@ at 3."""
    with GedcomParser(str(FIXTURES_DIR / "collapse.ged")) as p:
        p.load()
        dot = DotGenerator(p).generate_pedigree("@Z@", 5)
    assert "  P -> A [constraint=false];" in dot
    assert "  P -> M2;" in dot
    assert "  A -> B;" in dot


def test_relationship_chart_unmarried_other_parent_is_dashed(load):
    parser = load(
        "0 @D@ INDI\n1 SEX M\n1 FAMS @F1@\n"
        "0 @M@ INDI\n1 SEX F\n1 FAMS @F1@\n"
        "0 @C@ INDI\n1 FAMC @F1@\n"
        "0 @F1@ FAM\n1 HUSB @D@\n1 WIFE @M@\n1 CHIL @C@\n",
    )
    dot = DotGenerator(parser).generate_relationship(
        PathFinder(parser).get_shortest_paths("@C@", "@D@"), ""
    )
    assert "  D -> M [dir=none, style=dashed, constraint=false];" in dot
