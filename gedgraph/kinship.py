"""Plain-English names for the relationship a path describes."""

from __future__ import annotations

from itertools import groupby
from typing import TYPE_CHECKING

from .pathfinder import is_half

if TYPE_CHECKING:
    from .parser import GedcomParser
    from .pathfinder import RelationshipPath

# (male, female, neutral); uncle and nephew have no single neutral word.
_WORDS = {
    "parent": ("father", "mother", "parent"),
    "child": ("son", "daughter", "child"),
    "sibling": ("brother", "sister", "sibling"),
    "uncle": ("uncle", "aunt", ""),
    "nephew": ("nephew", "niece", ""),
    "spouse": ("husband", "wife", "spouse"),
}
_COUSINS = [
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "ninth",
    "tenth",
]
_REMOVED = {0: "", 1: " once removed", 2: " twice removed"}


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _greats(n: int) -> str:
    if n == 0:
        return ""
    return "great-" if n == 1 else f"{_ordinal(n)} great-"


def _lineal(k: int, word: str) -> str:
    return word if k == 1 else f"{_greats(k - 2)}grand{word}"


def _blood(a: int, b: int, sex: int) -> str:
    if b == 0:
        return _lineal(a, _WORDS["parent"][sex])
    if a == 0:
        return _lineal(b, _WORDS["child"][sex])
    if a == b == 1:
        return _WORDS["sibling"][sex]
    if b == 1:
        if sex == 2:
            return f"{_lineal(a - 1, 'parent')}'s sibling"
        return _greats(a - 2) + _WORDS["uncle"][sex]
    if a == 1:
        if sex == 2:
            return f"sibling's {_lineal(b - 1, 'child')}"
        return _greats(b - 2) + _WORDS["nephew"][sex]

    degree = min(a, b) - 1
    removed = abs(a - b)
    word = _COUSINS[degree - 1] if degree <= len(_COUSINS) else _ordinal(degree)
    return f"{word} cousin{_REMOVED.get(removed, f' {removed} times removed')}"


def _couple_term(path: RelationshipPath, parser: GedcomParser, sex: int) -> str:
    start = parser.get_individual(path.start_id)
    end = parser.get_individual(path.end_id)
    if start and end and parser.is_couple_married(start, end):
        return _WORDS["spouse"][sex]
    return "partner"


def describe(path: RelationshipPath, parser: GedcomParser) -> str | None:
    """Name the end person's relationship to the start person, e.g. "first cousin"."""
    runs = [(up, len(list(group))) for up, group in groupby(s.is_parent for s in path.steps)]
    if not runs:
        return None

    end = parser.get_individual(path.end_id)
    # "Private is X's daughter" would still give away what RESN hid.
    code = parser.get_sex(end) if end and not parser.is_private(end) else None
    sex = {"M": 0, "F": 1}.get(code or "", 2)
    shape = [up for up, _ in runs]

    if any(step.link == "spouse" for step in path.steps):
        return _couple_term(path, parser, sex) if path.length() == 1 else "relative by marriage"

    if shape in ([True], [False], [True, False]):
        a = runs[0][1] if runs[0][0] else 0
        b = 0 if runs[-1][0] else runs[-1][1]
        term = _blood(a, b, sex)
        # The loosest link names the tie, whichever end it is seen from: an
        # adoptive parent's stepchild is a stepbrother both ways round.
        kinds = {s.link for s in path.steps}
        link = next((k for k in ("step", "foster", "adopted") if k in kinds), "birth")
        if link == "step":
            # English has step- words only for parent, child and sibling.
            return f"step{term}" if a <= 1 and b <= 1 else "relative by marriage"
        if link != "birth":
            return f"{'adoptive' if link == 'adopted' else link} {term}"
        if is_half(path, parser):
            if term.endswith("'s sibling"):
                term = term.removesuffix("sibling") + "half-sibling"
            else:
                term = f"half-{term}"
        return term

    return "relative by marriage"


def sentence(start: str, end: str, term: str | None, steps: int) -> str:
    """The summary line for a relationship; term is describe()'s result."""
    if term is None:
        return f"{start} and {end} are the same person"
    unit = "step" if steps == 1 else "steps"
    return f"{end} is {start}'s {term} ({steps} {unit})"
