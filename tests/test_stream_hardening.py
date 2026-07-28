"""Tests for stdout/stderr hardening against non-ASCII output.

The bug these guard: on Windows a redirected stream defaults to the ANSI
codepage, so printing a Greek name raised UnicodeEncodeError. The tool worked
interactively and died under `> out.txt`.
"""

import contextlib
import io
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from gedgraph import cli
from gedgraph.cli import _harden_streams, main

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GREEK_GED = str(FIXTURES_DIR / "non_ascii_names.ged")
SURNAME = "Ανδρέου"


@pytest.fixture(autouse=True)
def _reset_hardening(monkeypatch):
    monkeypatch.setattr(cli, "_hardened_streams", set())
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)


def _double(encoding="cp1252", errors="strict"):
    """Stand-in for a real interpreter stream.

    write_through because a double whose flush() raises otherwise leaves its
    pending text unwritten, and content assertions would read "". newline=""
    keeps these tests about encoding -- without it Windows translates \\n to
    \\r\\n on write and the byte comparisons drift.
    """
    return io.TextIOWrapper(
        io.BytesIO(), encoding=encoding, errors=errors, newline="", write_through=True
    )


def _flush_raises(exc):
    """A double whose flush() always raises.

    Deliberately utf-8: reconfigure() calls the Python-level flush(), so
    _harden_streams skips this stream entirely. Built with cp1252 it would fail
    at print() instead and never reach the flush under test.
    """

    class Double(io.TextIOWrapper):
        def flush(self):
            raise exc

    return Double(io.BytesIO(), encoding="utf-8", newline="", write_through=True)


def _write_raises(exc):
    class Double(io.TextIOWrapper):
        def write(self, _text):
            raise exc

    return Double(io.BytesIO(), encoding="utf-8", newline="", write_through=True)


class _FakeTty:
    """A TTY-reporting stream that records how it was reconfigured.

    TextIOWrapper.isatty() delegates to its buffer, so a BytesIO-backed wrapper
    can never report True.
    """

    encoding = "cp1252"
    errors = "strict"

    def __init__(self):
        self.calls = []

    def isatty(self):
        return True

    def reconfigure(self, **kwargs):
        self.calls.append(kwargs)


def _install(monkeypatch, stdout, stderr=None):
    """Install doubles as both sys.X and sys.__X__.

    Patching only sys.stdout would trip the identity guard and the stream would
    be skipped, making every assertion below pass vacuously.
    """
    stderr = _double() if stderr is None else stderr
    for name, stream in (("stdout", stdout), ("stderr", stderr)):
        monkeypatch.setattr(sys, name, stream)
        monkeypatch.setattr(sys, f"__{name}__", stream)
    return stdout, stderr


def _decode(double):
    if double is None:
        return ""
    with contextlib.suppress(Exception):
        double.flush()  # write_through keeps the buffer populated anyway
    return double.buffer.getvalue().decode(double.encoding, errors="replace")


def _run_cli(args, out_double, err_double):
    """Run main() and collect (code, stdout, stderr).

    main() returns normally on success, so code is None there; sys.exit(str)
    puts its message in code rather than on either stream.
    """
    code = None
    try:
        with patch("sys.argv", ["gedgraph"] + args):
            main()
    except SystemExit as exc:
        code = exc.code
    return code, _decode(out_double), _decode(err_double)


class TestReconfiguration:
    def test_redirected_stream_becomes_utf8(self, monkeypatch):
        out, _ = _install(monkeypatch, _double())
        _harden_streams()
        assert out.encoding == "utf-8"
        # reconfigure(encoding=...) resets errors to strict unless passed together
        assert out.errors == "backslashreplace"

    def test_redirected_stream_round_trips_non_ascii(self, monkeypatch):
        out, _ = _install(monkeypatch, _double())
        _harden_streams()
        out.write("Ανδρέου → Müller ✓\n")
        assert out.buffer.getvalue().decode("utf-8") == "Ανδρέου → Müller ✓\n"

    def test_tty_keeps_encoding_and_only_gains_error_handler(self, monkeypatch):
        tty = _FakeTty()
        _install(monkeypatch, tty)
        _harden_streams()
        assert tty.calls == [{"errors": "backslashreplace"}]

    def test_both_streams_are_hardened(self, monkeypatch):
        out, err = _install(monkeypatch, _double(), _double())
        _harden_streams()
        assert out.encoding == "utf-8"
        assert err.encoding == "utf-8"


class TestSkippedStreams:
    def test_stream_without_reconfigure_is_skipped(self, monkeypatch):
        _install(monkeypatch, io.StringIO())
        _harden_streams()  # must not raise

    def test_stream_whose_reconfigure_raises_is_skipped(self, monkeypatch):
        class Hostile(_FakeTty):
            def reconfigure(self, **_kwargs):
                raise ValueError("detached buffer")

        _install(monkeypatch, Hostile())
        _harden_streams()
        assert "stdout" not in cli._hardened_streams

    def test_none_stream_is_skipped(self, monkeypatch):
        monkeypatch.setattr(sys, "stdout", None)
        monkeypatch.setattr(sys, "__stdout__", None)
        _harden_streams()

    def test_substituted_stream_is_left_alone(self, monkeypatch):
        """pytest's CaptureIO is a TextIOWrapper subclass with a working
        reconfigure(); without the identity guard it would be mutated."""
        substitute = _double()
        monkeypatch.setattr(sys, "__stdout__", _double())
        monkeypatch.setattr(sys, "stdout", substitute)
        monkeypatch.setattr(sys, "stderr", _double())
        monkeypatch.setattr(sys, "__stderr__", _double())
        _harden_streams()
        assert substitute.encoding == "cp1252"

    def test_substituted_stream_left_alone_when_original_is_none(self, monkeypatch):
        substitute = _double()
        monkeypatch.setattr(sys, "__stdout__", None)
        monkeypatch.setattr(sys, "stdout", substitute)
        monkeypatch.setattr(sys, "stderr", _double())
        monkeypatch.setattr(sys, "__stderr__", _double())
        _harden_streams()
        assert substitute.encoding == "cp1252"


