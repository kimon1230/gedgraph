"""Layout tests for pedigree, hourglass and bowtie charts.

The rendered tests run the DOT through GraphViz and check where nodes land.
"""

import os
import re
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pytest

from gedgraph.dotgen import COLOR_FOCAL, DotGenerator, _Edge, _Node
from gedgraph.parser import GedcomParser

FIXTURES_DIR = Path(__file__).parent / "fixtures"

NODE_RE = re.compile(r"^\s+(\w+) \[label=\"(?:[^\"\\]|\\.)*\", fillcolor=(\w+)\];$")
EDGE_RE = re.compile(r"^\s+(\w+) -> (\w+)(?: \[(.*)\])?;$")
TOLERANCE = 0.01


@dataclass
class Chart:
    nodes: list[_Node]
    edges: list[_Edge]
    dot: str
    rankdir: str


@pytest.fixture(scope="module")
def parsers():
    with (
        GedcomParser(str(FIXTURES_DIR / "sample.ged")) as sample,
        GedcomParser(str(FIXTURES_DIR / "layout.ged")) as layout,
        GedcomParser(str(FIXTURES_DIR / "collapse.ged")) as collapse,
    ):
        for parser in (sample, layout, collapse):
            parser.load()
        yield {"sample": sample, "layout": layout, "collapse": collapse}


def _require_dot() -> str:
    path = shutil.which("dot")
    if path is None:
        if os.environ.get("GEDGRAPH_REQUIRE_DOT") == "1":
            pytest.fail("GEDGRAPH_REQUIRE_DOT=1 but GraphViz dot is not on PATH")
        pytest.skip("GraphViz dot not installed")
    return path


@pytest.fixture(scope="module")
def dot_bin():
    return _require_dot()


def _chart(parser: GedcomParser, chart: str, focal: str, variant: str, generations: int) -> Chart:
    """Build once and render that same build, so the DOT matches nodes and edges."""
    gen = DotGenerator(parser)
    individual = parser.get_individual(focal)
    nodes, edges = gen._build_chart(individual, generations, variant)
    rankdir = "LR" if chart == "bowtie" else "TB"
    suffix = f" - {generations} generations" if chart == "pedigree" else ""
    dot = gen._render_chart(
        chart.title(), individual, nodes, edges, rankdir=rankdir, comment_suffix=suffix
    )
    return Chart(nodes, edges, dot, rankdir)


def _ranked(chart: Chart, edge: _Edge) -> bool:
    """False for a pedigree-collapse shortcut, which is drawn but not ranked."""
    generation = {n.node_id: n.generation for n in chart.nodes}
    return generation[edge.parent] - generation[edge.child] == 1


