from datetime import datetime

import pytest

from wxclaude.core.claude.permissions import hook_wait_text

pytestmark = pytest.mark.unit


def test_the_text_gives_the_deadline_and_the_minutes() -> None:
    now = datetime(2026, 10, 24, 13, 49, 30)
    assert hook_wait_text(now, 10) == "Without an answer by 13:59 (10 min), Claude denies the tool."


def test_the_deadline_can_pass_midnight() -> None:
    assert "00:05 (10 min)" in hook_wait_text(datetime(2026, 10, 24, 23, 55), 10)
