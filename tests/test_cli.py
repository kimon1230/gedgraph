"""Tests for CLI flag parsing and PhaseTracker wiring."""

import os
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gedgraph import __version__, pathfinder
from gedgraph.cli import main
from gedgraph.dotgen import COLOR_END, COLOR_FOCAL

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_GED = str(FIXTURES_DIR / "sample.ged")


def _make_tracker_mock():
    tracker = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=ctx)
    ctx.__exit__ = MagicMock(return_value=False)
    tracker.phase.return_value = ctx
    return tracker


def _run_with_mock_tracker(cli_args, tracker_mock):
    with (
        patch("sys.argv", ["gedgraph"] + cli_args),
        patch("gedgraph.cli.PhaseTracker", return_value=tracker_mock) as pt_cls,
    ):
        main()
    return pt_cls


def test_tracker_created_with_quiet(tmp_path):
    out = tmp_path / "out.dot"
    tracker = _make_tracker_mock()
    pt_cls = _run_with_mock_tracker(
        ["--quiet", "pedigree", SAMPLE_GED, "@I7@", "-o", str(out)],
        tracker,
    )
    assert pt_cls.call_args[1]["quiet"] is True


def test_tracker_created_with_verbose(tmp_path):
    out = tmp_path / "out.dot"
    tracker = _make_tracker_mock()
    pt_cls = _run_with_mock_tracker(
        ["--verbose", "pedigree", SAMPLE_GED, "@I7@", "-o", str(out)],
        tracker,
    )
    assert pt_cls.call_args[1]["verbose"] is True


def test_tracker_created_with_no_color(tmp_path):
    out = tmp_path / "out.dot"
    tracker = _make_tracker_mock()
    pt_cls = _run_with_mock_tracker(
        ["--no-color", "pedigree", SAMPLE_GED, "@I7@", "-o", str(out)],
        tracker,
    )
    assert pt_cls.call_args[1]["no_color"] is True


def test_tracker_stream_is_stderr(tmp_path):
    out = tmp_path / "out.dot"
    tracker = _make_tracker_mock()
    pt_cls = _run_with_mock_tracker(
        ["pedigree", SAMPLE_GED, "@I7@", "-o", str(out)],
        tracker,
    )
    assert pt_cls.call_args[1]["stream"] is sys.stderr


def test_pedigree_phase_names(tmp_path):
    out = tmp_path / "out.dot"
    tracker = _make_tracker_mock()
    _run_with_mock_tracker(
        ["pedigree", SAMPLE_GED, "@I7@", "-o", str(out)],
        tracker,
    )
    phase_names = [call.args[0] for call in tracker.phase.call_args_list]
    assert phase_names == ["Loading GEDCOM", "Generating pedigree", "Writing output"]


def test_relationship_phase_names(tmp_path):
    out = tmp_path / "out.dot"
    tracker = _make_tracker_mock()
    _run_with_mock_tracker(
        ["relationship", SAMPLE_GED, "@I1@", "@I3@", "-o", str(out)],
        tracker,
    )
    phase_names = [call.args[0] for call in tracker.phase.call_args_list]
    assert phase_names == ["Loading GEDCOM", "Finding relationship", "Writing output"]


@pytest.mark.parametrize(
    ("ids", "summary"),
    [
        (["@I7@", "@I8@"], "Emily Smith is David Smith's sister (2 steps)"),
        (["@I1@", "@I1@"], "John Smith and John Smith are the same person"),
    ],
)
def test_relationship_summary_line(tmp_path, capsys, ids, summary):
    out = tmp_path / "out.dot"
    with patch("sys.argv", ["gedgraph", "-q", "relationship", SAMPLE_GED, *ids, "-o", str(out)]):
        main()
    assert capsys.readouterr().out == f"Relationship: {summary} -> {out}\n"


def test_relationship_search_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(pathfinder, "_MAX_NODES", 0)
    ged = str(FIXTURES_DIR / "links.ged")
    argv = ["gedgraph", "-q", "relationship", ged, "@H7@", "@H8@", "-o", str(tmp_path / "o.dot")]
    with patch("sys.argv", argv), pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == "Error: search limit reached looking for @H7@ -> @H8@"