class TestPythonIoEncoding:
    def test_named_encoding_is_kept_and_gains_handler(self, monkeypatch):
        monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
        out, _ = _install(monkeypatch, _double())
        _harden_streams()
        assert out.encoding == "cp1252"
        assert out.errors == "backslashreplace"

    def test_explicit_handler_is_untouched(self, monkeypatch):
        monkeypatch.setenv("PYTHONIOENCODING", "cp1252:strict")
        out, _ = _install(monkeypatch, _double())
        _harden_streams()
        assert out.encoding == "cp1252"
        assert out.errors == "strict"

    def test_trailing_colon_still_hardens(self, monkeypatch):
        """`cp1252:` names no handler, so errors stay strict and the original
        crash survives -- matching on the bare separator would skip it."""
        monkeypatch.setenv("PYTHONIOENCODING", "cp1252:")
        out, _ = _install(monkeypatch, _double())
        _harden_streams()
        assert out.encoding == "cp1252"
        assert out.errors == "backslashreplace"

    def test_empty_encoding_with_handler_is_untouched(self, monkeypatch):
        monkeypatch.setenv("PYTHONIOENCODING", ":backslashreplace")
        out, _ = _install(monkeypatch, _double())
        _harden_streams()
        assert out.encoding == "cp1252"
        assert out.errors == "strict"


class TestLatching:
    def test_hardening_is_idempotent(self, monkeypatch):
        tty = _FakeTty()
        _install(monkeypatch, tty)
        _harden_streams()
        _harden_streams()
        assert len(tty.calls) == 1

    def test_skipped_streams_are_not_latched(self, monkeypatch):
        """A call that hardened nothing must not disable a later valid one."""
        _install(monkeypatch, io.StringIO(), io.StringIO())
        _harden_streams()
        assert cli._hardened_streams == set()

        out, _ = _install(monkeypatch, _double(), _double())
        _harden_streams()
        assert out.encoding == "utf-8"

    def test_stderr_not_locked_out_by_stdout(self, monkeypatch):
        """A single process-wide flag would latch after stdout and leave stderr
        -- where the spinner glyphs go -- unhardened forever."""
        _install(monkeypatch, _double(), io.StringIO())
        _harden_streams()
        assert cli._hardened_streams == {"stdout"}

        err = _double()
        monkeypatch.setattr(sys, "stderr", err)
        monkeypatch.setattr(sys, "__stderr__", err)
        _harden_streams()
        assert err.encoding == "utf-8"


class TestCliErrorPaths:
    def test_encode_failure_names_the_encoding(self, monkeypatch, tmp_path):
        """Must not be reported as a parse error by the broad ValueError clause."""
        exc = UnicodeEncodeError("cp1252", "Ανδρέου", 0, 1, "mock")
        out, err = _install(monkeypatch, _write_raises(exc))
        code, _, _ = _run_cli(
            ["-q", "pedigree", GREEK_GED, "@I1@", "-o", str(tmp_path / "o.dot")], out, err
        )
        assert isinstance(code, str)
        assert "cannot represent" in code

    def test_flush_failure_is_distinguishable(self, monkeypatch, tmp_path):
        """A post-write failure must not look like a generation failure."""
        out, err = _install(monkeypatch, _flush_raises(OSError("disk full")))
        code, _, _ = _run_cli(
            ["-q", "pedigree", GREEK_GED, "@I1@", "-o", str(tmp_path / "o.dot")], out, err
        )
        assert isinstance(code, str)
        assert "failed to flush stdout" in code

    def test_none_stdout_completes(self, monkeypatch, tmp_path):
        """pythonw: print() is a no-op but a bare flush() would AttributeError."""
        err = _double()
        monkeypatch.setattr(sys, "stdout", None)
        monkeypatch.setattr(sys, "__stdout__", None)
        monkeypatch.setattr(sys, "stderr", err)
        monkeypatch.setattr(sys, "__stderr__", err)
        out_path = tmp_path / "o.dot"
        code, _, _ = _run_cli(["-q", "pedigree", GREEK_GED, "@I1@", "-o", str(out_path)], None, err)
        assert code is None
        assert out_path.exists()


class TestEndToEnd:
    @pytest.mark.parametrize(
        ("command", "extra"),
        [
            ("pedigree", ["@I1@"]),
            ("hourglass", ["@I1@"]),
            ("bowtie", ["@I1@"]),
            ("relationship", ["@I1@", "@I5@"]),
        ],
    )
    def test_redirected_run_preserves_greek(self, monkeypatch, tmp_path, command, extra):
        out, err = _install(monkeypatch, _double())
        code, text, _ = _run_cli(
            ["-q", command, GREEK_GED, *extra, "-o", str(tmp_path / "o.dot")], out, err
        )
        assert code is None
        assert SURNAME in text

    def test_legacy_codepage_degrades_to_ascii(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
        out, err = _install(monkeypatch, _double())
        code, text, _ = _run_cli(
            ["-q", "pedigree", GREEK_GED, "@I1@", "-o", str(tmp_path / "o.dot")], out, err
        )
        assert code is None
        text.encode("ascii")  # would raise if the escaping had not happened
        assert "\\u0391" in text
