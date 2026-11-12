"""What launching the CLI with a provider adds: settings, environment, and no key on the command."""

import pytest
from fake_vault import FakeVault

from wxclaude.core.claude.launch import (
    KEY_VARIABLE,
    NO_KEY,
    SCRUB_VARIABLE,
    TELEMETRY_OFF,
    ProviderLaunch,
    launch_for,
    provider_environment,
    provider_settings,
    sends_effort,
)
from wxclaude.core.config.providers import CLAUDE, KEY_NONE, Provider, ProviderStore
from wxclaude.core.security.key_relay import KeyRelay, RelayAccess

pytestmark = pytest.mark.unit

SECRET = "sk-secret-123"
INHERITED = {
    "PATH": "C:\\Windows",
    "HOME": "C:\\Users\\me",
    "ANTHROPIC_API_KEY": "sk-ant-mine",
    "ANTHROPIC_BASE_URL": "https://other.example.com",
    "ANTHROPIC_AUTH_TOKEN": "tok-mine",
    "anthropic_model": "lower case name",
    "CLAUDE_CODE_USE_BEDROCK": "1",
    "CLAUDE_CODE_USE_VERTEX": "1",
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "999",
    "CLAUDE_CONFIG_DIR": "C:\\config",
    "DISABLE_TELEMETRY": "0",
}


def deepseek(**changes: object) -> Provider:
    provider = Provider(
        id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com/anthropic",
        tiers=["deepseek-chat", "deepseek-chat", "deepseek-reasoner", "deepseek-reasoner"],
    )
    for name, value in changes.items():
        setattr(provider, name, value)
    return provider


def launch(provider: Provider | None = None, *, scrub: bool = True) -> ProviderLaunch:
    return ProviderLaunch(provider or deepseek(), SECRET, scrub)


# -- Claude adds nothing --------------------------------------------------------------------


@pytest.mark.parametrize("claude", [None, ProviderLaunch(CLAUDE)])
def test_claude_adds_nothing(claude: ProviderLaunch | None) -> None:
    assert provider_settings(claude) == {}
    assert provider_environment(claude, INHERITED) is None
    assert sends_effort(claude)


def test_claude_is_not_active_and_a_provider_is() -> None:
    assert not ProviderLaunch(CLAUDE).active
    assert launch().active


# -- the settings ---------------------------------------------------------------------------


def test_the_settings_hold_the_address_and_the_aliases_of_the_ranks() -> None:
    assert provider_settings(launch()) == {
        "env": {
            "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-chat",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-chat",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-reasoner",
        }
    }


def test_the_variables_of_the_provider_go_to_the_inline_settings() -> None:
    provider = deepseek(env={"API_TIMEOUT_MS": "600000", "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "65536"})
    env = provider_settings(launch(provider))["env"]
    assert isinstance(env, dict)
    assert env["API_TIMEOUT_MS"] == "600000"
    assert env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] == "65536"
    assert "API_TIMEOUT_MS" not in provider_settings(launch())["env"]  # type: ignore[operator]


def test_the_window_and_the_length_of_an_answer_can_be_set_too() -> None:
    provider = deepseek(
        env={
            "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "40000",
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "4096",
        }
    )
    env = provider_settings(launch(provider))["env"]
    assert isinstance(env, dict)
    assert env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] == "40000"
    assert env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "4096"


