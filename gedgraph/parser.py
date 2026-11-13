from __future__ import annotations

import re

from ged4py import GedcomReader, model
from ged4py.calendar import CalendarDate, CalendarType
from ged4py.date import (
    DateValue,
    DateValueAbout,
    DateValueAfter,
    DateValueBefore,
    DateValueCalculated,
    DateValueEstimated,
    DateValueFrom,
    DateValuePeriod,
    DateValuePhrase,
    DateValueRange,
    DateValueSimple,
    DateValueTo,
)
from ged4py.model import Individual, Record
from ged4py.parser import GedcomLine

# A free-text date yields a year only from its last word, and only when every
# earlier word reads as part of a date, so other numbers a researcher typed into
# the phrase (phone, reference, SSN) never show as one.
_PHRASE_YEAR_RE = re.compile(r"([1-9][0-9]{2,3})(?:/[0-9]{1,2})?")
_PHRASE_SPLIT_RE = re.compile(r"[\s.,()?]+")
_WESTERN_ESCAPE_RE = re.compile(r"@#D(?:JULIAN|GREGORIAN)@", re.IGNORECASE)
_JULIAN_ESCAPE_RE = re.compile(r"@#DJULIAN@", re.IGNORECASE)
_DUAL_YEAR_RE = re.compile(r"(?<=\d)/\d{1,4}\b")

_PHRASE_QUALIFIERS = {
    **dict.fromkeys(
        ("abt", "about", "circa", "ca", "c", "approx", "est", "estimated", "cal"), "c. "
    ),
    **dict.fromkeys(("bef", "before"), "bef. "),
    **dict.fromkeys(("aft", "after"), "aft. "),
}
_MONTHS = "january february march april may june july august september october november december"
_DAYS = [str(day) for day in range(1, 32)] + [f"0{day}" for day in range(1, 10)]
_PHRASE_FILLER = frozenset(
    _MONTHS.split() + [m[:3] for m in _MONTHS.split()] + _DAYS + ["sept", "born", "b"]
)
_PRIVATE_RESN = frozenset({"privacy", "confidential"})
# Real names are far shorter; a name built from thousands of CONC lines would
# otherwise fill every label, comment and summary line it appears in.
_MAX_NAME = 200


class _TolerantDate(model.Date):
    def freeze(self) -> model.Date:
        try:
            return super().freeze()
        except ValueError:
            # e.g. a dual year in a Julian date, or an unknown calendar escape.
            # read_record has already decoded the value to str by now.
            text: str = self.value  # type: ignore[assignment]
            if _JULIAN_ESCAPE_RE.search(text):
                # ged4py refuses dual years outside the Gregorian calendar.
                text = _DUAL_YEAR_RE.sub("", text)
                try:
                    self.value = DateValue.parse(text)  # type: ignore[assignment]
                    return self
                except ValueError:
                    pass
            self.value = DateValuePhrase(text)  # type: ignore[assignment]
            return self


def _phrase_year(text: str) -> str | None:
    # Any other calendar escape (Hebrew, French, a misspelled one) would show
    # its own year numbering as if it were Gregorian.
    text = _WESTERN_ESCAPE_RE.sub("", text)
    if "@#" in text:
        return None
    words = [w for w in _PHRASE_SPLIT_RE.split(text.lower()) if w]
    match = _PHRASE_YEAR_RE.fullmatch(words[-1]) if words else None
    if not match:
        return None
    prefix = ""
    for word in words[:-1]:
        if word in _PHRASE_QUALIFIERS:
            prefix = prefix or _PHRASE_QUALIFIERS[word]
        elif word not in _PHRASE_FILLER:
            return None
    return prefix + match.group(1)


# _make_record and Date.freeze are private ged4py API; the <0.6 pin holds them still.
class _Reader(GedcomReader):
    def _make_record(self, parent: Record | None, gline: GedcomLine) -> Record | None:
        rec = super()._make_record(parent, gline)
        if type(rec) is model.Date:
            rec.__class__ = _TolerantDate
        return rec


def _restricted(record: Record) -> bool:
    """RESN privacy or confidential (GEDCOM 7 allows a list, e.g. "CONFIDENTIAL, LOCKED").

    LOCKED only stops edits, so it hides nothing.
    """
    resn = record.sub_tag("RESN")
    words = re.split(r"[\s,]+", str(resn.value or "").lower()) if resn else []
    return not _PRIVATE_RESN.isdisjoint(words)


