from collections import deque
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class PathStep:
    individual_id: str
    is_parent: bool  # True if going up (to parent), False if going down (to child)
    is_full_blood: bool
    via_male: bool


@dataclass
class RelationshipPath:
    steps: List[PathStep]
    start_id: str
    end_id: str

    def length(self) -> int:
        return len(self.steps)

    def generation_distance(self) -> int:
        """Positive = descendant, negative = ancestor, 0 = same generation."""
        distance = 0
        for step in self.steps:
            distance += -1 if step.is_parent else 1
        return distance

    def sorting_key(self) -> Tuple:
        """Sort by: length, full blood preference, male line preference."""
        blood_score = sum(0 if step.is_full_blood else 1 for step in self.steps)
        male_score = sum(0 if step.via_male else 1 for step in self.steps)
        return (self.length(), blood_score, male_score)


class PathFinder:
    def __init__(self, parser):
        self.parser = parser

    def _bfs_traverse(self, individual_id: str, generations: int, get_relatives_fn):
        """Generic BFS traversal - used for both ancestors and descendants."""
        individual = self.parser.get_individual(individual_id)
        if not individual:
            return []

        results = []
        queue = deque([(individual, 0)])
        visited = {individual.xref_id}

        while queue:
            current, gen = queue.popleft()
            results.append((current, gen))

            if gen < generations:
                relatives = get_relatives_fn(current)
                for relative in relatives:
                    if relative and relative.xref_id not in visited:
                        visited.add(relative.xref_id)
                        queue.append((relative, gen + 1))

        return results

    def find_pedigree(self, individual_id: str, generations: int = 4):
        results = self._bfs_traverse(
            individual_id,
            generations,
            lambda ind: [p for p in self.parser.get_parents(ind) if p]
        )
        return [ind for ind, _ in results]

    def find_pedigree_with_generations(self, individual_id: str, generations: int = 4) -> List[Tuple]:
        return self._bfs_traverse(
            individual_id,
            generations,
            lambda ind: [p for p in self.parser.get_parents(ind) if p]
        )

    def find_descendants(self, individual_id: str, generations: int = 4) -> List[Tuple]:
        return self._bfs_traverse(
            individual_id,
            generations,
            lambda ind: self.parser.get_children(ind)
        )

    def find_pedigree_split(self, individual_id: str, generations: int = 4) -> Tuple[List[Tuple], List[Tuple]]:
        individual = self.parser.get_individual(individual_id)
        if not individual:
            return ([], [])

        father, mother = self.parser.get_parents(individual)

        paternal = []
        if father:
            paternal = [(ind, gen + 1) for ind, gen in
                       self.find_pedigree_with_generations(father.xref_id, generations - 1)]

        maternal = []
        if mother:
            maternal = [(ind, gen + 1) for ind, gen in
                       self.find_pedigree_with_generations(mother.xref_id, generations - 1)]

        return (paternal, maternal)

    def find_relationship_paths(self, start_id: str, end_id: str, max_depth: int = 50) -> List[RelationshipPath]:
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
            depth = len(path)

            if (min_length and depth > min_length) or depth >= max_depth:
                continue

            for neighbor, step in self._get_neighbors(current):
                if neighbor.xref_id == end.xref_id:
                    new_path = RelationshipPath(steps=path + [step], start_id=start_id, end_id=end_id)
                    paths.append(new_path)
                    if min_length is None:
                        min_length = len(new_path.steps)
                    continue

                if neighbor.xref_id not in visited or visited[neighbor.xref_id] >= depth + 1:
                    visited[neighbor.xref_id] = depth + 1
                    queue.append((neighbor, path + [step]))

        return paths

    def _get_neighbors(self, individual) -> List[Tuple]:
        neighbors = []
        father, mother = self.parser.get_parents(individual)

        if father:
            neighbors.append((father, PathStep(
                individual_id=father.xref_id,
                is_parent=True,
                is_full_blood=True,
                via_male=True
            )))

        if mother:
            neighbors.append((mother, PathStep(
                individual_id=mother.xref_id,
                is_parent=True,
                is_full_blood=True,
                via_male=False
            )))

        is_male = self.parser.get_sex(individual) == "M"
        for child in self.parser.get_children(individual):
            neighbors.append((child, PathStep(
                individual_id=child.xref_id,
                is_parent=False,
                is_full_blood=self._is_full_blood(individual, child),
                via_male=is_male
            )))

        return neighbors

    def _is_full_blood(self, parent, child) -> bool:
        """Check if parent-child relationship is full blood (both parents in same family)."""
        child_father, child_mother = self.parser.get_parents(child)
        if not child_father or not child_mother:
            return False

        for family in self.parser.get_families_as_spouse(parent):
            husb = family.sub_tag("HUSB")
            wife = family.sub_tag("WIFE")
            if husb and wife:
                if child_father.xref_id == husb.xref_id and child_mother.xref_id == wife.xref_id:
                    return True

        return False

    def get_shortest_paths(self, start_id: str, end_id: str, max_depth: int = 50) -> List[RelationshipPath]:
        all_paths = self.find_relationship_paths(start_id, end_id, max_depth)
        if not all_paths:
            return []

        all_paths.sort(key=lambda p: p.sorting_key())
        shortest_key = all_paths[0].sorting_key()
        return [p for p in all_paths if p.sorting_key() == shortest_key]
