import argparse
import sys
from pathlib import Path
from .dotgen import DotGenerator
from .parser import GedcomParser
from .pathfinder import PathFinder


def main():
    parser = argparse.ArgumentParser(
        description="Generate genealogical charts from GEDCOM files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  gedgraph pedigree family.ged @I10@ -o pedigree.dot
  gedgraph relationship family.ged @I10@ @I20@ -o rel.dot
  gedgraph hourglass family.ged @I10@ -v descendants -o hourglass.dot
  gedgraph bowtie family.ged @I10@ -v ancestor-split -o bowtie.dot

  # Render with GraphViz
  dot -Tpng output.dot -o output.png
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    pedigree_parser = subparsers.add_parser(
        "pedigree", help="Generate pedigree chart for an individual"
    )
    pedigree_parser.add_argument("gedcom", type=str, help="Path to GEDCOM file")
    pedigree_parser.add_argument("individual", type=str, help="Individual ID (e.g., @I10@)")
    pedigree_parser.add_argument(
        "-g", "--generations", type=int, default=4, help="Number of generations (default: 4)"
    )
    pedigree_parser.add_argument(
        "-o", "--output", type=str, required=True, help="Output DOT file path"
    )

    relationship_parser = subparsers.add_parser(
        "relationship", help="Generate relationship chart between two individuals"
    )
    relationship_parser.add_argument("gedcom", type=str, help="Path to GEDCOM file")
    relationship_parser.add_argument("individual1", type=str, help="First individual ID")
    relationship_parser.add_argument("individual2", type=str, help="Second individual ID")
    relationship_parser.add_argument(
        "-o", "--output", type=str, required=True, help="Output DOT file path"
    )
    relationship_parser.add_argument(
        "-d",
        "--max-depth",
        type=int,
        default=50,
        help="Maximum search depth (default: 50)",
    )

    hourglass_parser = subparsers.add_parser(
        "hourglass", help="Generate hourglass chart (ancestors and descendants)"
    )
    hourglass_parser.add_argument("gedcom", type=str, help="Path to GEDCOM file")
    hourglass_parser.add_argument("individual", type=str, help="Center individual ID (e.g., @I10@)")
    hourglass_parser.add_argument(
        "-g", "--generations", type=int, default=4,
        help="Number of generations in each direction (default: 4)"
    )
    hourglass_parser.add_argument(
        "-v", "--variant", choices=["ancestor-split", "descendants"],
        default="ancestor-split",
        help="Chart variant: ancestor-split (father above, mother below) or descendants (ancestors above, descendants below)"
    )
    hourglass_parser.add_argument(
        "-o", "--output", type=str, required=True, help="Output DOT file path"
    )

    bowtie_parser = subparsers.add_parser(
        "bowtie", help="Generate bowtie chart (horizontal hourglass)"
    )
    bowtie_parser.add_argument("gedcom", type=str, help="Path to GEDCOM file")
    bowtie_parser.add_argument("individual", type=str, help="Center individual ID (e.g., @I10@)")
    bowtie_parser.add_argument(
        "-g", "--generations", type=int, default=4,
        help="Number of generations in each direction (default: 4)"
    )
    bowtie_parser.add_argument(
        "-v", "--variant", choices=["ancestor-split", "descendants"],
        default="ancestor-split",
        help="Chart variant: ancestor-split (father left, mother right) or descendants (ancestors left, descendants right)"
    )
    bowtie_parser.add_argument(
        "-o", "--output", type=str, required=True, help="Output DOT file path"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    gedcom_path = Path(args.gedcom)
    if not gedcom_path.exists():
        print(f"Error: GEDCOM file not found: {args.gedcom}", file=sys.stderr)
        sys.exit(1)

    try:
        gp = GedcomParser(str(gedcom_path))
        gp.load()
        gen = DotGenerator(gp)

        if args.command == "pedigree":
            ind = gp.get_individual(args.individual)
            if not ind:
                sys.exit(f"Error: Individual {args.individual} not found")

            dot = gen.generate_pedigree(args.individual, args.generations)
            Path(args.output).write_text(dot)
            print(f"Pedigree: {gp.get_name(ind)} - {args.generations} gen -> {args.output}")

        elif args.command == "relationship":
            ind1 = gp.get_individual(args.individual1)
            ind2 = gp.get_individual(args.individual2)

            if not ind1:
                sys.exit(f"Error: Individual {args.individual1} not found")
            if not ind2:
                sys.exit(f"Error: Individual {args.individual2} not found")

            pf = PathFinder(gp)
            paths = pf.get_shortest_paths(args.individual1, args.individual2, args.max_depth)

            if not paths:
                sys.exit(f"Error: No relationship found between {args.individual1} and {args.individual2}")

            dot = gen.generate_relationship(paths)
            Path(args.output).write_text(dot)
            print(f"Relationship: {gp.get_name(ind1)} to {gp.get_name(ind2)} ({paths[0].length()} steps) -> {args.output}")

        elif args.command == "hourglass":
            ind = gp.get_individual(args.individual)
            if not ind:
                sys.exit(f"Error: Individual {args.individual} not found")

            dot = gen.generate_hourglass(args.individual, args.generations, args.variant)
            Path(args.output).write_text(dot)
            print(f"Hourglass: {gp.get_name(ind)} ({args.variant}) -> {args.output}")

        elif args.command == "bowtie":
            ind = gp.get_individual(args.individual)
            if not ind:
                sys.exit(f"Error: Individual {args.individual} not found")

            dot = gen.generate_bowtie(args.individual, args.generations, args.variant)
            Path(args.output).write_text(dot)
            print(f"Bowtie: {gp.get_name(ind)} ({args.variant}) -> {args.output}")

    except Exception as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
