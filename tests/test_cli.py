"""Tests for CLI entry point."""
import sys
from pathlib import Path
from unittest.mock import patch
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent.parent))
from auto_parts_search.__main__ import cmd_stats, cmd_pairs


def test_stats_command_runs_without_error(capsys):
    """Stats command should work even with no data."""
    cmd_stats()
    captured = capsys.readouterr()
    assert "DATA STATS" in captured.out


def test_pairs_command_generates_vocabulary_pairs(capsys):
    """Pairs command should generate vocabulary pairs even without scraped data."""
    cmd_pairs()
    captured = capsys.readouterr()
    assert "vocabulary pairs" in captured.out.lower() or "Generated" in captured.out
