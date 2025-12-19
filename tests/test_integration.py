"""Integration tests for GedGraph."""

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
                "gedgraph.py",
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
        assert "Pedigree chart generated" in result.stdout

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
                "gedgraph.py",
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
        assert "Relationship chart generated" in result.stdout
        assert "Path length: 3" in result.stdout

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
                "gedgraph.py",
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
                "gedgraph.py",
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
    result = subprocess.run(
        [python_cmd, "gedgraph.py", "pedigree", "nonexistent.ged", "@I1@", "-o", "out.dot"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "not found" in result.stderr


def test_pedigree_generations(sample_gedcom_path, python_cmd):
    """Test pedigree with different generation settings."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dot", delete=False) as f:
        output_path = f.name

    try:
        result = subprocess.run(
            [
                python_cmd,
                "gedgraph.py",
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
        assert "Generations: 2" in result.stdout

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
                "gedgraph.py",
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
