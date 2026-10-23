"""The version of the application: one number, in the right form, written in the changelog."""

import re
from pathlib import Path

import pytest
from setuptools.config.pyprojecttoml import read_configuration

from wxclaude import __version__

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parent.parent


def test_the_version_has_the_form_major_minor_patch() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_the_package_metadata_reads_the_version_of_the_code() -> None:
    configuration = read_configuration(str(ROOT / "pyproject.toml"), expand=True)
    assert configuration["project"]["version"] == __version__


def test_the_changelog_has_an_entry_for_the_version() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(rf"^## {re.escape(__version__)}\b", changelog, re.MULTILINE)
