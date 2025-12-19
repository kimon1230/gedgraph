"""Generate GraphViz DOT files for genealogical charts."""

from typing import List, Set

from .pathfinder import RelationshipPath, RelationType


class DotGenerator:
    """Generate DOT format files for visualization."""

    def __init__(self, parser):
        """
        Initialize DotGenerator.

        Args:
            parser: GedcomParser instance
        """
        self.parser = parser

    def generate_pedigree(self, individual_id: str, generations: int = 4) -> str:
        """
        Generate DOT file for pedigree chart (ancestors).

        Args:
            individual_id: Root individual ID
            generations: Number of generations to include

        Returns:
            DOT format string
        """
        individual = self.parser.get_individual(individual_id)
        if not individual:
            raise ValueError(f"Individual {individual_id} not found")

        lines = [
            "digraph Pedigree {",
            "  rankdir=BT;",
            '  node [shape=box, style="rounded,filled", fillcolor=lightblue];',
            "",
            f"  // Pedigree chart for {self.parser.get_name(individual)}",
            f"  // Root: {individual_id}",
            f"  // Generations: {generations}",
            "",
        ]

        visited = set()
        self._add_pedigree_nodes(individual, lines, visited, 0, generations)

        lines.append("}")
        return "\n".join(lines)

    def _add_pedigree_nodes(
        self, individual, lines: List[str], visited: Set[str], gen: int, max_gen: int
    ):
        """
        Recursively add nodes and edges for pedigree chart.

        Args:
            individual: Current individual
            lines: List to append DOT lines to
            visited: Set of visited individual IDs
            gen: Current generation
            max_gen: Maximum generations to include
        """
        if not individual or gen > max_gen or individual.xref_id in visited:
            return

        visited.add(individual.xref_id)

        node_id = self._escape_id(individual.xref_id)
        label = self._format_individual_label(individual)
        lines.append(f'  {node_id} [label="{label}"];')

        if gen < max_gen:
            father, mother = self.parser.get_parents(individual)

            if father:
                father_id = self._escape_id(father.xref_id)
                lines.append(f"  {father_id} -> {node_id};")
                self._add_pedigree_nodes(father, lines, visited, gen + 1, max_gen)

            if mother:
                mother_id = self._escape_id(mother.xref_id)
                lines.append(f"  {mother_id} -> {node_id};")
                self._add_pedigree_nodes(mother, lines, visited, gen + 1, max_gen)

    def generate_relationship(self, paths: List[RelationshipPath]) -> str:
        """
        Generate DOT file for relationship chart between two individuals.

        Args:
            paths: List of RelationshipPath objects to visualize

        Returns:
            DOT format string
        """
        if not paths:
            raise ValueError("No paths provided")

        path = paths[0]
        start_id = path.start_id
        end_id = path.end_id

        start = self.parser.get_individual(start_id)
        end = self.parser.get_individual(end_id)

        if not start or not end:
            raise ValueError("Invalid start or end individual")

        gen_distance = path.generation_distance()
        relationship_desc = self._describe_relationship(path)

        lines = [
            "digraph Relationship {",
            "  rankdir=TB;",
            '  node [shape=box, style="rounded,filled", fillcolor=lightblue];',
            "",
            "  // Relationship chart",
            f"  // Start: {self.parser.get_name(start)} ({start_id})",
            f"  // End: {self.parser.get_name(end)} ({end_id})",
            f"  // Relationship: {relationship_desc}",
            f"  // Generation distance: {gen_distance}",
            f"  // Path length: {path.length()} steps",
            "",
        ]

        if len(paths) > 1:
            lines.append(f"  // Note: {len(paths)} equally short paths found")
            lines.append("")

        visited = set()
        all_individuals = [start_id]

        for step in path.steps:
            all_individuals.append(step.individual_id)

        # Find spouses for each person in the direct line
        # We look at pairs of individuals where one is the parent of the other
        spouse_map = {}
        for i in range(len(all_individuals) - 1):
            current_ind = self.parser.get_individual(all_individuals[i])
            next_ind = self.parser.get_individual(all_individuals[i + 1])
            if current_ind and next_ind:
                # Get the spouse of next_ind in the context of having current_ind as a child
                spouse, is_married = self.parser.get_spouse_for_child(next_ind, current_ind)
                # Only add if spouse exists and isn't already in the bloodline
                if spouse and spouse.xref_id not in all_individuals:
                    spouse_map[all_individuals[i + 1]] = (spouse, is_married)

        for ind_id in all_individuals:
            if ind_id not in visited:
                visited.add(ind_id)
                ind = self.parser.get_individual(ind_id)
                if ind:
                    node_id = self._escape_id(ind_id)
                    label = self._format_individual_label(ind)

                    fillcolor = "lightgreen"
                    if ind_id == start_id:
                        fillcolor = "lightcoral"
                    elif ind_id == end_id:
                        fillcolor = "lightblue"

                    lines.append(f'  {node_id} [label="{label}", fillcolor={fillcolor}];')

                    if ind_id in spouse_map:
                        spouse, is_married = spouse_map[ind_id]
                        spouse_id = self._escape_id(spouse.xref_id)
                        spouse_label = self._format_individual_label(spouse)
                        lines.append(
                            f'  {spouse_id} [label="{spouse_label}", fillcolor=lightyellow];'
                        )
                        lines.append(f"  {{rank=same; {node_id}; {spouse_id};}}")

        lines.append("")

        for ind_id, (spouse, is_married) in spouse_map.items():
            ind_node = self._escape_id(ind_id)
            spouse_node = self._escape_id(spouse.xref_id)
            style = "solid" if is_married else "dashed"
            lines.append(
                f"  {ind_node} -> {spouse_node} [dir=none, style={style}, constraint=false];"
            )

        lines.append("")

        current_id = start_id
        for step in path.steps:
            current_node = self._escape_id(current_id)
            next_node = self._escape_id(step.individual_id)

            if step.relation_type == RelationType.PARENT:
                lines.append(f"  {next_node} -> {current_node};")
            else:
                lines.append(f"  {current_node} -> {next_node};")

            current_id = step.individual_id

        lines.append("}")
        return "\n".join(lines)

    def _format_individual_label(self, individual) -> str:
        """
        Format individual information for node label.

        Args:
            individual: Individual record

        Returns:
            Formatted label string
        """
        name = self.parser.get_name(individual)
        birth = self.parser.get_birth_year(individual)
        death = self.parser.get_death_year(individual)

        if birth or death:
            birth_str = birth if birth else "?"
            death_str = death if death else ""
            if death_str:
                return f"{name}\\n({birth_str} - {death_str})"
            return f"{name}\\n({birth_str} - )"
        return name

    def _escape_id(self, xref_id: str) -> str:
        """
        Escape ID for use in DOT file.

        Args:
            xref_id: Individual ID

        Returns:
            Escaped ID safe for DOT format
        """
        return xref_id.replace("@", "").replace("-", "_")

    def _describe_relationship(self, path: RelationshipPath) -> str:
        """
        Generate human-readable relationship description.

        Args:
            path: RelationshipPath object

        Returns:
            Relationship description string
        """
        if not path.steps:
            return "Same individual"

        gen_dist = path.generation_distance()
        path_len = path.length()

        if gen_dist == 0:
            if path_len == 2:
                return "Siblings"
            return f"Collateral relatives ({path_len//2}th cousins)"
        if gen_dist > 0:
            if path_len == gen_dist:
                if gen_dist == 1:
                    return "Parent-Child"
                if gen_dist == 2:
                    return "Grandparent-Grandchild"
                return f"Direct ancestor ({gen_dist} generations)"
            return f"Descendant via collateral line ({gen_dist} generations down)"
        if path_len == abs(gen_dist):
            return f"Direct descendant ({abs(gen_dist)} generations)"
        return f"Ancestor via collateral line ({abs(gen_dist)} generations up)"
