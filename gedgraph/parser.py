from __future__ import annotations

import re

from ged4py import GedcomReader
from ged4py.model import Individual, Record

_YEAR_RE = re.compile(r"\d{3,4}")


class GedcomParser:
    def __init__(self, gedcom_path: str):
        self.gedcom_path = gedcom_path
        self.gedcom: list[Individual] | None = None
        self._individuals: dict[str, Individual] = {}
        self._families: dict[str, Record] = {}
        self._reader: GedcomReader | None = None

    def load(self):
        self._reader = GedcomReader(self.gedcom_path)
        self._reader.__enter__()
        try:
            self.gedcom = list(self._reader.records0("INDI"))
            for indi in self.gedcom:
                self._individuals[indi.xref_id] = indi
            for fam in self._reader.records0("FAM"):
                self._families[fam.xref_id] = fam
        except Exception:
            self.close()
            raise

    def close(self):
        if self._reader:
            self._reader.__exit__(None, None, None)
            self._reader = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def get_individual(self, xref_id: str) -> Individual | None:
        if not xref_id.startswith("@"):
            xref_id = f"@{xref_id}@"
        return self._individuals.get(xref_id)

    def get_name(self, individual: Individual) -> str:
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
            return " ".join(parts).strip()

        if isinstance(name_rec.value, tuple):
            return " ".join(p for p in name_rec.value if p).strip()
        return str(name_rec.value).replace("/", "") if name_rec.value else "Unknown"

    def _extract_year(self, event: Record | None) -> str | None:
        """Extract year from GEDCOM event tag."""
        if not event:
            return None
        date = event.sub_tag("DATE")
        if date and date.value:
            parts = str(date.value).split()
            if parts and _YEAR_RE.fullmatch(parts[-1]):
                return parts[-1]
        return None

    def get_birth_year(self, individual: Individual) -> str | None:
        year = self._extract_year(individual.sub_tag("BIRT"))
        if not year:
            year = self._extract_year(individual.sub_tag("BAPM"))
        if not year:
            year = self._extract_year(individual.sub_tag("CHR"))
        return year

    def get_death_year(self, individual: Individual) -> str | None:
        year = self._extract_year(individual.sub_tag("DEAT"))
        if not year:
            year = self._extract_year(individual.sub_tag("BURI"))
        return year

    def get_parents(self, individual: Individual) -> tuple[Individual | None, Individual | None]:
        famc = individual.sub_tag("FAMC")
        if not famc:
            return None, None

        family = self._get_family(famc.xref_id)
        if not family:
            return None, None

        father = None
        mother = None
        husb = family.sub_tag("HUSB")
        wife = family.sub_tag("WIFE")

        if husb:
            father = self.get_individual(husb.xref_id)
        if wife:
            mother = self.get_individual(wife.xref_id)

        return father, mother

    def get_families_as_spouse(self, individual: Individual) -> list[Record]:
        families = []
        for fams in individual.sub_tags("FAMS"):
            family = self._get_family(fams.xref_id)
            if family:
                families.append(family)
        return families

    def get_children(self, individual: Individual) -> list[Individual]:
        children = []
        for family in self.get_families_as_spouse(individual):
            for child_ref in family.sub_tags("CHIL"):
                child = self.get_individual(child_ref.xref_id)
                if child:
                    children.append(child)
        return children

    def _get_family(self, xref_id: str) -> Record | None:
        return self._families.get(xref_id)

    def get_sex(self, individual: Individual) -> str | None:
        sex = individual.sub_tag("SEX")
        return str(sex.value) if sex and sex.value else None

    def is_full_sibling(self, ind1: Individual, ind2: Individual) -> bool:
        p1_father, p1_mother = self.get_parents(ind1)
        p2_father, p2_mother = self.get_parents(ind2)

        if not (p1_father and p1_mother and p2_father and p2_mother):
            return False

        return p1_father.xref_id == p2_father.xref_id and p1_mother.xref_id == p2_mother.xref_id

    def is_half_sibling(self, ind1: Individual, ind2: Individual) -> bool:
        p1_father, p1_mother = self.get_parents(ind1)
        p2_father, p2_mother = self.get_parents(ind2)

        same_father = p1_father and p2_father and p1_father.xref_id == p2_father.xref_id
        same_mother = p1_mother and p2_mother and p1_mother.xref_id == p2_mother.xref_id

        return (same_father or same_mother) and not (same_father and same_mother)

    def get_spouse_for_child(
        self, individual: Individual, child: Individual
    ) -> tuple[Individual | None, bool]:
        """Returns (spouse, is_married) tuple for the given parent-child relationship."""
        child_father, child_mother = self.get_parents(child)
        if not child_father or not child_mother:
            return None, False

        if individual.xref_id == child_father.xref_id:
            spouse = child_mother
        elif individual.xref_id == child_mother.xref_id:
            spouse = child_father
        else:
            return None, False

        is_married = self._is_couple_married(individual, spouse)
        return spouse, is_married

    def _is_couple_married(self, ind1: Individual, ind2: Individual) -> bool:
        for family in self.get_families_as_spouse(ind1):
            husb = family.sub_tag("HUSB")
            wife = family.sub_tag("WIFE")

            if (
                husb
                and wife
                and (
                    (husb.xref_id == ind1.xref_id and wife.xref_id == ind2.xref_id)
                    or (husb.xref_id == ind2.xref_id and wife.xref_id == ind1.xref_id)
                )
            ):
                return family.sub_tag("MARR") is not None

        return False
