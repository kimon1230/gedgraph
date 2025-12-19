"""Find relationship paths between individuals in a GEDCOM file."""

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple


class RelationType(Enum):
    """Types of genealogical relationships."""

    PARENT = "parent"
    CHILD = "child"


class BloodType(Enum):
    """Blood relationship types for sorting paths."""

    FULL = 1  # Full blood relationship
    HALF = 2  # Half blood relationship


@dataclass
class PathStep:
    """A single step in a relationship path."""

    individual_id: str
    relation_type: RelationType
    blood_type: BloodType
    via_male: bool  # True if relationship is through male line


@dataclass
class RelationshipPath:
    """A complete path between two individuals."""

    steps: List[PathStep]
    start_id: str
    end_id: str

    def length(self) -> int:
        """Get the number of steps in the path."""
        return len(self.steps)

    def generation_distance(self) -> int:
        """
        Calculate generation distance.

        Positive means end is descendant of start.
        Negative means end is ancestor of start.
        Zero means same generation (siblings, cousins, etc.)
        """
        distance = 0
        for step in self.steps:
            if step.relation_type == RelationType.CHILD:
                distance += 1
            elif step.relation_type == RelationType.PARENT:
                distance -= 1
        return distance

    def sorting_key(self) -> Tuple:
        """
        Generate sorting key for path comparison.

        Paths are sorted by:
        1. Length (shorter is better)
        2. Blood type (full blood preferred over half blood)
        3. Male line preference
        """
        blood_score = sum(step.blood_type.value for step in self.steps)
        male_score = sum(0 if step.via_male else 1 for step in self.steps)
        return (self.length(), blood_score, male_score)


class PathFinder:
    """Find relationship paths between individuals."""

    def __init__(self, parser):
        """
        Initialize PathFinder.

        Args:
            parser: GedcomParser instance
        """
        self.parser = parser

    def find_pedigree(self, individual_id: str, generations: int = 4):
        """
        Generate pedigree (ancestors) for an individual.

        Args:
            individual_id: ID of the individual
            generations: Number of generations to include

        Returns:
            List of individuals in the pedigree
        """
        pedigree = []
        individual = self.parser.get_individual(individual_id)
        if not individual:
            return pedigree

        queue = deque([(individual, 0)])
        visited = {individual.xref_id}

        while queue:
            current, gen = queue.popleft()
            pedigree.append(current)

            if gen < generations:
                father, mother = self.parser.get_parents(current)
                for parent in [father, mother]:
                    if parent and parent.xref_id not in visited:
                        visited.add(parent.xref_id)
                        queue.append((parent, gen + 1))

        return pedigree

    def find_relationship_paths(
        self, start_id: str, end_id: str, max_depth: int = 10
    ) -> List[RelationshipPath]:
        """
        Find all relationship paths between two individuals using BFS.

        Args:
            start_id: Starting individual ID
            end_id: Ending individual ID
            max_depth: Maximum search depth

        Returns:
            List of RelationshipPath objects, or empty list if no connection
        """
        start = self.parser.get_individual(start_id)
        end = self.parser.get_individual(end_id)

        if not start or not end:
            return []

        if start.xref_id == end.xref_id:
            return [RelationshipPath(steps=[], start_id=start_id, end_id=end_id)]

        paths = []
        queue = deque([(start, [])])
        visited = {start.xref_id: 0}
        min_length = None

        while queue:
            current, path = queue.popleft()
            current_depth = len(path)

            if min_length and current_depth > min_length:
                continue

            if current_depth >= max_depth:
                continue

            neighbors = self._get_neighbors(current)

            for neighbor, step in neighbors:
                if neighbor.xref_id == end.xref_id:
                    new_path = RelationshipPath(
                        steps=path + [step], start_id=start_id, end_id=end_id
                    )
                    paths.append(new_path)
                    if min_length is None:
                        min_length = len(new_path.steps)
                    continue

                if (
                    neighbor.xref_id not in visited
                    or visited[neighbor.xref_id] >= current_depth + 1
                ):
                    visited[neighbor.xref_id] = current_depth + 1
                    queue.append((neighbor, path + [step]))

        return paths

    def _get_neighbors(self, individual) -> List[Tuple]:
        """
        Get all neighboring individuals (parents and children) with relationship info.

        Args:
            individual: Individual record

        Returns:
            List of (neighbor_individual, PathStep) tuples
        """
        neighbors = []

        father, mother = self.parser.get_parents(individual)

        if father:
            neighbors.append(
                (
                    father,
                    PathStep(
                        individual_id=father.xref_id,
                        relation_type=RelationType.PARENT,
                        blood_type=BloodType.FULL,
                        via_male=True,
                    ),
                )
            )

        if mother:
            neighbors.append(
                (
                    mother,
                    PathStep(
                        individual_id=mother.xref_id,
                        relation_type=RelationType.PARENT,
                        blood_type=BloodType.FULL,
                        via_male=False,
                    ),
                )
            )

        children = self.parser.get_children(individual)
        for child in children:
            is_male = self.parser.get_sex(individual) == "M"
            blood_type = self._determine_blood_type(individual, child)

            neighbors.append(
                (
                    child,
                    PathStep(
                        individual_id=child.xref_id,
                        relation_type=RelationType.CHILD,
                        blood_type=blood_type,
                        via_male=is_male,
                    ),
                )
            )

        return neighbors

    def _determine_blood_type(self, parent, child) -> BloodType:
        """
        Determine if parent-child relationship is full or half blood.

        Args:
            parent: Parent individual
            child: Child individual

        Returns:
            BloodType enum value
        """
        parent_families = self.parser.get_families_as_spouse(parent)
        child_father, child_mother = self.parser.get_parents(child)

        if not child_father or not child_mother:
            return BloodType.HALF

        for family in parent_families:
            husb = family.sub_tag("HUSB")
            wife = family.sub_tag("WIFE")

            if husb and wife:
                family_father_id = husb.xref_id
                family_mother_id = wife.xref_id

                if (
                    child_father.xref_id == family_father_id
                    and child_mother.xref_id == family_mother_id
                ):
                    return BloodType.FULL

        return BloodType.HALF

    def get_shortest_paths(
        self, start_id: str, end_id: str, max_depth: int = 10
    ) -> List[RelationshipPath]:
        """
        Find shortest relationship paths with proper sorting.

        Returns paths sorted by:
        1. Blood via male preference
        2. Blood via female preference
        3. Half blood via male preference
        4. Half-blood via female preference

        Args:
            start_id: Starting individual ID
            end_id: Ending individual ID
            max_depth: Maximum search depth

        Returns:
            List of shortest RelationshipPath objects sorted by preference
        """
        all_paths = self.find_relationship_paths(start_id, end_id, max_depth)

        if not all_paths:
            return []

        all_paths.sort(key=lambda p: p.sorting_key())

        if not all_paths:
            return []

        shortest_length = all_paths[0].sorting_key()
        return [p for p in all_paths if p.sorting_key() == shortest_length]
