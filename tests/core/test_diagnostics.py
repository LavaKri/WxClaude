import logging
import sys
import threading
from datetime import datetime
from pathlib import Path

import pytest

from wxclaude import __version__
from wxclaude.core import diagnostics

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def restore_hooks() -> object:
    excepthook, thread_hook = sys.excepthook, threading.excepthook
    yield
    sys.excepthook, threading.excepthook = excepthook, thread_hook
    diagnostics.logger.handlers.clear()


def test_startup_report_groups_the_information(tmp_path: Path) -> None:
    lines = diagnostics.startup_report(
        datetime(2026, 10, 24, 9, 30), Path("C:/x/WxClaude.exe"), tmp_path, "debug"
    )
    text = "\n".join(lines)
    assert "Started:       2026-10-24T09:30:00" in text
    assert f"Version:       {__version__}" in text
    assert "Launched from: " in text
    assert "OS:" in text
    assert "Memory:" in text
    assert f"Preferences:   {tmp_path}" in text
    assert text.index("--- Application ---") < text.index("--- System ---")
    assert text.index("--- System ---") < text.index("--- Folders ---")


def test_log_file_starts_with_the_report(tmp_path: Path) -> None:
    log_file = diagnostics.configure_logging(tmp_path, "info")
    diagnostics.log_startup(tmp_path, Path("WxClaude.exe"), "info")
    diagnostics.logger.info("hello")
    diagnostics.logger.debug("hidden")
    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "=== WxClaude start ==="
    assert lines[-1].endswith("hello")
    assert "hidden" not in "\n".join(lines)


def test_debug_level_keeps_debug_lines(tmp_path: Path) -> None:
    log_file = diagnostics.configure_logging(tmp_path, "debug")
    diagnostics.logger.debug("detail")
    assert "detail" in log_file.read_text(encoding="utf-8")


def test_uncaught_error_of_a_thread_is_logged(tmp_path: Path) -> None:
    log_file = diagnostics.configure_logging(tmp_path, "error")

    def fail() -> None:
        raise ValueError("boom")

    thread = threading.Thread(target=fail, name="reader")
    thread.start()
    thread.join()
    text = log_file.read_text(encoding="utf-8")
    assert "Uncaught error in thread reader" in text
    assert "ValueError: boom" in text


def test_uncaught_error_of_the_main_thread_is_logged(tmp_path: Path) -> None:
    log_file = diagnostics.configure_logging(tmp_path, "error")
    error = KeyError("oops")
    sys.excepthook(KeyError, error, None)
    assert "KeyError" in log_file.read_text(encoding="utf-8")
    assert logging.getLogger("wxclaude") is diagnostics.logger
