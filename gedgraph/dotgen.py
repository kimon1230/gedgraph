from typing import List, Dict
from .pathfinder import PathFinder, RelationshipPath


class DotGenerator:
    def __init__(self, parser):
        self.parser = parser

    def generate_pedigree(self, individual_id: str, generations: int = 4) -> str:
        individual = self.parser.get_individual(individual_id)
        if not individual:
            raise ValueError(f"Individual {individual_id} not found")

        pathfinder = PathFinder(self.parser)
        pedigree_list = pathfinder.find_pedigree_with_generations(individual_id, generations)

        gen_map = {}
        for ind, gen in pedigree_list:
            gen_map.setdefault(gen, []).append(ind)

        lines = [
            "digraph Pedigree {",
            "  rankdir=TB;",
            '  node [shape=box, style="rounded,filled", fillcolor=lightblue];',
            f"  // {self.parser.get_name(individual)} - {generations} generations",
            "",
        ]

        visited = set()
        for gen in sorted(gen_map.keys(), reverse=True):
            nodes = []
            for ind in gen_map[gen]:
                node_id = self._escape_id(ind.xref_id)
                label = self._format_label(ind)
                color = "lightcoral" if gen == 0 else "lightgreen"
                lines.append(f'  {node_id} [label="{label}", fillcolor={color}];')
                nodes.append(node_id)
                visited.add(ind.xref_id)

            if nodes:
                lines.append(f"  {{rank=same; {'; '.join(nodes)};}}")

        lines.append("")
        for gen in sorted(gen_map.keys()):
            if gen > 0:
                for ind in gen_map[gen]:
                    child_id = self._escape_id(ind.xref_id)
                    father, mother = self.parser.get_parents(ind)

                    if father and father.xref_id in visited:
                        lines.append(f"  {self._escape_id(father.xref_id)} -> {child_id};")
                    if mother and mother.xref_id in visited:
                        lines.append(f"  {self._escape_id(mother.xref_id)} -> {child_id};")

        lines.append("}")
        return "\n".join(lines)

    def _build_generation_map(self, individual_id, generations, variant):
        """Build generation map for hourglass/bowtie charts."""
        pathfinder = PathFinder(self.parser)
        individual = self.parser.get_individual(individual_id)
        gen_map = {}

        if variant == "ancestor-split":
            father, mother = self.parser.get_parents(individual)
            gen_map[0] = [individual]

            if father:
                for ind, gen in pathfinder.find_pedigree_with_generations(father.xref_id, generations - 1):
                    gen_map.setdefault(gen + 1, []).append(ind)

            if mother:
                for ind, gen in pathfinder.find_pedigree_with_generations(mother.xref_id, generations - 1):
                    gen_map.setdefault(-(gen + 1), []).append(ind)

        elif variant == "descendants":
            for ind, gen in pathfinder.find_pedigree_with_generations(individual_id, generations):
                gen_map.setdefault(gen, []).append(ind)

            for ind, gen in pathfinder.find_descendants(individual_id, generations):
                if gen > 0:
                    gen_map.setdefault(-gen, []).append(ind)
        else:
            raise ValueError(f"Unknown variant: {variant}")

        return gen_map

    def _render_chart(self, chart_type, individual, gen_map, rankdir="TB"):
        """Generic chart renderer for pedigree/hourglass/bowtie."""
        lines = [
            f"digraph {chart_type} {{",
            f"  rankdir={rankdir};",
            '  node [shape=box, style="rounded,filled", fillcolor=lightblue];',
            f"  // {self.parser.get_name(individual)}",
            "",
        ]

        visited = set()
        for gen in sorted(gen_map.keys(), reverse=(rankdir == "TB")):
            nodes = []
            for ind in gen_map[gen]:
                node_id = self._escape_id(ind.xref_id)
                label = self._format_label(ind)
                color = "lightcoral" if gen == 0 else "lightgreen"
                lines.append(f'  {node_id} [label="{label}", fillcolor={color}];')
                nodes.append(node_id)
                visited.add(ind.xref_id)

            if nodes:
                lines.append(f"  {{rank=same; {'; '.join(nodes)};}}")

        lines.append("")
        for ind_list in gen_map.values():
            for ind in ind_list:
                father, mother = self.parser.get_parents(ind)
                child_id = self._escape_id(ind.xref_id)

                if father and father.xref_id in visited:
                    lines.append(f"  {self._escape_id(father.xref_id)} -> {child_id};")
                if mother and mother.xref_id in visited:
                    lines.append(f"  {self._escape_id(mother.xref_id)} -> {child_id};")

        lines.append("}")
        return "\n".join(lines)

    def generate_hourglass(self, individual_id: str, generations: int = 4, variant: str = "ancestor-split") -> str:
        individual = self.parser.get_individual(individual_id)
        if not individual:
            raise ValueError(f"Individual {individual_id} not found")

        gen_map = self._build_generation_map(individual_id, generations, variant)
        return self._render_chart("Hourglass", individual, gen_map, "TB")

    def generate_bowtie(self, individual_id: str, generations: int = 4, variant: str = "ancestor-split") -> str:
        individual = self.parser.get_individual(individual_id)
        if not individual:
            raise ValueError(f"Individual {individual_id} not found")

        # Flip signs for horizontal layout
        gen_map = self._build_generation_map(individual_id, generations, variant)
        if variant == "ancestor-split":
            flipped = {-k if k != 0 else k: v for k, v in gen_map.items()}
            gen_map = flipped

        return self._render_chart("Bowtie", individual, gen_map, "LR")

    def generate_relationship(self, paths: List[RelationshipPath]) -> str:
        if not paths:
            raise ValueError("No paths provided")

        path = paths[0]
        start = self.parser.get_individual(path.start_id)
        end = self.parser.get_individual(path.end_id)

        if not start or not end:
            raise ValueError("Invalid start or end individual")

        lines = [
            "digraph Relationship {",
            "  rankdir=TB;",
            '  node [shape=box, style="rounded,filled", fillcolor=lightblue];',
            f"  // {self.parser.get_name(start)} to {self.parser.get_name(end)}",
            f"  // {self._describe_relationship(path)} ({path.length()} steps)",
            "",
        ]

        all_ids = [path.start_id] + [s.individual_id for s in path.steps]

        # Find spouses
        spouse_map = {}
        for i in range(len(all_ids) - 1):
            curr = self.parser.get_individual(all_ids[i])
            next = self.parser.get_individual(all_ids[i + 1])
            if curr and next:
                spouse, married = self.parser.get_spouse_for_child(next, curr)
                if spouse and spouse.xref_id not in all_ids:
                    spouse_map[all_ids[i + 1]] = (spouse, married)

        # Draw nodes
        for ind_id in all_ids:
            ind = self.parser.get_individual(ind_id)
            if ind:
                node_id = self._escape_id(ind_id)
                label = self._format_label(ind)

                color = "lightgreen"
                if ind_id == path.start_id:
                    color = "lightcoral"
                elif ind_id == path.end_id:
                    color = "lightblue"

                lines.append(f'  {node_id} [label="{label}", fillcolor={color}];')

                if ind_id in spouse_map:
                    spouse, married = spouse_map[ind_id]
                    sp_id = self._escape_id(spouse.xref_id)
                    sp_label = self._format_label(spouse)
                    lines.append(f'  {sp_id} [label="{sp_label}", fillcolor=lightyellow];')
                    lines.append(f"  {{rank=same; {node_id}; {sp_id};}}")

        lines.append("")

        # Draw spouse edges
        for ind_id, (spouse, married) in spouse_map.items():
            style = "solid" if married else "dashed"
            lines.append(f"  {self._escape_id(ind_id)} -> {self._escape_id(spouse.xref_id)} [dir=none, style={style}, constraint=false];")

        lines.append("")

        # Draw path edges
        curr_id = path.start_id
        for step in path.steps:
            curr_node = self._escape_id(curr_id)
            next_node = self._escape_id(step.individual_id)

            if step.is_parent:
                lines.append(f"  {next_node} -> {curr_node};")
            else:
                lines.append(f"  {curr_node} -> {next_node};")

            curr_id = step.individual_id

        lines.append("}")
        return "\n".join(lines)

    def _format_label(self, individual) -> str:
        name = self.parser.get_name(individual)
        birth = self.parser.get_birth_year(individual)
        death = self.parser.get_death_year(individual)

        if birth or death:
            b = birth or "?"
            d = death or ""
            label = f"{name}\\n({b} - {d})" if d else f"{name}\\n({b} - )"
        else:
            label = name

        return label.replace('"', '\\"')

    def _escape_id(self, xref_id: str) -> str:
        return xref_id.replace("@", "").replace("-", "_")

    def _describe_relationship(self, path: RelationshipPath) -> str:
        if not path.steps:
            return "Same individual"

        gen = path.generation_distance()
        length = path.length()

        if gen == 0:
            return "Siblings" if length == 2 else f"Collateral relatives ({length//2}th cousins)"

        if gen > 0:
            if length == gen:
                if gen == 1:
                    return "Parent-Child"
                if gen == 2:
                    return "Grandparent-Grandchild"
                return f"Direct ancestor ({gen} generations)"
            return f"Descendant via collateral ({gen} gen down)"

        if length == abs(gen):
            return f"Direct descendant ({abs(gen)} generations)"
        return f"Ancestor via collateral ({abs(gen)} gen up)"