def _depths(dot_bin: str, chart: Chart) -> tuple[dict[str, float], dict[str, float]]:
    """Map node id to (depth, across) coordinates.

    Depth grows from the top (TB) or left (LR) of the drawing, so a parent drawn
    in the usual place has a smaller depth than its child. -Tplain y grows upward.
    """
    out = subprocess.run(
        [dot_bin, "-Tplain"],
        input=chart.dot,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout
    depth: dict[str, float] = {}
    across: dict[str, float] = {}
    for line in out.splitlines():
        parts = line.split()
        if parts and parts[0] == "node":
            x, y = float(parts[2]), float(parts[3])
            if chart.rankdir == "TB":
                depth[parts[1]], across[parts[1]] = -y, x
            else:
                depth[parts[1]], across[parts[1]] = x, y
    return depth, across


def _rows(chart: Chart) -> dict[tuple[str, int], list[str]]:
    rows = defaultdict(list)
    for node in chart.nodes:
        rows[(node.side, node.generation)].append(node.node_id)
    return rows


# Every chart shape the layout tests exercise, including both sides of the
# uneven-depth collapse around @U0@ / @UX@.
CHARTS = [
    ("sample", "pedigree", "@I7@", "pedigree", 3),
    ("sample", "hourglass", "@I7@", "ancestor-split", 3),
    ("sample", "bowtie", "@I7@", "ancestor-split", 3),
    ("sample", "hourglass", "@I5@", "descendants", 3),
    ("sample", "bowtie", "@I5@", "descendants", 3),
    ("layout", "hourglass", "@G0@", "ancestor-split", 2),
    ("layout", "bowtie", "@G0@", "ancestor-split", 2),
    ("layout", "hourglass", "@G0@", "descendants", 2),
    ("layout", "bowtie", "@G0@", "descendants", 2),
    ("layout", "hourglass", "@C0@", "ancestor-split", 3),
    ("layout", "bowtie", "@C0@", "ancestor-split", 3),
    ("layout", "pedigree", "@U0@", "pedigree", 4),
    ("layout", "hourglass", "@U0@", "ancestor-split", 4),
    ("layout", "bowtie", "@U0@", "ancestor-split", 4),
    ("layout", "hourglass", "@U0@", "descendants", 4),
    ("layout", "hourglass", "@UX@", "descendants", 4),
    ("layout", "bowtie", "@UX@", "descendants", 4),
    ("collapse", "pedigree", "@Z@", "pedigree", 5),
]


# --- Structural ---


@pytest.mark.parametrize(("fixture", "chart", "focal", "variant", "gens"), CHARTS)
def test_edges_render_in_flip_direction(parsers, fixture, chart, focal, variant, gens):
    c = _chart(parsers[fixture], chart, focal, variant, gens)
    rendered = [EDGE_RE.match(line) for line in c.dot.splitlines() if "->" in line]
    assert all(rendered)
    lines = {(m.group(1), m.group(2)): m.group(3) or "" for m in rendered if m}

    sides = {n.node_id: n.side for n in c.nodes}
    for edge in c.edges:
        assert edge.flip == (sides[edge.parent] == "m")
        tail, head = (edge.child, edge.parent) if edge.flip else (edge.parent, edge.child)
        attrs = lines[(tail, head)]
        assert (head, tail) not in lines
        assert ("dir=back" in attrs) == edge.flip
        assert ("constraint=false" in attrs) == (not _ranked(c, edge))


@pytest.mark.parametrize(("fixture", "chart", "focal", "variant", "gens"), CHARTS)
def test_no_duplicate_nodes_or_edges(parsers, fixture, chart, focal, variant, gens):
    c = _chart(parsers[fixture], chart, focal, variant, gens)
    defined = [m.group(1) for line in c.dot.splitlines() if (m := NODE_RE.match(line))]
    edges = [line.strip() for line in c.dot.splitlines() if "->" in line]

    assert len(defined) == len(c.nodes)
    assert len(set(defined)) == len(defined)
    assert len(set(edges)) == len(edges)
    assert len(edges) == len(c.edges)


@pytest.mark.parametrize(("fixture", "chart", "focal", "variant", "gens"), CHARTS)
def test_focal_defined_once_in_focal_color(parsers, fixture, chart, focal, variant, gens):
    c = _chart(parsers[fixture], chart, focal, variant, gens)
    focal_ids = [n.node_id for n in c.nodes if n.individual.xref_id == focal]
    assert len(focal_ids) == 1

    defs = [m for line in c.dot.splitlines() if (m := NODE_RE.match(line))]
    colors = {m.group(1): m.group(2) for m in defs}
    assert [m.group(1) for m in defs].count(focal_ids[0]) == 1
    assert colors[focal_ids[0]] == COLOR_FOCAL
    assert list(colors.values()).count(COLOR_FOCAL) == 1


@pytest.mark.parametrize(
    ("chart", "variant"),
    [
        ("pedigree", "pedigree"),
        ("hourglass", "ancestor-split"),
        ("hourglass", "descendants"),
        ("bowtie", "ancestor-split"),
        ("bowtie", "descendants"),
    ],
)
def test_chart_helper_matches_public_output(parsers, chart, variant):
    """_chart bypasses generate_*; this keeps the two from drifting apart."""
    public = getattr(DotGenerator(parsers["layout"]), f"generate_{chart}")
    args = ("@G0@", 3) if chart == "pedigree" else ("@G0@", 3, variant)
    assert _chart(parsers["layout"], chart, "@G0@", variant, 3).dot == public(*args)


def test_punctuation_twins_get_distinct_ids(parsers):
    c = _chart(parsers["layout"], "hourglass", "@G0@", "descendants", 2)
    ids = {n.individual.xref_id: n.node_id for n in c.nodes}
    assert ids["@K-1@"] != ids["@K.1@"]
    assert f"  {ids['@G0@']} -> {ids['@K-1@']};" in c.dot
    assert f"  {ids['@G0@']} -> {ids['@K.1@']};" in c.dot


def test_cousin_marriage_ids_do_not_collide(parsers):
    """@I1@ on the maternal side would naturally become I1_2, which @I1_2@ holds."""
    c = _chart(parsers["layout"], "hourglass", "@C0@", "ancestor-split", 3)
    by_key = {(n.side, n.individual.xref_id): n for n in c.nodes}

    assert ("p", "@I1@") in by_key
    assert ("m", "@I1@") in by_key
    assert ("p", "@I1_2@") in by_key
    assert by_key[("p", "@I1@")].generation == 3
    assert by_key[("m", "@I1@")].generation == 3
    assert by_key[("p", "@I1_2@")].generation == 3

    ids = {by_key[k].node_id for k in [("p", "@I1@"), ("m", "@I1@"), ("p", "@I1_2@")]}
    assert len(ids) == 3


@pytest.mark.parametrize(
    ("fixture", "focal", "variant", "gens", "present", "absent"),
    [
        ("sample", "@I7@", "pedigree", 1, ["@I5@", "@I6@"], ["@I3@"]),
        ("sample", "@I5@", "ancestor-split", 1, ["@I3@", "@I4@"], ["@I1@"]),
        ("sample", "@I5@", "descendants", 1, ["@I3@", "@I4@", "@I7@", "@I8@"], ["@I1@"]),
        ("sample", "@I1@", "descendants", 2, ["@I3@", "@I5@"], ["@I7@"]),
        (
            "layout",
            "@G0@",
            "ancestor-split",
            1,
            ["@GF@", "@GM@"],
            ["@GPF@", "@GPM@", "@GMF@", "@GMM@"],
        ),
    ],
)
def test_generation_cutoff(parsers, fixture, focal, variant, gens, present, absent):
    parser = parsers[fixture]
    nodes, _ = DotGenerator(parser)._build_chart(parser.get_individual(focal), gens, variant)
    xrefs = {n.individual.xref_id for n in nodes}

    assert set(present) <= xrefs
    assert not set(absent) & xrefs
    assert max(abs(n.generation) for n in nodes) == gens


# --- Rendered ---


def test_require_dot_skips_when_missing(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    for value in [None, "", "0", "yes"]:
        if value is None:
            monkeypatch.delenv("GEDGRAPH_REQUIRE_DOT", raising=False)
        else:
            monkeypatch.setenv("GEDGRAPH_REQUIRE_DOT", value)
        with pytest.raises(pytest.skip.Exception):
            _require_dot()


def test_require_dot_fails_when_required(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setenv("GEDGRAPH_REQUIRE_DOT", "1")
    with pytest.raises(pytest.fail.Exception, match="GEDGRAPH_REQUIRE_DOT"):
        _require_dot()


@pytest.mark.parametrize("chart", ["hourglass", "bowtie"])
@pytest.mark.parametrize(("fixture", "focal"), [("sample", "@I7@"), ("layout", "@G0@")])
def test_split_puts_father_and_mother_on_opposite_sides(parsers, dot_bin, chart, fixture, focal):
    """Hourglass: paternal above focal above maternal. Bowtie: left to right."""
    c = _chart(parsers[fixture], chart, focal, "ancestor-split", 2)
    depth, _ = _depths(dot_bin, c)
    focal_depth = depth[c.nodes[0].node_id]
    paternal = [depth[n.node_id] for n in c.nodes if n.side == "p"]
    maternal = [depth[n.node_id] for n in c.nodes if n.side == "m"]

    assert paternal
    assert maternal
    assert max(paternal) < focal_depth
    assert focal_depth < min(maternal)


@pytest.mark.parametrize("chart", ["hourglass", "bowtie"])
@pytest.mark.parametrize(("fixture", "focal"), [("sample", "@I5@"), ("layout", "@G0@")])
def test_descendants_put_ancestors_before_descendants(parsers, dot_bin, chart, fixture, focal):
    c = _chart(parsers[fixture], chart, focal, "descendants", 2)
    depth, _ = _depths(dot_bin, c)
    focal_depth = depth[c.nodes[0].node_id]
    ancestors = [depth[n.node_id] for n in c.nodes if n.generation > 0]
    descendants = [depth[n.node_id] for n in c.nodes if n.generation < 0]

    assert ancestors
    assert descendants
    assert max(ancestors) < focal_depth
    assert focal_depth < min(descendants)


@pytest.mark.parametrize(("fixture", "chart", "focal", "variant", "gens"), CHARTS)
def test_parents_drawn_on_their_side_of_child(
    parsers, dot_bin, fixture, chart, focal, variant, gens
):
    """Plain parents sit above/left of the child; flipped parents below/right.

    Collapse shortcuts are exempt: they run sideways so that rows stay intact.
    """
    c = _chart(parsers[fixture], chart, focal, variant, gens)
    depth, _ = _depths(dot_bin, c)
    for edge in c.edges:
        if not _ranked(c, edge):
            continue
        if edge.flip:
            assert depth[edge.parent] > depth[edge.child], (edge.parent, edge.child)
        else:
            assert depth[edge.parent] < depth[edge.child], (edge.parent, edge.child)


@pytest.mark.parametrize(
    ("chart", "focal", "variant"),
    [
        ("pedigree", "@I7@", "pedigree"),
        ("hourglass", "@I7@", "ancestor-split"),
        ("bowtie", "@I7@", "ancestor-split"),
        ("hourglass", "@I5@", "descendants"),
        ("bowtie", "@I5@", "descendants"),
    ],
)
def test_same_generation_shares_a_row(parsers, dot_bin, chart, focal, variant):
    c = _chart(parsers["sample"], chart, focal, variant, 3)
    depth, _ = _depths(dot_bin, c)
    rows = _rows(c)

    assert any(len(ids) >= 2 for ids in rows.values())
    for key, ids in rows.items():
        spread = max(depth[i] for i in ids) - min(depth[i] for i in ids)
        assert spread < TOLERANCE, key


@pytest.mark.parametrize(
    ("fixture", "chart", "focal", "variant", "gens"),
    [
        # Uncle-niece marriage: Grandpa is two and three generations up.
        ("collapse", "pedigree", "@X@", "pedigree", 3),
        # The same collapse wholly inside the father's side of a split chart.
        ("collapse", "hourglass", "@Y@", "ancestor-split", 4),
        ("collapse", "bowtie", "@Y@", "ancestor-split", 4),
        # A woman married her sibling's grandson: her father sits one generation
        # *below* the son he also fathered, so that edge must not rank either.
        ("collapse", "pedigree", "@Z@", "pedigree", 5),
        ("layout", "pedigree", "@U0@", "pedigree", 4),
        ("layout", "hourglass", "@UX@", "descendants", 4),
    ],
)
def test_collapse_keeps_generation_rows(parsers, dot_bin, fixture, chart, focal, variant, gens):
    c = _chart(parsers[fixture], chart, focal, variant, gens)
    depth, _ = _depths(dot_bin, c)
    rows = _rows(c)

    assert not all(_ranked(c, edge) for edge in c.edges)
    for key, ids in rows.items():
        spread = max(depth[i] for i in ids) - min(depth[i] for i in ids)
        assert spread < TOLERANCE, key
    # No extra rows: every drawn row is one (side, generation).
    assert len({round(d, 2) for d in depth.values()}) == len(rows)


@pytest.mark.parametrize("chart", ["hourglass", "bowtie"])
def test_grandparents_share_a_row_per_side(parsers, dot_bin, chart):
    c = _chart(parsers["layout"], chart, "@G0@", "ancestor-split", 2)
    depth, across = _depths(dot_bin, c)
    rows = _rows(c)

    for key in [("p", 2), ("m", 2)]:
        first, second = rows[key]
        assert abs(depth[first] - depth[second]) < TOLERANCE
        assert abs(across[first] - across[second]) > TOLERANCE


def test_entities_and_bidi_in_names_render_as_text(dot_bin, tmp_path):
    ged = tmp_path / "evil.ged"
    ged.write_text(
        "0 HEAD\n1 CHAR UTF-8\n"
        "0 @I1@ INDI\n1 NAME Bob &#27;]0;OWNED&#7;&#27;[2J AT&T \u202eX /Smith/\n"
        "0 TRLR\n",
        encoding="utf-8",
    )
    with GedcomParser(str(ged)) as parser:
        parser.load()
        dot = DotGenerator(parser).generate_pedigree("@I1@", 1)
    out = subprocess.run(
        [dot_bin, "-Tplain"], input=dot, check=True, capture_output=True, text=True, timeout=60
    ).stdout
    for char in ("\x1b", "\x07", "\u202e"):
        assert char not in out
    assert "Bob &#27;]0;OWNED&#7;&#27;[2J AT&T X Smith" in out
