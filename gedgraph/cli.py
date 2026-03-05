import argparse
import sys
from pathlib import Path

from ged4py.parser import IntegrityError, ParserError

from .dotgen import DotGenerator
from .parser import GedcomParser
from .pathfinder import PathFinder
from .progress import PhaseTracker


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add gedcom positional arg and -o/--output, shared by all subcommands."""
    parser.add_argument("gedcom", type=str, help="Path to GEDCOM file")
    parser.add_argument("-o", "--output", type=str, required=True, help="Output DOT file path")


def _add_generation_args(parser: argparse.ArgumentParser) -> None:
    """Add -g/--generations, shared by pedigree, hourglass, and bowtie."""
    parser.add_argument(
        "-g",
        "--generations",
        type=int,
        default=4,
        help="Number of generations (1-15, default: 4). Cost doubles per generation.",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate genealogical charts from GEDCOM files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  gedgraph pedigree family.ged @I10@ -o pedigree.dot
  gedgraph --quiet relationship family.ged @I10@ @I20@ -o rel.dot
  gedgraph --verbose hourglass family.ged @I10@ -v descendants -o hourglass.dot
  gedgraph bowtie family.ged @I10@ -v ancestor-split -o bowtie.dot

  # Render with GraphViz
  dot -Tpng output.dot -o output.png
        """,
    )

    parser.add_argument("--verbose", action="store_true", help="Show detailed progress with timing")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress progress output")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    pedigree_parser = subparsers.add_parser(
        "pedigree", help="Generate pedigree chart for an individual"
    )
    _add_common_args(pedigree_parser)
    pedigree_parser.add_argument("individual", type=str, help="Individual ID (e.g., @I10@)")
    _add_generation_args(pedigree_parser)

    relationship_parser = subparsers.add_parser(
        "relationship", help="Generate relationship chart between two individuals"
    )
    _add_common_args(relationship_parser)
    relationship_parser.add_argument("individual1", type=str, help="First individual ID")
    relationship_parser.add_argument("individual2", type=str, help="Second individual ID")
    relationship_parser.add_argument(
        "-d",
        "--max-depth",
        type=int,
        default=50,
        help="Maximum search depth (1-50, default: 50)",
    )

    hourglass_parser = subparsers.add_parser(
        "hourglass", help="Generate hourglass chart (ancestors and descendants)"
    )
    _add_common_args(hourglass_parser)
    hourglass_parser.add_argument("individual", type=str, help="Center individual ID (e.g., @I10@)")
    _add_generation_args(hourglass_parser)
    hourglass_parser.add_argument(
        "-v",
        "--variant",
        choices=["ancestor-split", "descendants"],
        default="ancestor-split",
        help="Chart variant: ancestor-split (father above, mother below) "
        "or descendants (ancestors above, descendants below)",
    )

    bowtie_parser = subparsers.add_parser(
        "bowtie", help="Generate bowtie chart (horizontal hourglass)"
    )
    _add_common_args(bowtie_parser)
    bowtie_parser.add_argument("individual", type=str, help="Center individual ID (e.g., @I10@)")
    _add_generation_args(bowtie_parser)
    bowtie_parser.add_argument(
        "-v",
        "--variant",
        choices=["ancestor-split", "descendants"],
        default="ancestor-split",
        help="Chart variant: ancestor-split (father left, mother right) "
        "or descendants (ancestors left, descendants right)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    sub = subparsers.choices[args.command]
    if hasattr(args, "generations") and not 1 <= args.generations <= 15:
        sub.error("--generations must be between 1 and 15")
    if hasattr(args, "max_depth") and not 1 <= args.max_depth <= 50:
        sub.error("--max-depth must be between 1 and 50")

    gedcom_path = Path(args.gedcom)
    if not gedcom_path.exists():
        print(f"Error: GEDCOM file not found: {args.gedcom}", file=sys.stderr)
        sys.exit(1)

    try:
        tracker = PhaseTracker(
            3,
            stream=sys.stderr,
            no_color=args.no_color,
            quiet=args.quiet,
            verbose=args.verbose,
        )

        with tracker.phase("Loading GEDCOM"):
            gp = GedcomParser(str(gedcom_path))
            gp.load()

        gen = DotGenerator(gp)

        if args.command == "pedigree":
            ind = gp.get_individual(args.individual)
            if not ind:
                sys.exit(f"Error: Individual {args.individual} not found")

            with tracker.phase("Generating pedigree"):
                dot = gen.generate_pedigree(args.individual, args.generations)
            with tracker.phase("Writing output"):
                Path(args.output).write_text(dot, encoding="utf-8")
            print(f"Pedigree: {gp.get_name(ind)} - {args.generations} gen -> {args.output}")

        elif args.command == "relationship":
            ind1 = gp.get_individual(args.individual1)
            ind2 = gp.get_individual(args.individual2)
            if not ind1:
                sys.exit(f"Error: Individual {args.individual1} not found")
            if not ind2:
                sys.exit(f"Error: Individual {args.individual2} not found")

            with tracker.phase("Finding relationship"):
                pf = PathFinder(gp)
                paths = pf.get_shortest_paths(args.individual1, args.individual2, args.max_depth)

            if not paths:
                id1, id2 = args.individual1, args.individual2
                sys.exit(f"Error: No relationship found between {id1} and {id2}")

            with tracker.phase("Writing output"):
                dot = gen.generate_relationship(paths)
                Path(args.output).write_text(dot, encoding="utf-8")
            name1 = gp.get_name(ind1)
            name2 = gp.get_name(ind2)
            steps = paths[0].length()
            print(f"Relationship: {name1} to {name2} ({steps} steps) -> {args.output}")

        elif args.command == "hourglass":
            ind = gp.get_individual(args.individual)
            if not ind:
                sys.exit(f"Error: Individual {args.individual} not found")

            with tracker.phase("Generating hourglass"):
                dot = gen.generate_hourglass(args.individual, args.generations, args.variant)
            with tracker.phase("Writing output"):
                Path(args.output).write_text(dot, encoding="utf-8")
            print(f"Hourglass: {gp.get_name(ind)} ({args.variant}) -> {args.output}")

        elif args.command == "bowtie":
            ind = gp.get_individual(args.individual)
            if not ind:
                sys.exit(f"Error: Individual {args.individual} not found")

            with tracker.phase("Generating bowtie"):
                dot = gen.generate_bowtie(args.individual, args.generations, args.variant)
            with tracker.phase("Writing output"):
                Path(args.output).write_text(dot, encoding="utf-8")
            print(f"Bowtie: {gp.get_name(ind)} ({args.variant}) -> {args.output}")

    except (ValueError, FileNotFoundError, KeyError, OSError, ParserError, IntegrityError) as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
