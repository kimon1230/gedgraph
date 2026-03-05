"""Tests for CLI flag parsing and PhaseTracker wiring."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from gedgraph.cli import main

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
