"""A launch with a provider: the arguments and the environment the CLI is given."""

import json
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

from wxclaude.core.claude.events import RunEvent, TurnEnded
from wxclaude.core.claude.launch import ProviderLaunch
from wxclaude.core.claude.permission_channel import HOOK, StdioChannel, make_channel
from wxclaude.core.claude.runner import ClaudeRunner, RunRequest, build_arguments
from wxclaude.core.config.agents import Agent
from wxclaude.core.config.providers import CLAUDE, Provider

pytestmark = pytest.mark.unit

FAKE = Path(__file__).resolve().parents[2] / "fakes" / "fake_claude.py"
SESSION = "11111111-1111-4111-8111-111111111111"
SECRET = "sk-secret-123"
AGENT = Agent(model="deepseek-chat", effort="low", permission_mode="manual")


def deepseek(*, send_effort: bool = True) -> Provider:
    return Provider(
        id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com/anthropic",
        tiers=["deepseek-chat"],
        send_effort=send_effort,
    )


def request(
    workspace: Path, provider: ProviderLaunch | None, *, restricted: bool = False
) -> RunRequest:
    return RunRequest(
        "Hello", AGENT, SESSION, False, workspace, restricted=restricted, provider=provider
    )


def option(arguments: list[str], name: str) -> str:
    return arguments[arguments.index(name) + 1]


# -- the arguments --------------------------------------------------------------------------


def test_claude_is_launched_as_it_always_was(tmp_path: Path) -> None:
    for claude in (None, ProviderLaunch(CLAUDE)):
        arguments = build_arguments(request(tmp_path, claude), StdioChannel())
        assert "--settings" not in arguments
        assert option(arguments, "--effort") == "low"


def test_a_provider_gives_its_address_in_the_inline_settings(tmp_path: Path) -> None:
    arguments = build_arguments(
        request(tmp_path, ProviderLaunch(deepseek(), SECRET)), StdioChannel()
    )
    assert arguments.count("--settings") == 1
    assert json.loads(option(arguments, "--settings")) == {
        "env": {
            "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-chat",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-chat",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-chat",
        }
    }
    assert option(arguments, "--model") == "deepseek-chat"


def test_the_key_is_never_in_the_arguments(tmp_path: Path) -> None:
    channel = make_channel(HOOK, lambda _event: None, 90)
    try:
        arguments = build_arguments(
            request(tmp_path, ProviderLaunch(deepseek(), SECRET), restricted=True), channel
        )
    finally:
        channel.close()
    assert SECRET not in " ".join(arguments)


def test_the_effort_is_left_out_for_a_server_that_refuses_it(tmp_path: Path) -> None:
    arguments = build_arguments(
        request(tmp_path, ProviderLaunch(deepseek(send_effort=False), SECRET)), StdioChannel()
    )
    assert "--effort" not in arguments
    assert "low" not in arguments


def test_the_hook_the_provider_and_the_restriction_share_one_settings_argument(
    tmp_path: Path,
) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"deny": ["Read(.env)"]}}), encoding="utf-8"
    )
    channel = make_channel(HOOK, lambda _event: None, 90)
    try:
        arguments = build_arguments(
            request(tmp_path, ProviderLaunch(deepseek(), SECRET), restricted=True), channel
        )
    finally:
        channel.close()
    assert arguments.count("--settings") == 1
    settings = json.loads(option(arguments, "--settings"))
    assert settings["hooks"]["PermissionRequest"]
    assert settings["env"]["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"
    assert settings["permissions"] == {"deny": ["Read(.env)"]}
    assert option(arguments, "--setting-sources") == "user"


# -- the process ----------------------------------------------------------------------------


class Collector:
    def __init__(self) -> None:
        self.done = threading.Event()
        self.ended: TurnEnded | None = None

    def __call__(self, event: RunEvent) -> None:
        if isinstance(event, TurnEnded):
            self.ended = event
            self.done.set()


def launch_with(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider: ProviderLaunch | None
) -> dict[str, Any]:
    """Run the fake claude once and return what it says it was given (its log)."""
    log = tmp_path / "log.json"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    collector = Collector()
    ClaudeRunner([sys.executable, str(FAKE)]).start(request(tmp_path, provider), collector)
    assert collector.done.wait(30), "the run did not end"
    assert collector.ended is not None
    assert collector.ended.exit_code == 0
    report: dict[str, Any] = json.loads(log.read_text(encoding="utf-8"))
    return report


def test_a_provider_gets_its_key_in_the_environment_and_none_of_the_inherited_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-mine")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://other.example.com")
    monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
    report = launch_with(tmp_path, monkeypatch, ProviderLaunch(deepseek(), SECRET))
    environment = report["environment"]
    assert environment["ANTHROPIC_AUTH_TOKEN"] == SECRET
    assert "ANTHROPIC_API_KEY" not in environment
    assert "ANTHROPIC_BASE_URL" not in environment
    assert "CLAUDE_CODE_USE_BEDROCK" not in environment
    assert environment["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"] == "1"
    assert environment["DISABLE_TELEMETRY"] == "1"
    assert SECRET not in " ".join(report["arguments"])


def test_the_scrub_can_be_turned_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = launch_with(tmp_path, monkeypatch, ProviderLaunch(deepseek(), SECRET, scrub=False))
    assert "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB" not in report["environment"]


def test_claude_keeps_the_environment_of_the_application(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-mine")
    report = launch_with(tmp_path, monkeypatch, None)
    environment = report["environment"]
    assert environment["ANTHROPIC_API_KEY"] == "sk-ant-mine"
    assert "DISABLE_TELEMETRY" not in environment
    assert "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB" not in environment
    assert "ANTHROPIC_AUTH_TOKEN" not in environment
