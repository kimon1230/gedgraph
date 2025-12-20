"""Command-line interface for GedGraph."""

import argparse
import sys
from pathlib import Path

from .dotgen import DotGenerator
from .parser import GedcomParser
from .pathfinder import PathFinder


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate genealogical charts from GEDCOM files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate pedigree chart for individual @I10@
  gedgraph pedigree family.ged @I10@ -o output.dot

  # Generate relationship chart between two individuals
  gedgraph relationship family.ged @I10@ @I20@ -o output.dot

  # Specify number of generations for pedigree
  gedgraph pedigree family.ged @I10@ -g 5 -o output.dot
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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    gedcom_path = Path(args.gedcom)
    if not gedcom_path.exists():
        print(f"Error: GEDCOM file not found: {args.gedcom}", file=sys.stderr)
        sys.exit(1)

    try:
        gedcom_parser = GedcomParser(str(gedcom_path))
        gedcom_parser.load()

        if args.command == "pedigree":
            individual = gedcom_parser.get_individual(args.individual)
            if not individual:
                print(
                    f"Error: Individual {args.individual} not found in GEDCOM file",
                    file=sys.stderr,
                )
                sys.exit(1)

            dot_gen = DotGenerator(gedcom_parser)
            dot_content = dot_gen.generate_pedigree(args.individual, args.generations)

            with open(args.output, "w") as f:
                f.write(dot_content)

            print(f"Pedigree chart generated: {args.output}")
            print(f"Individual: {gedcom_parser.get_name(individual)} ({args.individual})")
            print(f"Generations: {args.generations}")

        elif args.command == "relationship":
            individual1 = gedcom_parser.get_individual(args.individual1)
            individual2 = gedcom_parser.get_individual(args.individual2)

            if not individual1:
                print(
                    f"Error: Individual {args.individual1} not found in GEDCOM file",
                    file=sys.stderr,
                )
                sys.exit(1)

            if not individual2:
                print(
                    f"Error: Individual {args.individual2} not found in GEDCOM file",
                    file=sys.stderr,
                )
                sys.exit(1)

            pathfinder = PathFinder(gedcom_parser)
            paths = pathfinder.get_shortest_paths(
                args.individual1, args.individual2, args.max_depth
            )

            if not paths:
                print(
                    f"Error: No relationship found between {args.individual1} "
                    f"and {args.individual2}",
                    file=sys.stderr,
                )
                print(
                    f"  {gedcom_parser.get_name(individual1)} ({args.individual1})",
                    file=sys.stderr,
                )
                print(
                    f"  {gedcom_parser.get_name(individual2)} ({args.individual2})",
                    file=sys.stderr,
                )
                sys.exit(1)

            dot_gen = DotGenerator(gedcom_parser)
            dot_content = dot_gen.generate_relationship(paths)

            with open(args.output, "w") as f:
                f.write(dot_content)

            print(f"Relationship chart generated: {args.output}")
            print(f"From: {gedcom_parser.get_name(individual1)} ({args.individual1})")
            print(f"To: {gedcom_parser.get_name(individual2)} ({args.individual2})")
            print(f"Path length: {paths[0].length()} steps")
            print(f"Generation distance: {paths[0].generation_distance()}")

            if len(paths) > 1:
                print(f"Note: {len(paths)} equally short paths found, showing first")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
