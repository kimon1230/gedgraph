import argparse
import os
import sys
import tempfile
from pathlib import Path

from ged4py.parser import IntegrityError, ParserError

from . import __version__
from .dotgen import DotGenerator, strip_control
from .kinship import describe, sentence
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
    parser.add_argument(
        "--include-private",
        action="store_true",
        help="Show people and events the file marks RESN privacy or confidential "
        "(shown as Private, without years, by default)",
    )


def _write_output(path: str, text: str) -> None:
    """Write through a temporary file and a rename.

    main() has refused a symlink or device at the path; one planted since is
    replaced, never followed, and a failed write leaves the old file whole. The
    new file is readable by its owner only: it holds names and dates of real
    people.
    """
    out = Path(path)
    # A fixed prefix: one built from the output's name could push a legal name
    # past the file system's limit.
    fd, tmp = tempfile.mkstemp(dir=out.parent, prefix=".gedgraph-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        Path(tmp).replace(out)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _add_generation_args(parser: argparse.ArgumentParser) -> None:
    """Add -g/--generations, shared by pedigree, hourglass, and bowtie."""
    parser.add_argument(
        "-g",
        "--generations",
        type=int,
        default=4,
        help="Number of generations (1-15, default: 4). Cost doubles per generation.",
    )


def _build_arg_parser() -> tuple[argparse.ArgumentParser, dict[str, argparse.ArgumentParser]]:
    """Return the top-level parser and the subcommand parsers keyed by name."""
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

    parser.add_argument("--version", action="version", version=f"gedgraph {__version__}")
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

    return parser, dict(subparsers.choices)


def _chart(
    gp: GedcomParser, gen: DotGenerator, tracker: PhaseTracker, args: argparse.Namespace
) -> None:
    """Write a pedigree, hourglass, or bowtie chart and print its summary line."""
    ind = gp.get_individual(args.individual)
    if not ind:
        sys.exit(f"Error: Individual {args.individual} not found")

    with tracker.phase(f"Generating {args.command}"):
        if args.command == "pedigree":
            dot = gen.generate_pedigree(args.individual, args.generations)
        elif args.command == "hourglass":
            dot = gen.generate_hourglass(args.individual, args.generations, args.variant)
        else:
            dot = gen.generate_bowtie(args.individual, args.generations, args.variant)
    with tracker.phase("Writing output"):
        _write_output(args.output, dot)

    name = strip_control(gp.get_name(ind))
    if args.command == "pedigree":
        print(f"Pedigree: {name} - {args.generations} gen -> {args.output}")
    else:
        print(f"{args.command.capitalize()}: {name} ({args.variant}) -> {args.output}")


def _relationship(
    gp: GedcomParser, gen: DotGenerator, tracker: PhaseTracker, args: argparse.Namespace
) -> None:
    """Write the relationship chart and print a kinship summary line."""
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
        if pf.truncated:
            sys.exit(f"Error: search limit reached looking for {id1} -> {id2}")
        if pf.depth_limited:
            sys.exit(f"Error: --max-depth {args.max_depth} reached looking for {id1} -> {id2}")
        sys.exit(f"Error: No relationship found between {id1} and {id2}")

    name1 = strip_control(gp.get_name(ind1))
    name2 = strip_control(gp.get_name(ind2))
    term = describe(paths[0], gp)
    summary = sentence(name1, name2, term, paths[0].length())
    if pf.truncated:
        summary += " (search limit reached; a blood relationship may have been missed)"
    elif pf.depth_limited:
        summary += " (--max-depth reached; a blood relationship may have been missed)"

    with tracker.phase("Writing output"):
        dot = gen.generate_relationship(paths, summary)
        _write_output(args.output, dot)
    print(f"Relationship: {summary} -> {args.output}")


def main() -> None:
    # Before the parser: argparse writes --help and usage errors from inside
    # parse_args() and then exits.
    _harden_streams()

    parser, subcommands = _build_arg_parser()
    args = parser.parse_args()

    if args.ascii is not None:
        set_ascii_mode(args.ascii)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    sub = subcommands[args.command]
    if hasattr(args, "generations") and not 1 <= args.generations <= 15:
        sub.error("--generations must be between 1 and 15")
    if hasattr(args, "max_depth") and not 1 <= args.max_depth <= 50:
        sub.error("--max-depth must be between 1 and 50")

    gedcom_path = Path(args.gedcom)
    out = Path(args.output)
    try:
        found = gedcom_path.exists()
        same = found and out.exists() and out.samefile(gedcom_path)
        # /dev/stdout, a FIFO, a link someone left in a shared directory: the
        # chart would go wherever it points. (Under -o /dev/stdout the summary
        # line shares the stream, so the DOT was never usable that way.)
        special = out.is_symlink() or (out.exists() and not out.is_file())
    except OSError as e:
        # A name too long for the file system, say: one line, not a traceback.
        sys.exit(f"Error: {strip_control(str(e))}")
    if not found:
        print(f"Error: GEDCOM file not found: {args.gedcom}", file=sys.stderr)
        sys.exit(1)
    if same:
        sub.error("--output must not be the input GEDCOM file")
    if special:
        sub.error("--output must be a regular file, not a link or device")

    gp = GedcomParser(str(gedcom_path), include_private=args.include_private)
    try:
        tracker = PhaseTracker(
            3,
            stream=sys.stderr,
            no_color=args.no_color,
            quiet=args.quiet,
            verbose=args.verbose,
        )

        with tracker.phase("Loading GEDCOM"):
            gp.load()

        gen = DotGenerator(gp)

        if args.command == "relationship":
            _relationship(gp, gen, tracker, args)
        else:
            _chart(gp, gen, tracker, args)

        if sys.stdout is not None:
            try:
                sys.stdout.flush()
            except OSError as e:
                sys.exit(f"Error: wrote {args.output} but failed to flush stdout: {e}")

    except UnicodeEncodeError as e:
        # Must precede the ValueError clause below: UnicodeEncodeError is a
        # subclass and would otherwise be reported as a parse error.
        enc = getattr(sys.stdout, "encoding", None) or "unknown"
        sys.exit(
            f"Error: output encoding ({enc}) cannot represent this text: {strip_control(str(e))}"
        )
    except (ValueError, FileNotFoundError, OSError, ParserError, IntegrityError) as e:
        # ged4py's ParserError quotes the offending GEDCOM line verbatim.
        sys.exit(f"Error: {strip_control(str(e))}")
    finally:
        gp.close()


if __name__ == "__main__":
    main()
