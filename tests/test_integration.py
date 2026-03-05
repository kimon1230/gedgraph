"""Integration tests for GedGraph."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def sample_gedcom_path():
    """Get path to sample GEDCOM file."""
    return Path(__file__).parent / "fixtures" / "sample.ged"


@pytest.fixture
def python_cmd():
    """Get Python executable path."""
    return sys.executable


def test_cli_pedigree(sample_gedcom_path, python_cmd, tmp_path):
    """Test CLI pedigree command."""
    output_path = str(tmp_path / "output.dot")

    result = subprocess.run(
        [
            python_cmd,
            "-m",
            "gedgraph",
            "pedigree",
            str(sample_gedcom_path),
            "@I7@",
            "-o",
            output_path,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Pedigree:" in result.stdout

    with open(output_path) as f:
        content = f.read()
        assert "digraph Pedigree" in content
        assert "David Smith" in content


def test_cli_relationship(sample_gedcom_path, python_cmd, tmp_path):
    """Test CLI relationship command."""
    output_path = str(tmp_path / "output.dot")

    result = subprocess.run(
        [
            python_cmd,
            "-m",
            "gedgraph",
            "relationship",
            str(sample_gedcom_path),
            "@I1@",
            "@I7@",
            "-o",
            output_path,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Relationship:" in result.stdout
    assert "3 steps" in result.stdout

    with open(output_path) as f:
        content = f.read()
        assert "digraph Relationship" in content
        assert "John Smith" in content
        assert "David Smith" in content


def test_cli_no_relationship(sample_gedcom_path, python_cmd, tmp_path):
    """Test CLI when no relationship exists."""
    output_path = str(tmp_path / "output.dot")

    result = subprocess.run(
        [
            python_cmd,
            "-m",
            "gedgraph",
            "relationship",
            str(sample_gedcom_path),
            "@I1@",
            "@I10@",
            "-o",
            output_path,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "No relationship found" in result.stderr


def test_cli_invalid_individual(sample_gedcom_path, python_cmd, tmp_path):
    """Test CLI with invalid individual ID."""
    output_path = str(tmp_path / "output.dot")

    result = subprocess.run(
        [
            python_cmd,
            "-m",
            "gedgraph",
            "pedigree",
            str(sample_gedcom_path),
            "@I999@",
            "-o",
            output_path,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "not found" in result.stderr


def test_cli_invalid_gedcom(python_cmd, tmp_path):
    """Test CLI with non-existent GEDCOM file."""
    nonexistent = str(tmp_path / "nonexistent.ged")
    output_path = str(tmp_path / "out.dot")

    result = subprocess.run(
        [python_cmd, "-m", "gedgraph", "pedigree", nonexistent, "@I1@", "-o", output_path],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "not found" in result.stderr


def test_pedigree_generations(sample_gedcom_path, python_cmd, tmp_path):
    """Test pedigree with different generation settings."""
    output_path = str(tmp_path / "output.dot")

    result = subprocess.run(
        [
            python_cmd,
            "-m",
            "gedgraph",
            "pedigree",
            str(sample_gedcom_path),
            "@I7@",
            "-g",
            "2",
            "-o",
            output_path,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "2 gen" in result.stdout


def test_relationship_max_depth(sample_gedcom_path, python_cmd, tmp_path):
    """Test relationship with max depth setting."""
    output_path = str(tmp_path / "output.dot")

    result = subprocess.run(
        [
            python_cmd,
            "-m",
            "gedgraph",
            "relationship",
            str(sample_gedcom_path),
            "@I1@",
            "@I7@",
            "-d",
            "5",
            "-o",
            output_path,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0


@pytest.mark.parametrize(
    ("chart_type", "variant"),
    [
        ("hourglass", "ancestor-split"),
        ("hourglass", "descendants"),
        ("bowtie", "ancestor-split"),
        ("bowtie", "descendants"),
    ],
)
def test_cli_hourglass_bowtie(sample_gedcom_path, python_cmd, tmp_path, chart_type, variant):
    """Test hourglass and bowtie commands with both variant options."""
    output_path = str(tmp_path / "output.dot")

    result = subprocess.run(
        [
            python_cmd,
            "-m",
            "gedgraph",
            chart_type,
            str(sample_gedcom_path),
            "@I5@",
            "-g",
            "2",
            "-v",
            variant,
            "-o",
            output_path,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"

    with open(output_path) as f:
        content = f.read()
        assert "digraph" in content


def test_cli_main_module(python_cmd):
    """Test that python -m gedgraph exposes all subcommands."""
    result = subprocess.run(
        [python_cmd, "-m", "gedgraph", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "pedigree" in result.stdout
    assert "relationship" in result.stdout
    assert "hourglass" in result.stdout
    assert "bowtie" in result.stdout


@pytest.mark.parametrize("gen_val", ["0", "-1", "16"])
def test_generations_out_of_range(sample_gedcom_path, python_cmd, tmp_path, gen_val):
    """Reject --generations outside 1-15."""
    output_path = str(tmp_path / "output.dot")

    result = subprocess.run(
        [
            python_cmd,
            "-m",
            "gedgraph",
            "pedigree",
            str(sample_gedcom_path),
            "@I7@",
            "-g",
            gen_val,
            "-o",
            output_path,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


@pytest.mark.parametrize("gen_val", ["1", "15"])
def test_generations_boundary_valid(sample_gedcom_path, python_cmd, tmp_path, gen_val):
    """Accept --generations at boundaries 1 and 15."""
    output_path = str(tmp_path / "output.dot")

    result = subprocess.run(
        [
            python_cmd,
            "-m",
            "gedgraph",
            "pedigree",
            str(sample_gedcom_path),
            "@I7@",
            "-g",
            gen_val,
            "-o",
            output_path,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


@pytest.mark.parametrize("depth_val", ["0", "51"])
def test_max_depth_out_of_range(sample_gedcom_path, python_cmd, tmp_path, depth_val):
    """Reject --max-depth outside 1-50."""
    output_path = str(tmp_path / "output.dot")

    result = subprocess.run(
        [
            python_cmd,
            "-m",
            "gedgraph",
            "relationship",
            str(sample_gedcom_path),
            "@I1@",
            "@I7@",
            "-d",
            depth_val,
            "-o",
            output_path,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_max_depth_boundary_valid_min(sample_gedcom_path, python_cmd, tmp_path):
    """Accept --max-depth 1 with a directly connected pair."""
    output_path = str(tmp_path / "output.dot")

    result = subprocess.run(
        [
            python_cmd,
            "-m",
            "gedgraph",
            "relationship",
            str(sample_gedcom_path),
            "@I1@",
            "@I3@",
            "-d",
            "1",
            "-o",
            output_path,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_max_depth_boundary_valid_max(sample_gedcom_path, python_cmd, tmp_path):
    """Accept --max-depth 50."""
    output_path = str(tmp_path / "output.dot")

    result = subprocess.run(
        [
            python_cmd,
            "-m",
            "gedgraph",
            "relationship",
            str(sample_gedcom_path),
            "@I1@",
            "@I7@",
            "-d",
            "50",
            "-o",
            output_path,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_cli_malformed_gedcom(python_cmd, tmp_path):
    """Malformed GEDCOM shows sanitized error, not ged4py internals."""
    bad_ged = tmp_path / "bad.ged"
    bad_ged.write_text("this is not a valid gedcom file\n")
    output_path = str(tmp_path / "out.dot")

    result = subprocess.run(
        [python_cmd, "-m", "gedgraph", "pedigree", str(bad_ged), "@I1@", "-o", output_path],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Error:" in result.stderr
    # Must not leak ged4py class names or tracebacks
    assert "ParserError" not in result.stderr
    assert "IntegrityError" not in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("command", "individuals", "extra_args"),
    [
        ("pedigree", ["@I7@"], ["-g", "2"]),
        ("relationship", ["@I1@", "@I7@"], ["-d", "5"]),
        ("hourglass", ["@I5@"], ["-g", "2", "-v", "ancestor-split"]),
        ("bowtie", ["@I5@"], ["-g", "2", "-v", "ancestor-split"]),
    ],
)
def test_cli_quiet_suppresses_progress(
    sample_gedcom_path, python_cmd, tmp_path, command, individuals, extra_args
):
    """Quiet mode suppresses all spinner output on stderr."""
    output_path = str(tmp_path / "output.dot")

    result = subprocess.run(
        [
            python_cmd,
            "-m",
            "gedgraph",
            "-q",
            command,
            str(sample_gedcom_path),
            *individuals,
            "-o",
            output_path,
            *extra_args,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stderr == ""
    assert result.stdout.strip() != ""


def test_cli_default_shows_phases(sample_gedcom_path, python_cmd, tmp_path):
    """Default mode shows phase progress on stderr."""
    output_path = str(tmp_path / "output.dot")

    result = subprocess.run(
        [
            python_cmd,
            "-m",
            "gedgraph",
            "pedigree",
            str(sample_gedcom_path),
            "@I7@",
            "-o",
            output_path,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "[1/3]" in result.stderr
    assert "Loading GEDCOM" in result.stderr
    assert "Writing output" in result.stderr