def _event_year(event: Record | None) -> str | None:
    """Year of an event's DATE for display, qualified with c./bef./aft. where inexact."""
    if not event:
        return None
    date = event.sub_tag("DATE")
    if not date or not isinstance(date.value, DateValue):
        return None
    value = date.value

    if isinstance(value, DateValuePhrase):
        return _phrase_year(value.phrase or "")

    cal_date: CalendarDate | None = None
    for attr in ("date", "date1", "date2"):
        cal_date = getattr(value, attr, None)
        if cal_date is not None:
            break
    if cal_date is None or cal_date.calendar in (CalendarType.HEBREW, CalendarType.FRENCH_R):
        return None
    # ged4py takes a short word before the year as a month ("Mai 1950", "born
    # 1902"), leaving month_num unset when it is not a GEDCOM one.
    if cal_date.month is not None and cal_date.month_num is None:
        if isinstance(value, DateValueSimple):
            return _phrase_year(cal_date.original or "")
        return None
    # ged4py accepts any digit run as a year; a 4000-digit one would fill the label.
    if not 0 < cal_date.year <= 9999:
        return None

    year = f"{cal_date.year} BC" if cal_date.bc else cal_date.year_str
    inexact = (
        DateValueAbout,
        DateValueEstimated,
        DateValueCalculated,
        DateValueRange,
        DateValuePeriod,
    )
    if isinstance(value, inexact):
        return f"c. {year}"
    if isinstance(value, (DateValueBefore, DateValueTo)):
        return f"bef. {year}"
    if isinstance(value, (DateValueAfter, DateValueFrom)):
        return f"aft. {year}"
    return year


def _sex_code(value: object) -> str | None:
    # Files write "Male", " m" or a bare SEX line; only the first letter counts.
    return str(value or "").strip().upper()[:1] or None


def _pedigree(famc: Record) -> str:
    for sub in famc.sub_records:
        if sub.tag == "PEDI":
            kind = str(sub.value or "").strip().lower()
            return kind if kind in ("adopted", "foster", "step") else "birth"
    return "birth"


