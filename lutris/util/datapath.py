"""Utility to get the path of Lutris assets"""

from pathlib import Path


def get() -> str:
    """Return the path to Lutris's packaged runtime assets."""
    return str(Path(__file__).resolve().parents[1] / "data")