def test_relationship_spouse_past_search_limit_is_flagged(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(pathfinder, "_MAX_NODES", 0)
    ged = str(FIXTURES_DIR / "links.ged")
    out = tmp_path / "o.dot"
    argv = ["gedgraph", "-q", "relationship", ged, "@H7@", "@W7@", "-o", str(out)]
    with patch("sys.argv", argv):
        main()
    assert capsys.readouterr().out.endswith(
        " (search limit reached; a blood relationship may have been missed) -> " + f"{out}\n"
    )


@pytest.mark.parametrize("pair", [["@NOPE@", "@I1@"], ["@I1@", "@NOPE@"]])
def test_relationship_unknown_individual(tmp_path, pair):
    argv = ["gedgraph", "-q", "relationship", SAMPLE_GED, *pair, "-o"]
    with patch("sys.argv", [*argv, str(tmp_path / "o.dot")]), pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == "Error: Individual @NOPE@ not found"


def test_relationship_not_found(tmp_path):
    argv = ["gedgraph", "-q", "relationship", SAMPLE_GED, "@I1@", "@I10@", "-o"]
    with patch("sys.argv", [*argv, str(tmp_path / "o.dot")]), pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == "Error: No relationship found between @I1@ and @I10@"


def test_relationship_max_depth_reached(tmp_path):
    ged = FIXTURES_DIR / "cousins.ged"
    argv = ["gedgraph", "-q", "relationship", str(ged), "@A@", "@B@", "-d", "3", "-o"]
    with patch("sys.argv", [*argv, str(tmp_path / "o.dot")]), pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == "Error: --max-depth 3 reached looking for @A@ -> @B@"


def test_relationship_spouse_past_max_depth_is_flagged(tmp_path, capsys):
    ged = FIXTURES_DIR / "cousins.ged"
    out = tmp_path / "o.dot"
    argv = ["gedgraph", "-q", "relationship", str(ged), "@A@", "@S@", "-d", "3", "-o", str(out)]
    with patch("sys.argv", argv):
        main()
    summary = (
        "Sue X is Al X's partner (1 step) "
        "(--max-depth reached; a blood relationship may have been missed)"
    )
    assert capsys.readouterr().out == f"Relationship: {summary} -> {out}\n"
    # The chart must not state as fact what the summary line hedges.
    assert f"  // {summary}\n" in out.read_text(encoding="utf-8")


def test_relationship_accepts_ids_without_at_signs(tmp_path):
    """Jennifer is Michael's partner: one marriage edge, each person drawn once."""
    out = tmp_path / "out.dot"
    with patch(
        "sys.argv", ["gedgraph", "-q", "relationship", SAMPLE_GED, "I6", "I5", "-o", str(out)]
    ):
        main()
    dot = out.read_text(encoding="utf-8")
    fills = {}
    for line in dot.splitlines():
        if "[label=" in line:
            node_id = line.split()[0]
            assert node_id not in fills
            fills[node_id] = line.rsplit("fillcolor=", 1)[1].rstrip("];")
    assert fills == {"I6": COLOR_FOCAL, "I5": COLOR_END}
    assert dot.count(" -> ") == 1
    assert "  I6 -> I5 [dir=none, style=dashed, constraint=false];" in dot


ESCAPE_GED = (
    "0 HEAD\n1 CHAR UTF-8\n"
    "0 @I1@ INDI\n1 NAME Evil\x1b]0;pwned\x07\x1b[2J\x9b31m /X/\n1 FAMS @F1@\n"
    "0 @I2@ INDI\n1 NAME Kid /X/\n1 FAMC @F1@\n"
    "0 @F1@ FAM\n1 HUSB @I1@\n1 CHIL @I2@\n"
    "0 TRLR\n"
)


@pytest.mark.parametrize(
    "command",
    [
        ["pedigree", "@I1@"],
        ["relationship", "@I1@", "@I2@"],
        ["hourglass", "@I1@"],
        ["bowtie", "@I1@"],
    ],
)
def test_summary_line_strips_terminal_control_codes(tmp_path, capsys, command):
    ged = tmp_path / "escape.ged"
    ged.write_text(ESCAPE_GED, encoding="utf-8")
    out = tmp_path / "out.dot"
    with patch("sys.argv", ["gedgraph", "-q", command[0], str(ged), *command[1:], "-o", str(out)]):
        main()
    stdout = capsys.readouterr().out
    assert "Evil]0;pwned[2J31m" in stdout
    assert not any(c in stdout for c in "\x1b\x07\x9b")


def test_parse_error_strips_terminal_control_codes(tmp_path):
    ged = tmp_path / "broken.ged"
    ged.write_text(
        "0 HEAD\n1 CHAR UTF-8\nGARBAGE \x1b]0;pwned\x07\x1b[2J\n0 TRLR\n", encoding="utf-8"
    )
    argv = ["gedgraph", "-q", "pedigree", str(ged), "@I1@", "-o", str(tmp_path / "out.dot")]
    with patch("sys.argv", argv), pytest.raises(SystemExit) as exc:
        main()
    message = str(exc.value.code)
    assert message.startswith("Error: ")
    assert "GARBAGE" in message
    assert not any(c in message for c in "\x1b\x07")


@pytest.mark.parametrize("alias", ["dotted", "hardlink"])
def test_output_aliasing_input_is_refused(tmp_path, capsys, alias):
    ged = tmp_path / "in.ged"
    shutil.copy(SAMPLE_GED, ged)
    original = ged.read_bytes()
    if alias == "hardlink":
        out = tmp_path / "link.ged"
        os.link(ged, out)
    else:
        out = f"{tmp_path}{os.sep}.{os.sep}in.ged"
    argv = ["gedgraph", "-q", "pedigree", str(ged), "@I1@", "-o", str(out)]
    with patch("sys.argv", argv), pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "must not be the input GEDCOM file" in capsys.readouterr().err
    assert ged.read_bytes() == original


def test_output_to_new_file_is_written(tmp_path):
    out = tmp_path / "new" / "out.dot"
    out.parent.mkdir()
    assert not out.exists()
    with patch("sys.argv", ["gedgraph", "-q", "pedigree", SAMPLE_GED, "@I1@", "-o", str(out)]):
        main()
    assert out.read_text(encoding="utf-8").startswith("digraph Pedigree {")


def test_version_flag(capsys):
    with patch("sys.argv", ["gedgraph", "--version"]), pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    assert capsys.readouterr().out == f"gedgraph {__version__}\n"


RESTRICTED_GED = (
    "0 HEAD\n1 CHAR UTF-8\n"
    "0 @P@ INDI\n1 NAME Secret /Parent/\n1 SEX M\n1 RESN privacy\n1 BIRT\n2 DATE 1985\n"
    "1 FAMS @F1@\n"
    "0 @C@ INDI\n1 NAME Kid /Parent/\n1 FAMC @F1@\n"
    "0 @F1@ FAM\n1 HUSB @P@\n1 CHIL @C@\n"
    "0 TRLR\n"
)


@pytest.mark.parametrize(
    ("flag", "name", "label"),
    [
        ([], "Private", '"Private"'),
        (["--include-private"], "Secret Parent", '"Secret Parent\\n(1985 - )"'),
    ],
)
def test_restricted_people_are_private_by_default(tmp_path, capsys, flag, name, label):
    ged = tmp_path / "resn.ged"
    ged.write_text(RESTRICTED_GED, encoding="utf-8")
    out = tmp_path / "o.dot"
    argv = ["gedgraph", "-q", "relationship", str(ged), "@C@", "@P@", "-o", str(out), *flag]
    with patch("sys.argv", argv):
        main()
    dot = out.read_text(encoding="utf-8")
    assert f"P [label={label}" in dot
    # A private person's sex is hidden too: parent, not father.
    term = "parent" if name == "Private" else "father"
    assert f"// {name} is Kid Parent's {term} (1 step)" in dot
    assert capsys.readouterr().out.startswith(f"Relationship: {name} is Kid Parent's {term}")


@pytest.mark.skipif(os.name != "posix", reason="a 300-byte name is valid on some Windows setups")
@pytest.mark.parametrize("which", ["gedcom", "output"])
def test_overlong_path_is_a_one_line_error(tmp_path, which):
    long = str(tmp_path / ("a" * 300))
    ged, out = (long, str(tmp_path / "o.dot")) if which == "gedcom" else (SAMPLE_GED, long)
    argv = ["gedgraph", "-q", "pedigree", ged, "@I1@", "-o", out]
    with patch("sys.argv", argv), pytest.raises(SystemExit) as exc:
        main()
    message = str(exc.value.code)
    assert message.startswith("Error: ")
    assert "too long" in message


@pytest.mark.skipif(os.name != "posix", reason="file modes")
def test_output_is_owner_only_and_leaves_no_temp_file(tmp_path):
    out = tmp_path / "o.dot"
    out.write_text("old chart", encoding="utf-8")
    with patch("sys.argv", ["gedgraph", "-q", "pedigree", SAMPLE_GED, "@I1@", "-o", str(out)]):
        main()
    assert out.read_text(encoding="utf-8").startswith("digraph Pedigree")
    assert (out.stat().st_mode & 0o777) == 0o600
    assert sorted(p.name for p in tmp_path.iterdir()) == ["o.dot"]


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="symlinks and FIFOs")
@pytest.mark.parametrize("kind", ["symlink", "fifo", "symlink to fifo", "device"])
def test_output_refuses_links_and_devices(tmp_path, capsys, kind):
    victim = tmp_path / "victim.txt"
    victim.write_text("keep me", encoding="utf-8")
    out = tmp_path / "o.dot"
    if kind == "symlink":
        out.symlink_to(victim)
    elif kind == "fifo":
        os.mkfifo(out)
    elif kind == "symlink to fifo":
        os.mkfifo(tmp_path / "fifo")
        out.symlink_to(tmp_path / "fifo")
    else:
        out = Path(os.devnull)
    argv = ["gedgraph", "-q", "pedigree", SAMPLE_GED, "@I1@", "-o", str(out)]
    with patch("sys.argv", argv), pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "--output must be a regular file, not a link or device" in capsys.readouterr().err
    assert victim.read_text(encoding="utf-8") == "keep me"


