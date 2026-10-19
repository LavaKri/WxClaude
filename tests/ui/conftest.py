from pathlib import Path

import pytest
import wx


@pytest.fixture(scope="session")
def wx_app():
    """One wx application for the whole session: wx cannot cleanly recreate it per test."""
    return wx.App()


@pytest.fixture(autouse=True)
def claude_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty Claude Code configuration folder: the tests never read the real one."""
    folder = tmp_path / "claude-config"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(folder))
    return folder
