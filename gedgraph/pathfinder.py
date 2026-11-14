from __future__ import annotations

from dataclasses import KW_ONLY, dataclass
from itertools import pairwise
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ged4py.model import Individual

    from .parser import GedcomParser

# Search states, not people: a person can be held twice, once climbing and once
# after a step down.
_MAX_NODES = 200_000
_MAX_PATHS = 10_000


@dataclass
class PathStep:
    individual_id: str
    is_parent: bool  # True if going up (to parent), False if going down (to child)
    via_male: bool
    _: KW_ONLY
    link: str = "birth"  # birth, adopted, foster, step or spouse
    family: str | None = None


@dataclass
class RelationshipPath:
    steps: list[PathStep]
    start_id: str
    end_id: str

    def length(self) -> int:
        return len(self.steps)

    def ids(self) -> list[str]:
        return [self.start_id] + [step.individual_id for step in self.steps]


def is_half(path: RelationshipPath, parser: GedcomParser) -> bool:
    """Whether a birth-only path climbs to and descends from different families of its apex."""
    steps = path.steps
    if any(step.link != "birth" for step in steps):
        return False
    ups = next((i for i, step in enumerate(steps) if not step.is_parent), len(steps))
    if ups == 0 or ups == len(steps) or any(step.is_parent for step in steps[ups:]):
        return False
    return parser.half_blood(steps[ups - 1].family, steps[ups].family)


def _step_order(step: PathStep) -> tuple[bool, bool]:
    return step.link not in ("birth", "spouse"), not step.via_male


# (xref, descended): whether the route to this person has gone down a generation.
_State = tuple[str, bool]


