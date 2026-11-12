import pytest

from wxclaude.__main__ import parse_arguments

pytestmark = pytest.mark.ui


def test_the_remote_control_is_off_unless_asked() -> None:
    assert not parse_arguments([]).remote
    assert parse_arguments(["--remote"]).remote


def test_the_log_level_is_still_read() -> None:
    assert parse_arguments(["--remote", "--log-level", "debug"]).log_level == "debug"
