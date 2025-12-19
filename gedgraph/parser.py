"""GEDCOM parsing utilities."""

from typing import Optional

from ged4py import GedcomReader


class GedcomParser:
    """Parse and query GEDCOM files."""

    def __init__(self, gedcom_path: str):
        """
        Initialize parser with GEDCOM file.

        Args:
            gedcom_path: Path to GEDCOM file
        """
        self.gedcom_path = gedcom_path
        self.gedcom = None
        self._individuals = {}
        self._families = {}
        self._reader = None

    def load(self):
        """Load and parse the GEDCOM file."""
        self._reader = GedcomReader(self.gedcom_path)
        self._reader.__enter__()

        self.gedcom = list(self._reader.records0("INDI"))
        for indi in self.gedcom:
            self._individuals[indi.xref_id] = indi

        for fam in self._reader.records0("FAM"):
            self._families[fam.xref_id] = fam

    def get_individual(self, xref_id: str):
        """
        Get individual record by ID.

        Args:
            xref_id: Individual ID (e.g., '@I10@')

        Returns:
            Individual record or None if not found
        """
        if not xref_id.startswith("@"):
            xref_id = f"@{xref_id}@"
        return self._individuals.get(xref_id)

    def get_name(self, individual) -> str:
        """
        Get formatted name for an individual.

        Uses sequence: NPFX/TITL GIVN SURN NSFX

        Args:
            individual: Individual record

        Returns:
            Formatted name string
        """
        name_rec = individual.sub_tag("NAME")
        if not name_rec:
            return "Unknown"

        # Try to build name from GEDCOM sub-tags first
        name_parts = []

        # Get all the name components
        npfx = name_rec.sub_tag("NPFX")
        titl = name_rec.sub_tag("TITL")
        givn = name_rec.sub_tag("GIVN")
        surn = name_rec.sub_tag("SURN")
        nsfx = name_rec.sub_tag("NSFX")

        # Prefer prefix, but use title if prefix not available
        prefix_or_title = None
        if npfx and npfx.value:
            prefix_or_title = str(npfx.value)
        elif titl and titl.value:
            prefix_or_title = str(titl.value)

        if prefix_or_title:
            name_parts.append(prefix_or_title)

        # Add given name
        if givn and givn.value:
            name_parts.append(str(givn.value))
        elif name_rec.value and isinstance(name_rec.value, tuple) and name_rec.value[0]:
            name_parts.append(str(name_rec.value[0]))

        # Add surname
        if surn and surn.value:
            name_parts.append(str(surn.value))
        elif name_rec.value and isinstance(name_rec.value, tuple) and name_rec.value[1]:
            name_parts.append(str(name_rec.value[1]))

        # Add suffix
        if nsfx and nsfx.value:
            name_parts.append(str(nsfx.value))
        elif (
            name_rec.value
            and isinstance(name_rec.value, tuple)
            and len(name_rec.value) > 2
            and name_rec.value[2]
        ):
            name_parts.append(str(name_rec.value[2]))

        if name_parts:
            return " ".join(name_parts).strip()

        # Fallback to the raw NAME value if no sub-tags worked
        if name_rec.value:
            if isinstance(name_rec.value, tuple):
                given, surname, suffix = name_rec.value
                parts = [p for p in [given, surname, suffix] if p]
                return " ".join(parts).strip()
            # Remove slashes from simple string values
            return str(name_rec.value).replace("/", "")

        return "Unknown"

    def get_birth_year(self, individual) -> Optional[str]:
        """
        Get birth year for an individual.

        Tries BIRT first, then falls back to BAPM or CHR if needed.

        Args:
            individual: Individual record

        Returns:
            Birth year string or None
        """
        # Try birth date first
        birth = individual.sub_tag("BIRT")
        if birth:
            date = birth.sub_tag("DATE")
            if date and date.value:
                date_str = str(date.value)
                parts = date_str.split()
                # Year is typically the last token in GEDCOM dates
                return parts[-1] if parts else None

        # Fall back to baptism or christening date
        bapt = individual.sub_tag("BAPM") or individual.sub_tag("CHR")
        if bapt:
            date = bapt.sub_tag("DATE")
            if date and date.value:
                date_str = str(date.value)
                parts = date_str.split()
                return parts[-1] if parts else None

        return None

    def get_death_year(self, individual) -> Optional[str]:
        """
        Get death year for an individual.

        Args:
            individual: Individual record

        Returns:
            Death year string or None
        """
        death = individual.sub_tag("DEAT")
        if death:
            date = death.sub_tag("DATE")
            if date and date.value:
                date_str = str(date.value)
                parts = date_str.split()
                return parts[-1] if parts else None

        burial = individual.sub_tag("BURI")
        if burial:
            date = burial.sub_tag("DATE")
            if date and date.value:
                date_str = str(date.value)
                parts = date_str.split()
                return parts[-1] if parts else None

        return None

    def get_parents(self, individual):
        """
        Get parents of an individual.

        Args:
            individual: Individual record

        Returns:
            Tuple of (father, mother) records, either may be None
        """
        father = None
        mother = None

        famc = individual.sub_tag("FAMC")
        if famc:
            family = self._get_family(famc.xref_id)
            if family:
                husb = family.sub_tag("HUSB")
                wife = family.sub_tag("WIFE")
                if husb:
                    father = self.get_individual(husb.xref_id)
                if wife:
                    mother = self.get_individual(wife.xref_id)

        return father, mother

    def get_families_as_spouse(self, individual):
        """
        Get families where individual is a spouse.

        Args:
            individual: Individual record

        Returns:
            List of family records
        """
        families = []
        for fams in individual.sub_tags("FAMS"):
            family = self._get_family(fams.xref_id)
            if family:
                families.append(family)
        return families

    def get_children(self, individual):
        """
        Get children of an individual.

        Args:
            individual: Individual record

        Returns:
            List of child individual records
        """
        children = []
        for family in self.get_families_as_spouse(individual):
            for child_ref in family.sub_tags("CHIL"):
                child = self.get_individual(child_ref.xref_id)
                if child:
                    children.append(child)
        return children

    def _get_family(self, xref_id: str):
        """
        Get family record by ID.

        Args:
            xref_id: Family ID

        Returns:
            Family record or None
        """
        return self._families.get(xref_id)

    def get_sex(self, individual) -> Optional[str]:
        """
        Get sex of individual.

        Args:
            individual: Individual record

        Returns:
            'M' for male, 'F' for female, None if unknown
        """
        sex = individual.sub_tag("SEX")
        return str(sex.value) if sex and sex.value else None

    def is_full_sibling(self, ind1, ind2) -> bool:
        """
        Check if two individuals are full siblings (same parents).

        Args:
            ind1: First individual
            ind2: Second individual

        Returns:
            True if full siblings
        """
        p1_father, p1_mother = self.get_parents(ind1)
        p2_father, p2_mother = self.get_parents(ind2)

        if not (p1_father and p1_mother and p2_father and p2_mother):
            return False

        return p1_father.xref_id == p2_father.xref_id and p1_mother.xref_id == p2_mother.xref_id

    def is_half_sibling(self, ind1, ind2) -> bool:
        """
        Check if two individuals are half siblings (one common parent).

        Args:
            ind1: First individual
            ind2: Second individual

        Returns:
            True if half siblings
        """
        p1_father, p1_mother = self.get_parents(ind1)
        p2_father, p2_mother = self.get_parents(ind2)

        same_father = p1_father and p2_father and p1_father.xref_id == p2_father.xref_id
        same_mother = p1_mother and p2_mother and p1_mother.xref_id == p2_mother.xref_id

        return (same_father or same_mother) and not (same_father and same_mother)

    def get_spouse_for_child(self, individual, child):
        """
        Get the spouse of an individual in the context of a specific child.

        Args:
            individual: Parent individual
            child: Child individual

        Returns:
            Tuple of (spouse individual, is_married boolean) or (None, False)
        """
        child_father, child_mother = self.get_parents(child)
        if not child_father or not child_mother:
            return None, False

        spouse = None
        if individual.xref_id == child_father.xref_id:
            spouse = child_mother
        elif individual.xref_id == child_mother.xref_id:
            spouse = child_father

        if not spouse:
            return None, False

        is_married = self._is_couple_married(individual, spouse)
        return spouse, is_married

    def _is_couple_married(self, ind1, ind2) -> bool:
        """
        Check if two individuals were married.

        Args:
            ind1: First individual
            ind2: Second individual

        Returns:
            True if married, False otherwise
        """
        for family in self.get_families_as_spouse(ind1):
            husb = family.sub_tag("HUSB")
            wife = family.sub_tag("WIFE")

            if husb and wife:
                husb_id = husb.xref_id
                wife_id = wife.xref_id

                if (husb_id == ind1.xref_id and wife_id == ind2.xref_id) or (
                    husb_id == ind2.xref_id and wife_id == ind1.xref_id
                ):
                    marr = family.sub_tag("MARR")
                    return marr is not None

        return False