class PathFinder:
    def __init__(self, parser: GedcomParser):
        self.parser = parser
        self.truncated = False
        self.depth_limited = False

    def find_relationship_paths(
        self, start_id: str, end_id: str, max_depth: int = 50
    ) -> list[RelationshipPath]:
        self.truncated = False
        self.depth_limited = False
        start = self.parser.get_individual(start_id)
        end = self.parser.get_individual(end_id)

        if not start or not end:
            return []
        # Callers may pass ids without the @s; paths carry the canonical xref.
        start_id, end_id = start.xref_id or start_id, end.xref_id or end_id

        if start_id == end_id:
            return [RelationshipPath(steps=[], start_id=start_id, end_id=end_id)]

        # Marriage links are tried only when there is no line of descent, so
        # they can never displace a blood or adoptive relationship.
        paths = self._search(start, start_id, end_id, max_depth, spouses=False)
        if paths:
            return paths
        if end in self.parser.spouses(start):
            # Kept even if the search above was cut off; the flags stay set so
            # callers can say a blood tie may have been missed.
            step = PathStep(end_id, is_parent=False, via_male=True, link="spouse")
            return [RelationshipPath(steps=[step], start_id=start_id, end_id=end_id)]
        if self.truncated or self.depth_limited:
            # An in-law route must not stand in for descent the search never reached.
            return []
        return self._search(start, start_id, end_id, max_depth, spouses=True)

    def _search(
        self, start: Individual, start_id: str, end_id: str, max_depth: int, spouses: bool
    ) -> list[RelationshipPath]:
        """Breadth-first, one level at a time, expanding each state once.

        The blood search follows lines of descent only: once a route has gone
        down it never climbs again, so it cannot pass through a shared
        descendant. The marriage search may go down and up freely.
        """
        origin: _State = (start_id, False)
        depth = {origin: 0}
        preds: dict[_State, list[tuple[_State, PathStep]]] = {origin: []}
        level: list[tuple[_State, Individual]] = [(origin, start)]
        count = 0

        def next_state(state: _State, step: PathStep) -> _State | None:
            if spouses:
                return (step.individual_id, False)
            descended = state[1]
            if descended and step.is_parent:
                return None
            if descended or not step.is_parent:
                # Someone already reached by climbing, no deeper than here, can
                # take every step a descended copy of them could, so the copy is
                # dropped (it would only be start -> parent -> start and the like).
                # Ties in the same level are kept: they are other routes.
                climbed = depth.get((step.individual_id, False))
                if climbed is not None and climbed <= depth[state]:
                    return None
                return (step.individual_id, True)
            return (step.individual_id, False)

        for d in range(max_depth):
            following: list[tuple[_State, Individual]] = []
            ends: list[_State] = []
            spent = False
            for state, person in level:
                for neighbor, step in self._get_neighbors(person, spouses):
                    to = next_state(state, step)
                    if to is None:
                        continue
                    if to not in depth:
                        if to[0] == end_id:
                            ends.append(to)
                        elif count >= _MAX_NODES:
                            spent = True
                            continue
                        else:
                            count += 1
                            following.append((to, neighbor))
                        depth[to] = d + 1
                        preds[to] = []
                    if depth[to] == d + 1:
                        preds[to].append((state, step))

            # The level that reaches the end is finished whatever the cap.
            if ends:
                return self._unwind(ends, preds, start_id, end_id)
            if spent:
                self.truncated = True
                return []
            if not following:
                return []
            level = following

        # Out of levels: the limit mattered only if someone new lies one step on.
        self.depth_limited = any(
            (to := next_state(state, step)) is not None and to not in depth
            for state, person in level
            for _, step in self._get_neighbors(person, spouses)
        )
        return []

    def _unwind(
        self,
        ends: list[_State],
        preds: dict[_State, list[tuple[_State, PathStep]]],
        start_id: str,
        end_id: str,
    ) -> list[RelationshipPath]:
        # Every tied shortest path, unless there are more than _MAX_PATHS of
        # them. Then taking the best step first at each hop is only a heuristic:
        # the whole budget may go to one end state, and the route kept can be the
        # male line through half-siblings when a full-blood one also exists.
        paths: list[RelationshipPath] = []
        stack: list[tuple[_State, list[PathStep]]] = [(end, []) for end in reversed(ends)]
        while stack and len(paths) < _MAX_PATHS:
            state, tail = stack.pop()
            if not preds[state]:
                paths.append(RelationshipPath(steps=tail, start_id=start_id, end_id=end_id))
                continue
            options = sorted(preds[state], key=lambda pred: _step_order(pred[1]))
            stack.extend((prev, [step, *tail]) for prev, step in reversed(options))
        return paths

    def _get_neighbors(
        self, individual: Individual, spouses: bool
    ) -> list[tuple[Individual, PathStep]]:
        """One step per neighbouring person, preferring a birth link over any other."""
        couple = self.parser.couple
        links = [
            (parent, fam, link, True, couple(fam)[0] == parent.xref_id)
            for parent, fam, link in self.parser.parent_links(individual)
        ]
        links += [
            (child, fam, link, False, couple(fam)[0] == individual.xref_id)
            for child, fam, link in self.parser.child_links(individual)
        ]

        found: dict[str, tuple[Individual, PathStep]] = {}
        for person, fam, link, up, male in links:
            xref = person.xref_id
            if xref is None:
                continue
            if xref not in found or (link == "birth" and found[xref][1].link != "birth"):
                found[xref] = (person, PathStep(xref, up, male, link=link, family=fam))

        if spouses:
            for spouse in self.parser.spouses(individual):
                if spouse.xref_id is not None and spouse.xref_id not in found:
                    step = PathStep(spouse.xref_id, is_parent=False, via_male=True, link="spouse")
                    found[spouse.xref_id] = (spouse, step)

        return list(found.values())

    def _rank(self, path: RelationshipPath) -> tuple[int, int, int, bool, int]:
        steps = path.steps
        non_birth = sum(step.link not in ("birth", "spouse") for step in steps)
        # A route down to a child and up to its other parent says nothing a
        # marriage edge would not say better.
        turns = sum(
            not one.is_parent and one.link != "spouse" and two.is_parent
            for one, two in pairwise(steps)
        )
        non_male = sum(not step.via_male for step in steps)
        return (path.length(), non_birth, turns, is_half(path, self.parser), non_male)

    def get_shortest_paths(
        self, start_id: str, end_id: str, max_depth: int = 50
    ) -> list[RelationshipPath]:
        all_paths = self.find_relationship_paths(start_id, end_id, max_depth)
        if not all_paths:
            return []

        ranked = [(self._rank(p), p) for p in all_paths]
        best = min(rank for rank, _ in ranked)
        return [p for rank, p in ranked if rank == best]
