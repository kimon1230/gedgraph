from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ged4py.model import Individual

    from .parser import GedcomParser
    from .pathfinder import RelationshipPath

_NONALNUM_RE = re.compile(r"[^a-zA-Z0-9_]")
# C0, DEL and C1: ESC or CSI in a name could otherwise drive a terminal, and a
# newline would end a DOT comment early. Bidi controls, zero-width space, line
# and paragraph separators and BOM could reorder or hide the rest of a summary
# line. ZWNJ and ZWJ (U+200C/D) stay: Persian, Indic scripts and emoji need them.
_CONTROL_RE = re.compile(
    r"[\x00-\x1f\x7f-\x9f\u200b\u200e\u200f\u2028\u2029\u202a-\u202e\u2066-\u2069\ufeff]"
)
# Reserved in DOT (case-insensitively), so never valid as a bare node id.
_DOT_KEYWORDS = {"node", "edge", "graph", "digraph", "subgraph", "strict"}

COLOR_FOCAL = "lightcoral"
COLOR_DEFAULT = "lightgreen"
COLOR_SPOUSE = "lightyellow"
COLOR_END = "lightblue"


@dataclass
class _Node:
    node_id: str
    individual: Individual
    focal: bool
    side: str  # "p", "m", or "" (single tree / focal)
    generation: int  # focal 0, ancestors +N, descendants -N; depth of first BFS visit


@dataclass
class _Edge:
    parent: str
    child: str
    flip: bool  # draw parent below/right of child
    link: str = "birth"  # birth, adopted, foster or step


def strip_control(text: str) -> str:
    return _CONTROL_RE.sub("", text)


def _split_variant(variant: str) -> str:
    # _build_chart also draws plain pedigrees; hourglass and bowtie must not.
    if variant not in ("ancestor-split", "descendants"):
        raise ValueError(f"Unknown variant: {variant}")
    return variant


def _escape_dot_text(text: str) -> str:
    """Strip control characters, then escape for a DOT double-quoted label.

    Backslash and double-quote would end or bend the string; & would start an
    entity, which Graphviz decodes even in plain labels.
    """
    text = strip_control(text)
    text = text.replace("\\", "\\\\")
    # Graphviz decodes HTML entities even in plain labels, so "&#27;" in a name
    # would come back out as a raw ESC byte.
    text = text.replace("&", "&amp;")
    return text.replace('"', '\\"')


def _escape_id(xref_id: str | None) -> str:
    if xref_id is None:
        return "_"
    cleaned = _NONALNUM_RE.sub("_", xref_id.replace("@", ""))
    if not cleaned or cleaned[0].isdigit() or cleaned.lower() in _DOT_KEYWORDS:
        cleaned = "_" + cleaned
    return cleaned


class _NodeIds:
    """Readable DOT ids, unique even when two xrefs escape to the same text."""

    def __init__(self) -> None:
        self._ids: dict[tuple[str, str], str] = {}
        self._taken: set[str] = set()
        self._next: dict[str, int] = {}

    def get(self, xref_id: str | None, side: str = "") -> tuple[str, bool]:
        """Id for (side, xref) and whether it was just issued."""
        key = (side, xref_id or "")
        if key in self._ids:
            return self._ids[key], False
        base = node_id = _escape_id(xref_id)
        n = self._next.get(base, 2)
        while node_id in self._taken:
            node_id = f"{base}_{n}"
            n += 1
        self._next[base] = n
        self._taken.add(node_id)
        self._ids[key] = node_id
        return node_id, True

    def share(self, xref_id: str | None, side: str, node_id: str) -> None:
        self._ids[(side, xref_id or "")] = node_id