def test_only_a_known_variable_with_a_valid_value_is_sent() -> None:
    provider = deepseek(env={"API_TIMEOUT_MS": "abc", "ANTHROPIC_BASE_URL": "http://evil"})
    env = provider_settings(launch(provider))["env"]
    assert isinstance(env, dict)
    assert "API_TIMEOUT_MS" not in env
    assert env["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"


def test_the_settings_never_hold_the_key() -> None:
    assert SECRET not in str(provider_settings(launch()))


# -- the environment ------------------------------------------------------------------------


def test_the_key_goes_to_the_environment_as_the_auth_token() -> None:
    environment = provider_environment(launch(), INHERITED)
    assert environment is not None
    assert environment[KEY_VARIABLE] == SECRET


def test_the_variables_that_choose_a_provider_are_not_passed_on() -> None:
    environment = provider_environment(launch(), INHERITED)
    assert environment is not None
    assert "ANTHROPIC_API_KEY" not in environment
    assert "ANTHROPIC_BASE_URL" not in environment
    assert "anthropic_model" not in environment
    assert "CLAUDE_CODE_USE_BEDROCK" not in environment
    assert "CLAUDE_CODE_USE_VERTEX" not in environment
    assert environment[KEY_VARIABLE] != "tok-mine"


def test_the_rest_of_the_environment_is_kept() -> None:
    environment = provider_environment(launch(), INHERITED)
    assert environment is not None
    assert environment["PATH"] == "C:\\Windows"
    assert environment["HOME"] == "C:\\Users\\me"
    assert environment["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "999"
    assert environment["CLAUDE_CONFIG_DIR"] == "C:\\config"


def test_what_is_sent_to_anthropic_is_turned_off() -> None:
    environment = provider_environment(launch(), INHERITED)
    assert environment is not None
    for name, value in TELEMETRY_OFF.items():
        assert environment[name] == value
    assert set(TELEMETRY_OFF) == {
        "DISABLE_TELEMETRY",
        "DISABLE_ERROR_REPORTING",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
    }


def test_the_tools_of_claude_do_not_see_the_credentials_unless_the_user_chose_so() -> None:
    scrubbed = provider_environment(launch(scrub=True), INHERITED)
    kept = provider_environment(launch(scrub=False), INHERITED)
    assert scrubbed is not None
    assert kept is not None
    assert scrubbed[SCRUB_VARIABLE] == "1"
    assert SCRUB_VARIABLE not in kept
    assert launch().scrub  # on by default


def test_a_provider_without_a_key_gets_a_placeholder() -> None:
    local = Provider(id="lm", name="LM", base_url="http://127.0.0.1:1234", key_source=KEY_NONE)
    environment = provider_environment(ProviderLaunch(local), INHERITED)
    assert environment is not None
    assert environment[KEY_VARIABLE] == NO_KEY


def test_the_environment_of_the_application_is_not_changed() -> None:
    before = dict(INHERITED)
    provider_environment(launch(), INHERITED)
    assert before == INHERITED


def test_without_an_environment_given_the_one_of_the_process_is_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-mine")
    monkeypatch.setenv("WXCLAUDE_TEST_VARIABLE", "kept")
    environment = provider_environment(launch())
    assert environment is not None
    assert "ANTHROPIC_API_KEY" not in environment
    assert environment["WXCLAUDE_TEST_VARIABLE"] == "kept"


# -- the effort and the repr ----------------------------------------------------------------


def test_the_effort_is_sent_only_if_the_provider_accepts_it() -> None:
    assert sends_effort(launch())
    assert not sends_effort(launch(deepseek(send_effort=False)))


def test_the_key_is_not_in_the_repr() -> None:
    assert SECRET not in repr(launch())
    assert SECRET not in str(launch())


# -- the relay --------------------------------------------------------------------------------

RELAY = RelayAccess("http://127.0.0.1:5555", "tok-relay")


def relayed(provider: Provider | None = None) -> ProviderLaunch:
    return ProviderLaunch(provider or deepseek(), "", False, RELAY)


def test_with_the_relay_the_cli_gets_the_address_of_the_relay_not_that_of_the_provider() -> None:
    settings = provider_settings(relayed())
    env = settings["env"]
    assert isinstance(env, dict)
    assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:5555"
    assert "deepseek.com" not in str(settings)
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "deepseek-chat"  # the aliases stay


def test_with_the_relay_the_cli_gets_the_token_and_never_the_key() -> None:
    environment = provider_environment(relayed(), INHERITED)
    assert environment is not None
    assert environment[KEY_VARIABLE] == "tok-relay"
    assert SCRUB_VARIABLE not in environment  # nothing to hide: the modes of permission work
    assert SECRET not in str(environment)
    assert "tok-relay" not in repr(relayed())


def test_a_provider_without_a_key_keeps_its_placeholder_through_the_relay() -> None:
    local = Provider(id="lm", name="LM", base_url="http://127.0.0.1:1234", key_source=KEY_NONE)
    environment = provider_environment(relayed(local), INHERITED)
    assert environment is not None
    assert environment[KEY_VARIABLE] == NO_KEY


def store_with_key() -> ProviderStore:
    store = ProviderStore(FakeVault())
    store.add(deepseek())
    store.set_key("deepseek", SECRET)
    return store


def test_masked_and_shared_give_the_key_to_the_cli_hidden_or_not() -> None:
    masked = launch_for("deepseek", store_with_key(), transmission="masked")
    shared = launch_for("deepseek", store_with_key(), transmission="shared")
    assert masked is not None
    assert shared is not None
    assert (masked.key, masked.scrub, masked.relay) == (SECRET, True, None)
    assert (shared.key, shared.scrub, shared.relay) == (SECRET, False, None)


def test_relayed_gives_the_cli_the_relay_and_keeps_the_key_in_the_relay() -> None:
    relay = KeyRelay(check_seconds=3600)
    try:
        launched = launch_for("deepseek", store_with_key(), transmission="relayed", relay=relay)
        assert launched is not None
        assert launched.key == ""
        assert not launched.scrub
        assert launched.relay is not None
        assert launched.relay.base_url.startswith("http://127.0.0.1:")
        assert relay.running
    finally:
        relay.stop()


def test_relayed_without_a_relay_falls_back_to_masked() -> None:
    launched = launch_for("deepseek", store_with_key(), transmission="relayed")
    assert launched is not None
    assert (launched.key, launched.scrub, launched.relay) == (SECRET, True, None)


def test_a_provider_that_needs_no_key_has_nothing_to_hide_or_to_relay() -> None:
    store = ProviderStore(FakeVault())
    store.add(Provider(id="lm", name="LM", base_url="http://x", key_source=KEY_NONE, tiers=["q"]))
    relay = KeyRelay(check_seconds=3600)
    try:
        for transmission in ("masked", "shared", "relayed"):
            launched = launch_for("lm", store, transmission=transmission, relay=relay)
            assert launched is not None
            assert not launched.scrub  # no secret: the modes of permission are left alone
            assert launched.relay is None
        assert not relay.running
    finally:
        relay.stop()


def test_claude_is_never_launched_with_a_relay() -> None:
    relay = KeyRelay(check_seconds=3600)
    assert launch_for("claude", store_with_key(), transmission="relayed", relay=relay) is None
    assert launch_for(None, store_with_key(), transmission="relayed", relay=relay) is None
    assert not relay.running
