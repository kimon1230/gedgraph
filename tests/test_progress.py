"""Tests for progress indicators."""

import io

from gedgraph.progress import PhaseTracker, _NullSpinner


class TestPhaseTracker:
    def test_phase_tracker_increments(self):
        stream = io.StringIO()
        tracker = PhaseTracker(3, stream=stream)

        with tracker.phase("First"):
            pass
        with tracker.phase("Second"):
            pass
        with tracker.phase("Third"):
            pass

        output = stream.getvalue()
        assert "[1/3]" in output
        assert "[2/3]" in output
        assert "[3/3]" in output

    def test_phase_tracker_quiet_mode(self):
        stream = io.StringIO()
        tracker = PhaseTracker(2, stream=stream, quiet=True)

        with tracker.phase("First"):
            pass
        with tracker.phase("Second"):
            pass

        assert stream.getvalue() == ""

    def test_phase_returns_null_spinner_when_quiet(self):
        tracker = PhaseTracker(1, quiet=True)
        assert isinstance(tracker.phase("Test"), _NullSpinner)