class GedcomParser:
    def __init__(self, gedcom_path: str, include_private: bool = False):
        self.gedcom_path = gedcom_path
        # The file's own RESN privacy/confidential notices are honoured unless
        # the caller asks otherwise: the charts are made to be shared.
        self.include_private = include_private
        self._reader: GedcomReader | None = None
        self._clear()

    def _clear(self) -> None:
        self.gedcom: list[Individual] | None = None
        self._individuals: dict[str, Individual] = {}
        self._families: dict[str, Record] = {}
        self._couple: dict[str, list[str | None]] = {}
        self._famc_links: dict[str, list[tuple[str, str]]] = {}
        self._fam_children: dict[str, list[tuple[str, str]]] = {}
        self._spouse_fams: dict[str, list[str]] = {}

    def load(self) -> None:
        # Loading again starts from nothing, so no record of an earlier file lingers.
        self.close()
        self._clear()
        try:
            self._reader = _Reader(self.gedcom_path, errors="replace")
            # records0() is typed as yielding Record; the INDI tag narrows it to
            # Individual, which ged4py's annotation cannot express.
            self.gedcom = [
                indi for indi in self._reader.records0("INDI") if isinstance(indi, Individual)
            ]
            # Records without an xref id cannot be referenced by any FAM link, so
            # they can take part in no relationship. Skipping them keeps the
            # indexes keyed by str -- otherwise every such record collides on a
            # single None key and all but the last are silently discarded.
            for indi in self.gedcom:
                if indi.xref_id is not None:
                    self._individuals[indi.xref_id] = indi
            for fam in self._reader.records0("FAM"):
                if fam.xref_id is not None:
                    self._families[fam.xref_id] = fam
            self._build_links()
        except BaseException:
            # A half-built index would answer queries with a partial tree.
            self.close()
            self._clear()
            raise

    def _build_links(self) -> None:
        # Pointers are read as xref strings off sub_records: sub_tag(s) would
        # follow each one, re-reading the target record from disk.
        # Dicts stand in for ordered sets throughout: a file can give one family
        # thousands of CHIL lines, and a list membership test per line would
        # make loading it quadratic.
        chil, named = self._index_families()
        famc, fams = self._index_individuals(named)

        spouse_fams = {
            indi_id: dict.fromkeys(f for f in fams[indi_id] if indi_id in self._couple[f])
            for indi_id in self._individuals
        }
        for fam_id, couple in self._couple.items():
            for spouse in couple:
                if spouse:
                    spouse_fams[spouse].setdefault(fam_id)
        for indi_id in self._individuals:
            self._spouse_fams[indi_id] = list(spouse_fams[indi_id])
            self._famc_links[indi_id] = list(famc[indi_id].items())

        has_birth = {indi_id for indi_id, links in famc.items() if "birth" in links.values()}
        for fam_id, children in chil.items():
            entries = self._fam_children[fam_id] = []
            for indi_id in children:
                link = famc[indi_id].get(fam_id)
                if link is None:
                    link = "step" if indi_id in has_birth else "birth"
                    self._famc_links[indi_id].append((fam_id, link))
                entries.append((indi_id, link))
        for indi_id, links in famc.items():
            for fam_id, link in links.items():
                if indi_id not in chil[fam_id]:
                    self._fam_children[fam_id].append((indi_id, link))

    def _index_families(self) -> tuple[dict[str, dict[str, None]], set[tuple[str, int]]]:
        """Fill the HUSB/WIFE slots; return each family's CHIL list and the slots
        a HUSB/WIFE line named."""
        individuals = self._individuals
        chil: dict[str, dict[str, None]] = {}
        named: set[tuple[str, int]] = set()
        for fam_id, fam in self._families.items():
            couple: list[str | None] = [None, None]
            children: dict[str, None] = {}
            chil[fam_id] = children
            for sub in fam.sub_records:
                value = sub.value
                if not isinstance(value, str) or value not in individuals:
                    continue
                if sub.tag in ("HUSB", "WIFE") and value not in couple:
                    slot = 0 if sub.tag == "HUSB" else 1
                    # Two HUSB (or WIFE) lines: a same-sex couple, not a typo to drop.
                    if couple[slot] is not None:
                        slot = 1 - slot
                    if couple[slot] is None:
                        couple[slot] = value
                        named.add((fam_id, slot))
                elif sub.tag == "CHIL":
                    children.setdefault(value)
            self._couple[fam_id] = couple
        return chil, named

    def _index_individuals(
        self, named: set[tuple[str, int]]
    ) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, None]]]:
        """Return each person's FAMC {family: link kind} and FAMS families, in file order.

        Also seats a spouse whom only their own FAMS line names into the family's
        free husband or wife slot, by SEX where it has one.
        """
        families = self._families
        famc: dict[str, dict[str, str]] = {}
        fams: dict[str, dict[str, None]] = {}
        leftover: list[tuple[str, str]] = []
        for indi_id, indi in self._individuals.items():
            own_famc: dict[str, str] = {}
            own_fams: dict[str, None] = {}
            famc[indi_id], fams[indi_id] = own_famc, own_fams
            sex = None
            for sub in indi.sub_records:
                value = sub.value
                if sub.tag == "SEX":
                    sex = sex or _sex_code(value)
                elif not isinstance(value, str) or value not in families:
                    continue
                elif sub.tag == "FAMC" and value not in own_famc:
                    own_famc[value] = _pedigree(sub)
                elif sub.tag == "FAMS":
                    own_fams.setdefault(value)
            for fam_id in own_fams:
                couple = self._couple[fam_id]
                if indi_id in couple:
                    continue
                own = {"M": 0, "F": 1}.get(sex or "")
                if own is None:
                    leftover.append((indi_id, fam_id))
                elif couple[own] is None:
                    couple[own] = indi_id
                elif (fam_id, own) not in named:
                    leftover.append((indi_id, fam_id))
                # else a FAMS that contradicts the family's own HUSB/WIFE line: a
                # stale pointer, not a second spouse.
        # Whoever is left takes a free slot, wife first, so a spouse of unknown sex
        # counts as the male line only when partnered with a woman.
        for indi_id, fam_id in leftover:
            couple = self._couple[fam_id]
            for slot in (1, 0):
                if indi_id not in couple and couple[slot] is None:
                    couple[slot] = indi_id
        return famc, fams

    def close(self) -> None:
        if self._reader:
            # ged4py types exc_type as `type` rather than `type | None`, but the
            # no-exception call is None and the argument is ignored anyway.
            self._reader.__exit__(None, None, None)  # type: ignore[arg-type]
            self._reader = None

    def __enter__(self) -> GedcomParser:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_individual(self, xref_id: str | None) -> Individual | None:
        # ged4py's Record.xref_id is optional, so callers routinely hold one that
        # may be None. Looking up nothing finds nothing.
        if xref_id is None:
            return None
        if not xref_id.startswith("@"):
            xref_id = f"@{xref_id}@"
        return self._individuals.get(xref_id)

    def get_name(self, individual: Individual) -> str:
        if self.is_private(individual):
            return "Private"
        name_rec = individual.sub_tag("NAME")
        if not name_rec:
            return "Unknown"

        parts = []

        npfx = name_rec.sub_tag("NPFX")
        titl = name_rec.sub_tag("TITL")
        if npfx and npfx.value:
            parts.append(str(npfx.value))
        elif titl and titl.value:
            parts.append(str(titl.value))

        givn = name_rec.sub_tag("GIVN")
        if givn and givn.value:
            parts.append(str(givn.value))
        elif isinstance(name_rec.value, tuple) and name_rec.value[0]:
            parts.append(str(name_rec.value[0]))

        surn = name_rec.sub_tag("SURN")
        if surn and surn.value:
            parts.append(str(surn.value))
        elif isinstance(name_rec.value, tuple) and name_rec.value[1]:
            parts.append(str(name_rec.value[1]))

        nsfx = name_rec.sub_tag("NSFX")
        if nsfx and nsfx.value:
            parts.append(str(nsfx.value))
        elif isinstance(name_rec.value, tuple) and len(name_rec.value) > 2 and name_rec.value[2]:
            parts.append(str(name_rec.value[2]))

        if parts:
            name = " ".join(parts)
        elif isinstance(name_rec.value, tuple):
            name = " ".join(p for p in name_rec.value if p)
        else:
            name = str(name_rec.value or "").replace("/", "")
        name = name.strip() or "Unknown"
        return name if len(name) <= _MAX_NAME else name[: _MAX_NAME - 1] + "…"

    def is_private(self, individual: Individual) -> bool:
        """Whether the person's record carries RESN privacy or confidential (and
        include_private is off)."""
        return not self.include_private and _restricted(individual)

    def get_birth_year(self, individual: Individual) -> str | None:
        return self._year(individual, ("BIRT", "BAPM", "CHR"))

    def get_death_year(self, individual: Individual) -> str | None:
        return self._year(individual, ("DEAT", "BURI"))

    def _year(self, individual: Individual, tags: tuple[str, ...]) -> str | None:
        """Year of the first of tags with one, e.g. baptism when birth has no date."""
        if self.is_private(individual):
            return None
        for tag in tags:
            event = individual.sub_tag(tag)
            if event and not self.include_private and _restricted(event):
                # A baptism year would give away the birth year it stands in for.
                return None
            year = _event_year(event)
            if year:
                return year
        return None

    def parent_family(self, individual: Individual) -> tuple[str, str] | None:
        """(family xref, link kind) of the family whose parents count as the
        person's own: the first birth family with a parent, else the first
        family of any kind with one."""
        fallback = None
        for fam_id, link in self._famc_links.get(individual.xref_id or "", []):
            if any(self._couple[fam_id]):
                if link == "birth":
                    return fam_id, link
                fallback = fallback or (fam_id, link)
        return fallback

    def parent_links(self, individual: Individual) -> list[tuple[Individual, str, str]]:
        """(parent, family xref, link kind) for every parent in every family of origin."""
        return [
            (self._individuals[parent], fam_id, link)
            for fam_id, link in self._famc_links.get(individual.xref_id or "", [])
            for parent in self._couple[fam_id]
            if parent
        ]

    def child_links(self, individual: Individual) -> list[tuple[Individual, str, str]]:
        """(child, family xref, link kind) for every child of every family as spouse."""
        return [
            (self._individuals[child], fam_id, link)
            for fam_id in self._spouse_fams.get(individual.xref_id or "", [])
            for child, link in self._fam_children[fam_id]
        ]

    def spouses(self, individual: Individual) -> list[Individual]:
        found: list[Individual] = []
        for fam_id in self._spouse_fams.get(individual.xref_id or "", []):
            husb, wife = self._couple[fam_id]
            other = self.get_individual(wife if husb == individual.xref_id else husb)
            if other and other is not individual and other not in found:
                found.append(other)
        return found

    def get_sex(self, individual: Individual) -> str | None:
        """One upper-case letter (M, F, U...) whatever the file's spelling, or None."""
        sex = individual.sub_tag("SEX")
        return _sex_code(sex.value if sex else None)

    def couple(self, fam_xref: str | None) -> tuple[str | None, str | None]:
        """Xrefs in the family's husband and wife slots (HUSB/WIFE, or a FAMS-only spouse)."""
        husb, wife = self._couple.get(fam_xref or "", (None, None))
        return husb, wife

    def half_blood(self, fam1: str | None, fam2: str | None) -> bool:
        # Children of one family are never half-siblings, whatever parent it lacks.
        if fam1 is None or fam2 is None or fam1 == fam2:
            return False
        # Sets, not father/mother pairs: one person can be HUSB in one family and
        # WIFE in another (same-sex couples, or a swapped entry).
        parents1 = {p for p in self._couple.get(fam1, ()) if p}
        parents2 = {p for p in self._couple.get(fam2, ()) if p}
        # The same couple split across duplicate FAM records is still full blood.
        return bool(parents1 & parents2) and not (len(parents1) == 2 and parents1 == parents2)

    def is_couple_married(self, ind1: Individual, ind2: Individual) -> bool:
        # A marriage is an event of a restricted person's too.
        if self.is_private(ind1) or self.is_private(ind2):
            return False
        pair = {ind1.xref_id, ind2.xref_id}
        if None in pair or len(pair) != 2:
            return False
        return any(
            set(self._couple[fam_id]) == pair and self._families[fam_id].sub_tag("MARR") is not None
            for fam_id in self._spouse_fams.get(ind1.xref_id or "", [])
        )
