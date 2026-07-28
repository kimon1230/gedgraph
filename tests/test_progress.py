"""Tests for progress indicators."""

import io

import pytest

from gedgraph import progress
from gedgraph.progress import (
    ASCII_GLYPHS,
    UNICODE_GLYPHS,
    PhaseTracker,
    Spinner,
    _NullSpinner,
    ascii_mode,
    glyphs,
    set_ascii_mode,
)


@pytest.fixture(autouse=True)
def _reset_ascii_mode(monkeypatch):
    """Both the flag and the env vars are process-global and would leak."""
    monkeypatch.setattr(progress, "_ascii_forced", None)
    for var in ("GEDGRAPH_ASCII", "GEDCOM_TOOLS_ASCII"):
        monkeypatch.delenv(var, raising=False)


class _FakeTtyStream(io.StringIO):
    def isatty(self):
        return True


class TestGlyphSelection:
    def test_default_is_unicode(self):
        assert glyphs() is UNICODE_GLYPHS

    def test_forced_on(self):
        set_ascii_mode(True)
        assert glyphs() is ASCII_GLYPHS

    def test_forced_off_beats_environment(self, monkeypatch):
        """The whole reason the flag is tri-state: a plain boolean could not
        express "explicitly off" and --no-ascii could never win."""
        monkeypatch.setenv("GEDGRAPH_ASCII", "1")
        set_ascii_mode(False)
        assert glyphs() is UNICODE_GLYPHS

    @pytest.mark.parametrize("value", ["1", "true", "yes", "on", "anything"])
    def test_environment_enables(self, monkeypatch, value):
        monkeypatch.setenv("GEDGRAPH_ASCII", value)
        assert ascii_mode() is True

    @pytest.mark.parametrize("value", ["", "0", "false", "False", "NO", "off", " 0 "])
    def test_environment_off_values(self, monkeypatch, value):
        monkeypatch.setenv("GEDGRAPH_ASCII", value)
        assert ascii_mode() is False

    def test_vendored_variable_used_as_fallback(self, monkeypatch):
        monkeypatch.setenv("GEDCOM_TOOLS_ASCII", "1")
        assert ascii_mode() is True

    def test_own_variable_wins_over_vendored(self, monkeypatch):
        monkeypatch.setenv("GEDGRAPH_ASCII", "0")
        monkeypatch.setenv("GEDCOM_TOOLS_ASCII", "1")
        assert ascii_mode() is False


class TestSpinnerGlyphs:
    def test_stop_uses_unicode_check(self):
        stream = io.StringIO()
        Spinner("Working", stream=stream).stop(success=True)
        assert UNICODE_GLYPHS.check in stream.getvalue()

    def test_stop_uses_ascii_check(self):
        set_ascii_mode(True)
        stream = io.StringIO()
        Spinner("Working", stream=stream).stop(success=True)
        assert ASCII_GLYPHS.check in stream.getvalue()

    def test_stop_uses_ascii_cross_on_failure(self):
        set_ascii_mode(True)
        stream = io.StringIO()
        Spinner("Working", stream=stream).stop(success=False)
        assert ASCII_GLYPHS.cross in stream.getvalue()

    def test_ascii_animation_outlasts_its_frame_count(self):
        """The frame counter must be bounded by the *active* glyph set: a
        modulo over the 10 Unicode frames would IndexError on the 4 ASCII ones."""
        set_ascii_mode(True)
        spinner = Spinner("Working", stream=_FakeTtyStream())
        for _ in range(3 * len(UNICODE_GLYPHS.frames)):
            spinner._frame = (spinner._frame + 1) % len(spinner.glyphs.frames)
            spinner._render()
        assert set(spinner.stream.getvalue()) >= set(ASCII_GLYPHS.frames)

    def test_stop_survives_an_unencodable_stream(self):
        """Progress decoration is never worth failing a command over."""

        class Hostile(io.StringIO):
            def write(self, text):
                raise UnicodeEncodeError("cp1252", text, 0, 1, "mock")

        Spinner("Working", stream=Hostile()).stop(success=True)


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