class DotGenerator:
    def __init__(self, parser: GedcomParser):
        self.parser = parser

    def _require(self, individual_id: str) -> Individual:
        individual = self.parser.get_individual(individual_id)
        if not individual:
            raise ValueError(f"Individual {individual_id} not found")
        return individual

    def _header(self, chart_type: str, rankdir: str, comment: str) -> list[str]:
        return [
            f"digraph {chart_type} {{",
            f"  rankdir={rankdir};",
            f'  node [shape=box, style="rounded,filled", fillcolor={COLOR_DEFAULT}];',
            f"  // {comment}",
            "",
        ]

    @staticmethod
    def _couple_lines(a: str, b: str, married: bool) -> list[str]:
        style = "solid" if married else "dashed"
        return [
            f"  {a} -> {b} [dir=none, style={style}, constraint=false];",
            f"  {{rank=same; {a}; {b};}}",
        ]

    def generate_pedigree(self, individual_id: str, generations: int = 4) -> str:
        individual = self._require(individual_id)
        nodes, edges = self._build_chart(individual, generations, "pedigree")
        return self._render_chart(
            "Pedigree",
            individual,
            nodes,
            edges,
            comment_suffix=f" - {generations} generations",
        )

    def _build_chart(
        self, individual: Individual, generations: int, variant: str
    ) -> tuple[list[_Node], list[_Edge]]:
        """Walk the tree around individual, one node per (side, person).

        In ancestor-split the father's ancestors are side "p" and the mother's
        side "m", so someone on both sides (cousin marriage) gets two nodes.
        """
        if variant not in ("pedigree", "ancestor-split", "descendants"):
            raise ValueError(f"Unknown variant: {variant}")

        nodes: list[_Node] = []
        edges: list[_Edge] = []
        ids = _NodeIds()
        linked: dict[tuple[str, str], _Edge] = {}

        def visit(side: str, ind: Individual, generation: int) -> tuple[str, bool]:
            node_id, new = ids.get(ind.xref_id, side)
            if new:
                nodes.append(
                    _Node(
                        node_id=node_id,
                        individual=ind,
                        focal=ind is individual,
                        side=side,
                        generation=generation,
                    )
                )
            return node_id, new

        def parent_pair(ind: Individual) -> tuple[Individual | None, Individual | None, str]:
            fam, link = self.parser.parent_family(ind) or (None, "birth")
            father, mother = self.parser.couple(fam)
            return self.parser.get_individual(father), self.parser.get_individual(mother), link

        def parents(ind: Individual) -> list[tuple[Individual, str]]:
            father, mother, link = parent_pair(ind)
            return [(p, link) for p in (father, mother) if p]

        def children(ind: Individual) -> list[tuple[Individual, str]]:
            return [(child, link) for child, _, link in self.parser.child_links(ind)]

        def walk(
            focal_id: str, side: str, first: list[tuple[Individual, str]], up: bool, flip: bool
        ) -> None:
            step = 1 if up else -1
            queue = deque([(individual, focal_id, 0)])
            while queue:
                ind, ind_id, gen = queue.popleft()
                if abs(gen) >= generations:
                    continue
                if gen == 0:
                    relatives = first
                elif up:
                    relatives = parents(ind)
                else:
                    relatives = children(ind)
                for rel, link in relatives:
                    rel_id, new = visit(side, rel, gen + step)
                    parent, child = (rel_id, ind_id) if up else (ind_id, rel_id)
                    edge = linked.get((parent, child))
                    if edge is None:
                        edge = linked[(parent, child)] = _Edge(parent, child, flip, link)
                        edges.append(edge)
                    elif link == "birth":
                        # One parent can list the same child twice: as a birth
                        # child in one family and an implied step child in another.
                        edge.link = "birth"
                    if new:
                        queue.append((rel, rel_id, gen + step))

        focal_id, _ = visit("", individual, 0)
        if variant == "ancestor-split":
            ids.share(individual.xref_id, "p", focal_id)
            ids.share(individual.xref_id, "m", focal_id)
            father, mother, link = parent_pair(individual)
            walk(focal_id, "p", [(father, link)] if father else [], up=True, flip=False)
            walk(focal_id, "m", [(mother, link)] if mother else [], up=True, flip=True)
        else:
            walk(focal_id, "", parents(individual), up=True, flip=False)
            if variant == "descendants":
                walk(focal_id, "", children(individual), up=False, flip=False)

        return nodes, edges

    def _render_chart(
        self,
        chart_type: str,
        individual: Individual,
        nodes: list[_Node],
        edges: list[_Edge],
        *,
        rankdir: str = "TB",
        comment_suffix: str = "",
    ) -> str:
        """Generic chart renderer for pedigree/hourglass/bowtie."""
        name = strip_control(self.parser.get_name(individual))
        lines = self._header(chart_type, rankdir, f"{name}{comment_suffix}")

        generation = {}
        for node in nodes:
            generation[node.node_id] = node.generation
            label = self._format_label(node.individual)
            color = COLOR_FOCAL if node.focal else COLOR_DEFAULT
            lines.append(f'  {node.node_id} [label="{label}", fillcolor={color}];')

        lines.append("")
        for edge in edges:
            attrs = []
            # dot ranks an edge's tail before its head, so a reversed edge with
            # dir=back puts the parent below/right while the arrow still points
            # at the child.
            if edge.flip:
                attrs.append("dir=back")
            # Pedigree collapse: an ancestor already placed by a shorter line also
            # parents someone at another depth, even one above it. Letting that
            # edge rank it would push whole generations onto the wrong rows, so it
            # is drawn but not ranked.
            if generation[edge.parent] - generation[edge.child] != 1:
                attrs.append("constraint=false")
            if edge.link != "birth":
                attrs.append("style=dotted")
            tail, head = (edge.child, edge.parent) if edge.flip else (edge.parent, edge.child)
            suffix = f" [{', '.join(attrs)}]" if attrs else ""
            lines.append(f"  {tail} -> {head}{suffix};")

        lines.append("}")
        return "\n".join(lines)

    def generate_hourglass(
        self, individual_id: str, generations: int = 4, variant: str = "ancestor-split"
    ) -> str:
        individual = self._require(individual_id)
        nodes, edges = self._build_chart(individual, generations, _split_variant(variant))
        return self._render_chart("Hourglass", individual, nodes, edges)

    def generate_bowtie(
        self, individual_id: str, generations: int = 4, variant: str = "ancestor-split"
    ) -> str:
        individual = self._require(individual_id)
        nodes, edges = self._build_chart(individual, generations, _split_variant(variant))
        return self._render_chart("Bowtie", individual, nodes, edges, rankdir="LR")

    def generate_relationship(self, paths: list[RelationshipPath], comment: str) -> str:
        """Draw paths[0]; comment is the summary line, caveats and all."""
        if not paths:
            raise ValueError("No paths provided")

        path = paths[0]
        start = self.parser.get_individual(path.start_id)
        end = self.parser.get_individual(path.end_id)

        if not start or not end:
            raise ValueError("Invalid start or end individual")

        lines = self._header("Relationship", "TB", strip_control(comment))

        all_ids = path.ids()
        ids = _NodeIds()

        def node_id(xref_id: str | None) -> str:
            return ids.get(xref_id)[0]

        # The other parent comes from the family the step went through, which for
        # an adoptive or step link is not the child's birth family.
        spouse_map = {}
        for step in path.steps:
            if not step.is_parent:
                continue
            parent = self.parser.get_individual(step.individual_id)
            for xref in self.parser.couple(step.family):
                spouse = self.parser.get_individual(xref)
                if parent and spouse and xref != step.individual_id and xref not in all_ids:
                    married = self.parser.is_couple_married(parent, spouse)
                    spouse_map[step.individual_id] = (spouse, married)

        couple_edges = {}
        for ind_id in all_ids:
            ind = self.parser.get_individual(ind_id)
            if not ind:
                continue
            label = self._format_label(ind)

            color = COLOR_DEFAULT
            if ind_id == path.start_id:
                color = COLOR_FOCAL
            elif ind_id == path.end_id:
                color = COLOR_END

            lines.append(f'  {node_id(ind_id)} [label="{label}", fillcolor={color}];')

            if ind_id in spouse_map:
                spouse, married = spouse_map[ind_id]
                sp_id = node_id(spouse.xref_id)
                sp_label = self._format_label(spouse)
                lines.append(f'  {sp_id} [label="{sp_label}", fillcolor={COLOR_SPOUSE}];')
                edge, rank = self._couple_lines(node_id(ind_id), sp_id, married)
                lines.append(rank)
                couple_edges[ind_id] = edge

        lines.append("")
        lines.extend(couple_edges.values())

        lines.append("")
        curr_id = path.start_id
        for step in path.steps:
            curr_node = node_id(curr_id)
            next_node = node_id(step.individual_id)

            if step.link == "spouse":
                curr = self.parser.get_individual(curr_id)
                nxt = self.parser.get_individual(step.individual_id)
                married = bool(curr and nxt and self.parser.is_couple_married(curr, nxt))
                lines.extend(self._couple_lines(curr_node, next_node, married))
            else:
                attrs = "" if step.link == "birth" else " [style=dotted]"
                if step.is_parent:
                    lines.append(f"  {next_node} -> {curr_node}{attrs};")
                else:
                    lines.append(f"  {curr_node} -> {next_node}{attrs};")

            curr_id = step.individual_id

        lines.append("}")
        return "\n".join(lines)

    def _format_label(self, individual: Individual) -> str:
        name = _escape_dot_text(self.parser.get_name(individual))
        birth = self.parser.get_birth_year(individual)
        death = self.parser.get_death_year(individual)

        if birth or death:
            b = _escape_dot_text(birth or "?")
            d = _escape_dot_text(death or "")
            label = f"{name}\\n({b} - {d})"
        else:
            label = name

        return label
