"""Generate GraphViz DOT files for genealogical charts."""

from typing import List, Set, Dict

from .pathfinder import PathFinder, RelationshipPath, RelationType


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

        # Use PathFinder to get pedigree with generation tracking
        pathfinder = PathFinder(self.parser)
        pedigree_list = pathfinder.find_pedigree_with_generations(
            individual_id, generations
        )

        # Group individuals by generation
        generations_map: Dict[int, List] = {}
        for ind, gen in pedigree_list:
            if gen not in generations_map:
                generations_map[gen] = []
            generations_map[gen].append(ind)

        lines = [
            "digraph Pedigree {",
            "  rankdir=TB;",
            '  node [shape=box, style="rounded,filled", fillcolor=lightblue];',
            "",
            f"  // Pedigree chart for {self.parser.get_name(individual)}",
            f"  // Root: {individual_id}",
            f"  // Generations: {generations}",
            "",
        ]

        visited_individuals = set()

        # Process generations from highest (oldest ancestors) to lowest (root)
        for gen_num in sorted(generations_map.keys(), reverse=True):
            individuals = generations_map[gen_num]
            ranksame_nodes = []

            for ind in individuals:
                node_id = self._escape_id(ind.xref_id)
                label = self._format_individual_label(ind)

                # Color root differently
                fillcolor = "lightcoral" if gen_num == 0 else "lightgreen"
                lines.append(f'  {node_id} [label="{label}", fillcolor={fillcolor}];')
                ranksame_nodes.append(node_id)
                visited_individuals.add(ind.xref_id)

            # Add ranksame constraint for this generation
            if ranksame_nodes:
                nodes_str = "; ".join(ranksame_nodes)
                lines.append(f"  {{rank=same; {nodes_str};}}")

        lines.append("")

        # Add parent-child edges
        for gen_num in sorted(generations_map.keys()):
            if gen_num > 0:  # Has parents
                for ind in generations_map[gen_num]:
                    father, mother = self.parser.get_parents(ind)
                    child_node = self._escape_id(ind.xref_id)

                    if father and father.xref_id in visited_individuals:
                        father_node = self._escape_id(father.xref_id)
                        lines.append(f"  {father_node} -> {child_node};")

                    if mother and mother.xref_id in visited_individuals:
                        mother_node = self._escape_id(mother.xref_id)
                        lines.append(f"  {mother_node} -> {child_node};")

        lines.append("}")
        return "\n".join(lines)

    def generate_hourglass(
        self, individual_id: str, generations: int = 4, variant: str = "ancestor-split"
    ) -> str:
        """
        Generate DOT file for hourglass chart.

        Args:
            individual_id: Center individual ID
            generations: Number of generations in each direction
            variant: "ancestor-split" (father above, mother below) or
                    "descendants" (ancestors above, descendants below)

        Returns:
            DOT format string
        """
        individual = self.parser.get_individual(individual_id)
        if not individual:
            raise ValueError(f"Individual {individual_id} not found")

        pathfinder = PathFinder(self.parser)
        generations_map: Dict[int, List] = {}

        if variant == "ancestor-split":
            # Father's pedigree above (positive generations)
            # Mother's pedigree below (negative generations)
            # Root at generation 0
            father, mother = self.parser.get_parents(individual)

            # Add root
            generations_map[0] = [individual]

            # Get paternal ancestors
            if father:
                paternal_ancestors = pathfinder.find_pedigree_with_generations(
                    father.xref_id, generations - 1
                )
                for ind, gen in paternal_ancestors:
                    # Adjust to positive generations (father line goes above)
                    adj_gen = gen + 1
                    if adj_gen not in generations_map:
                        generations_map[adj_gen] = []
                    generations_map[adj_gen].append(ind)

            # Get maternal ancestors
            if mother:
                maternal_ancestors = pathfinder.find_pedigree_with_generations(
                    mother.xref_id, generations - 1
                )
                for ind, gen in maternal_ancestors:
                    # Adjust to negative generations (mother line goes below)
                    adj_gen = -(gen + 1)
                    if adj_gen not in generations_map:
                        generations_map[adj_gen] = []
                    generations_map[adj_gen].append(ind)

        elif variant == "descendants":
            # Ancestors above (positive generations)
            # Descendants below (negative generations)
            # Root at generation 0

            # Get ancestors
            ancestors = pathfinder.find_pedigree_with_generations(
                individual_id, generations
            )
            for ind, gen in ancestors:
                if gen not in generations_map:
                    generations_map[gen] = []
                generations_map[gen].append(ind)

            # Get descendants
            descendants = pathfinder.find_descendants(individual_id, generations)
            for ind, gen in descendants:
                # Make generation negative for descendants (except root)
                if gen > 0:
                    adj_gen = -gen
                    if adj_gen not in generations_map:
                        generations_map[adj_gen] = []
                    generations_map[adj_gen].append(ind)

        else:
            raise ValueError(f"Unknown variant: {variant}")

        lines = [
            "digraph Hourglass {",
            "  rankdir=TB;",
            '  node [shape=box, style="rounded,filled", fillcolor=lightblue];',
            "",
            f"  // Hourglass chart for {self.parser.get_name(individual)}",
            f"  // Root: {individual_id}",
            f"  // Variant: {variant}",
            f"  // Generations: {generations}",
            "",
        ]

        visited_individuals = set()

        # Process generations from highest to lowest
        for gen_num in sorted(generations_map.keys(), reverse=True):
            individuals = generations_map[gen_num]
            ranksame_nodes = []

            for ind in individuals:
                node_id = self._escape_id(ind.xref_id)
                label = self._format_individual_label(ind)

                # Color root differently
                fillcolor = "lightcoral" if gen_num == 0 else "lightgreen"
                lines.append(f'  {node_id} [label="{label}", fillcolor={fillcolor}];')
                ranksame_nodes.append(node_id)
                visited_individuals.add(ind.xref_id)

            # Add ranksame constraint for this generation
            if ranksame_nodes:
                nodes_str = "; ".join(ranksame_nodes)
                lines.append(f"  {{rank=same; {nodes_str};}}")

        lines.append("")

        # Add edges based on relationships
        for gen_num in sorted(generations_map.keys()):
            for ind in generations_map[gen_num]:
                node_id = self._escape_id(ind.xref_id)

                # Add parent-child edges
                father, mother = self.parser.get_parents(ind)
                if father and father.xref_id in visited_individuals:
                    father_node = self._escape_id(father.xref_id)
                    lines.append(f"  {father_node} -> {node_id};")

                if mother and mother.xref_id in visited_individuals:
                    mother_node = self._escape_id(mother.xref_id)
                    lines.append(f"  {mother_node} -> {node_id};")

        lines.append("}")
        return "\n".join(lines)

    def generate_bowtie(
        self, individual_id: str, generations: int = 4, variant: str = "ancestor-split"
    ) -> str:
        """
        Generate DOT file for bowtie chart (horizontal hourglass).

        Args:
            individual_id: Center individual ID
            generations: Number of generations in each direction
            variant: "ancestor-split" (father left, mother right) or
                    "descendants" (ancestors left, descendants right)

        Returns:
            DOT format string
        """
        individual = self.parser.get_individual(individual_id)
        if not individual:
            raise ValueError(f"Individual {individual_id} not found")

        pathfinder = PathFinder(self.parser)
        generations_map: Dict[int, List] = {}

        if variant == "ancestor-split":
            # Father's pedigree left (negative generations)
            # Mother's pedigree right (positive generations)
            # Root at generation 0
            father, mother = self.parser.get_parents(individual)

            # Add root
            generations_map[0] = [individual]

            # Get paternal ancestors
            if father:
                paternal_ancestors = pathfinder.find_pedigree_with_generations(
                    father.xref_id, generations - 1
                )
                for ind, gen in paternal_ancestors:
                    # Adjust to negative generations (father line goes left)
                    adj_gen = -(gen + 1)
                    if adj_gen not in generations_map:
                        generations_map[adj_gen] = []
                    generations_map[adj_gen].append(ind)

            # Get maternal ancestors
            if mother:
                maternal_ancestors = pathfinder.find_pedigree_with_generations(
                    mother.xref_id, generations - 1
                )
                for ind, gen in maternal_ancestors:
                    # Adjust to positive generations (mother line goes right)
                    adj_gen = gen + 1
                    if adj_gen not in generations_map:
                        generations_map[adj_gen] = []
                    generations_map[adj_gen].append(ind)

        elif variant == "descendants":
            # Ancestors left (negative generations)
            # Descendants right (positive generations)
            # Root at generation 0

            # Get ancestors
            ancestors = pathfinder.find_pedigree_with_generations(
                individual_id, generations
            )
            for ind, gen in ancestors:
                # Make generation negative for ancestors (except root)
                if gen > 0:
                    adj_gen = -gen
                    if adj_gen not in generations_map:
                        generations_map[adj_gen] = []
                    generations_map[adj_gen].append(ind)
                else:
                    # Root at 0
                    if 0 not in generations_map:
                        generations_map[0] = []
                    generations_map[0].append(ind)

            # Get descendants
            descendants = pathfinder.find_descendants(individual_id, generations)
            for ind, gen in descendants:
                # Descendants use positive generations
                if gen > 0:
                    if gen not in generations_map:
                        generations_map[gen] = []
                    generations_map[gen].append(ind)

        else:
            raise ValueError(f"Unknown variant: {variant}")

        lines = [
            "digraph Bowtie {",
            "  rankdir=LR;",
            '  node [shape=box, style="rounded,filled", fillcolor=lightblue];',
            "",
            f"  // Bowtie chart for {self.parser.get_name(individual)}",
            f"  // Root: {individual_id}",
            f"  // Variant: {variant}",
            f"  // Generations: {generations}",
            "",
        ]

        visited_individuals = set()

        # Process generations from left to right (negative to positive)
        for gen_num in sorted(generations_map.keys()):
            individuals = generations_map[gen_num]
            ranksame_nodes = []

            for ind in individuals:
                node_id = self._escape_id(ind.xref_id)
                label = self._format_individual_label(ind)

                # Color root differently
                fillcolor = "lightcoral" if gen_num == 0 else "lightgreen"
                lines.append(f'  {node_id} [label="{label}", fillcolor={fillcolor}];')
                ranksame_nodes.append(node_id)
                visited_individuals.add(ind.xref_id)

            # Add ranksame constraint for this generation
            if ranksame_nodes:
                nodes_str = "; ".join(ranksame_nodes)
                lines.append(f"  {{rank=same; {nodes_str};}}")

        lines.append("")

        # Add edges based on relationships
        for gen_num in sorted(generations_map.keys()):
            for ind in generations_map[gen_num]:
                node_id = self._escape_id(ind.xref_id)

                # Add parent-child edges
                father, mother = self.parser.get_parents(ind)
                if father and father.xref_id in visited_individuals:
                    father_node = self._escape_id(father.xref_id)
                    lines.append(f"  {father_node} -> {node_id};")

                if mother and mother.xref_id in visited_individuals:
                    mother_node = self._escape_id(mother.xref_id)
                    lines.append(f"  {mother_node} -> {node_id};")

        lines.append("}")
        return "\n".join(lines)

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
            Formatted label string with escaped quotes
        """
        name = self.parser.get_name(individual)
        birth = self.parser.get_birth_year(individual)
        death = self.parser.get_death_year(individual)

        if birth or death:
            birth_str = birth if birth else "?"
            death_str = death if death else ""
            if death_str:
                label = f"{name}\\n({birth_str} - {death_str})"
            else:
                label = f"{name}\\n({birth_str} - )"
        else:
            label = name

        return label.replace('"', '\\"')

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