@pytest.mark.skipif(not Path("/proc/self/fd").is_dir(), reason="/proc")
def test_output_cannot_reach_the_open_input_through_proc(tmp_path):
    """The GEDCOM is open while the chart is written. Its /proc fd path must never be
    written through, whether main() refuses it or the temporary file cannot be made."""
    ged = tmp_path / "victim.ged"
    ged.write_bytes(Path(SAMPLE_GED).read_bytes())
    for fd in range(3, 8):
        argv = ["gedgraph", "-q", "pedigree", str(ged), "@I1@", "-o", f"/proc/self/fd/{fd}"]
        with patch("sys.argv", argv), pytest.raises(SystemExit):
            main()
    assert ged.read_bytes() == Path(SAMPLE_GED).read_bytes()


def test_failed_write_keeps_the_old_file(tmp_path):
    out = tmp_path / "o.dot"
    out.write_text("old chart", encoding="utf-8")
    argv = ["gedgraph", "-q", "pedigree", SAMPLE_GED, "@I1@", "-o", str(out)]
    disk_full = patch("gedgraph.cli.os.fdopen", side_effect=OSError("disk full"))
    with patch("sys.argv", argv), disk_full, pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == "Error: disk full"
    assert out.read_text(encoding="utf-8") == "old chart"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["o.dot"]


@pytest.mark.skipif(os.name != "posix", reason="255-byte name limit")
def test_output_name_near_the_limit(tmp_path):
    out = tmp_path / ("a" * 250 + ".dot")
    with patch("sys.argv", ["gedgraph", "-q", "pedigree", SAMPLE_GED, "@I1@", "-o", str(out)]):
        main()
    assert out.read_text(encoding="utf-8").startswith("digraph Pedigree")
