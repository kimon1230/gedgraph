"""Integration tests for GedGraph."""

import shutil
import subprocess
import sys
import tempfile
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


def test_cli_pedigree(sample_gedcom_path, python_cmd):
    """Test CLI pedigree command."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dot", delete=False) as f:
        output_path = f.name

    try:
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

    finally:
        Path(output_path).unlink(missing_ok=True)


def test_cli_relationship(sample_gedcom_path, python_cmd):
    """Test CLI relationship command."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dot", delete=False) as f:
        output_path = f.name

    try:
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

    finally:
        Path(output_path).unlink(missing_ok=True)


def test_cli_no_relationship(sample_gedcom_path, python_cmd):
    """Test CLI when no relationship exists."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dot", delete=False) as f:
        output_path = f.name

    try:
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

    finally:
        Path(output_path).unlink(missing_ok=True)


def test_cli_invalid_individual(sample_gedcom_path, python_cmd):
    """Test CLI with invalid individual ID."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dot", delete=False) as f:
        output_path = f.name

    try:
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

    finally:
        Path(output_path).unlink(missing_ok=True)


def test_cli_invalid_gedcom(python_cmd):
    """Test CLI with non-existent GEDCOM file."""
    tmpdir = tempfile.mkdtemp()
    nonexistent = str(Path(tmpdir) / "nonexistent.ged")
    output_path = str(Path(tmpdir) / "out.dot")
    try:
        result = subprocess.run(
            [python_cmd, "-m", "gedgraph", "pedigree", nonexistent, "@I1@", "-o", output_path],
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "not found" in result.stderr
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_pedigree_generations(sample_gedcom_path, python_cmd):
    """Test pedigree with different generation settings."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dot", delete=False) as f:
        output_path = f.name

    try:
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

    finally:
        Path(output_path).unlink(missing_ok=True)


def test_relationship_max_depth(sample_gedcom_path, python_cmd):
    """Test relationship with max depth setting."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dot", delete=False) as f:
        output_path = f.name

    try:
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

    finally:
        Path(output_path).unlink(missing_ok=True)


@pytest.mark.parametrize(
    ("chart_type", "variant"),
    [
        ("hourglass", "ancestor-split"),
        ("hourglass", "descendants"),
        ("bowtie", "ancestor-split"),
        ("bowtie", "descendants"),
    ],
)
def test_cli_hourglass_bowtie(sample_gedcom_path, python_cmd, chart_type, variant):
    """Test hourglass and bowtie commands with both variant options."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dot", delete=False) as f:
        output_path = f.name

    try:
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

    finally:
        Path(output_path).unlink(missing_ok=True)


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
def test_generations_out_of_range(sample_gedcom_path, python_cmd, gen_val):
    """Reject --generations outside 1-15."""
    with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
        output_path = f.name
    try:
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
    finally:
        Path(output_path).unlink(missing_ok=True)


@pytest.mark.parametrize("gen_val", ["1", "15"])
def test_generations_boundary_valid(sample_gedcom_path, python_cmd, gen_val):
    """Accept --generations at boundaries 1 and 15."""
    with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
        output_path = f.name
    try:
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
    finally:
        Path(output_path).unlink(missing_ok=True)


@pytest.mark.parametrize("depth_val", ["0", "51"])
def test_max_depth_out_of_range(sample_gedcom_path, python_cmd, depth_val):
    """Reject --max-depth outside 1-50."""
    with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
        output_path = f.name
    try:
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
    finally:
        Path(output_path).unlink(missing_ok=True)


def test_max_depth_boundary_valid_min(sample_gedcom_path, python_cmd):
    """Accept --max-depth 1 with a directly connected pair."""
    with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
        output_path = f.name
    try:
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
    finally:
        Path(output_path).unlink(missing_ok=True)


def test_max_depth_boundary_valid_max(sample_gedcom_path, python_cmd):
    """Accept --max-depth 50."""
    with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
        output_path = f.name
    try:
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
    finally:
        Path(output_path).unlink(missing_ok=True)
