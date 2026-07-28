import argparse
import os
import sys
from pathlib import Path

from ged4py.parser import IntegrityError, ParserError

from .dotgen import DotGenerator
from .parser import GedcomParser
from .pathfinder import PathFinder
from .progress import PhaseTracker, set_ascii_mode

_hardened_streams: set[str] = set()


def _harden_streams() -> None:
    """Make stdout/stderr survive non-ASCII names on legacy codepages.

    Windows picks the ANSI codepage for a redirected stream, so writing a Greek
    or accented name raises UnicodeEncodeError. The tool works interactively and
    dies under `> out.txt`, which is the worst way for it to fail.

    Redirected streams get UTF-8: there is no terminal on the other end whose
    codepage we owe anything to. A real terminal keeps its encoding, because
    forcing UTF-8 onto a cp1252 console produces mojibake; it only gains the
    error handler, which changes nothing except for characters that would
    otherwise raise.

    Call once, before any thread writes to the streams -- reconfigure() is not
    safe to call concurrently with a write, and Spinner animates on stderr.
    """
    io_encoding = os.environ.get("PYTHONIOENCODING", "")
    _, _, handler = io_encoding.partition(":")
    if handler:
        # User named their own error handler; leave both streams alone.
        return

    for name in ("stdout", "stderr"):
        if name in _hardened_streams:
            continue
        stream = getattr(sys, name)
        # Only touch the real interpreter streams: pytest's CaptureIO is a
        # TextIOWrapper subclass and would otherwise be mutated session-wide.
        if stream is None or stream is not getattr(sys, f"__{name}__"):
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            if stream.isatty() or io_encoding:
                reconfigure(errors="backslashreplace")
            else:
                # reconfigure() resets errors to strict unless passed together.
                reconfigure(encoding="utf-8", errors="backslashreplace")
        except (ValueError, OSError):
            continue
        _hardened_streams.add(name)


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
    # Before the parser: argparse writes --help and usage errors from inside
    # parse_args() and then exits.
    _harden_streams()

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
    parser.add_argument(
        "--ascii",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Use ASCII-only decorations, for consoles lacking the glyph fonts "
        "(must come before the subcommand)",
    )

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

    if args.ascii is not None:
        set_ascii_mode(args.ascii)

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

        if sys.stdout is not None:
            try:
                sys.stdout.flush()
            except OSError as e:
                sys.exit(f"Error: wrote {args.output} but failed to flush stdout: {e}")

    except UnicodeEncodeError as e:
        # Must precede the ValueError clause below -- UnicodeEncodeError is a
        # subclass, and reporting it as a parse error is what made the original
        # failure so hard to place.
        enc = getattr(sys.stdout, "encoding", None) or "unknown"
        sys.exit(f"Error: output encoding ({enc}) cannot represent this text: {e}")
    except (ValueError, FileNotFoundError, KeyError, OSError, ParserError, IntegrityError) as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
