"""Names that look like a credential or redirect the traffic, and the masking of secrets."""

import json

import pytest

from wxclaude.core.security.sensitive import (
    is_credential_name,
    is_sensitive_name,
    mask_json_text,
    mask_secrets,
    mask_url,
    masked_value,
    name_words,
    redirects_traffic,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("name", "words"),
    [
        ("ANTHROPIC_AUTH_TOKEN", ["ANTHROPIC", "AUTH", "TOKEN"]),
        ("apiKey", ["API", "KEY"]),
        ("APIKey", ["API", "KEY"]),
        ("x-api-key", ["X", "API", "KEY"]),
        ("baseUrl", ["BASE", "URL"]),
        ("", []),
        ("__", []),
    ],
)
def test_name_words(name: str, words: list[str]) -> None:
    assert name_words(name) == words


@pytest.mark.parametrize(
    "name",
    [
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_API_KEY",
        "NPM_TOKEN",
        "GITHUB_TOKEN",
        "AWS_SECRET_ACCESS_KEY",
        "DB_PASSWORD",
        "MYSQL_PWD",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "apiKey",
        "Authorization",
        "x-api-key",
        "Cookie",
        "SENTRY_DSN",
    ],
)
def test_credential_names(name: str) -> None:
    assert is_credential_name(name)
    assert is_sensitive_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "MODEL",
        "ANTHROPIC_MODEL",
        "DATABASE_URL",
        "HTTPS_PROXY",
        "ANTHROPIC_BASE_URL",
        "MAX_THINKING_TOKENS",
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS",
        "KEYBOARD_LAYOUT",
        "monkey",
        "permissions",
        "apiKeyHelper",
        "awsAuthRefresh",
        "awsCredentialExport",
    ],
)
def test_not_credential_names(name: str) -> None:
    assert not is_credential_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_BEDROCK_BASE_URL",
        "baseUrl",
        "HTTP_PROXY",
        "https_proxy",
        "NO_PROXY",
        "AWS_ENDPOINT_URL",
        "SSL_CERT_FILE",
        "NODE_EXTRA_CA_CERTS",
        "REQUESTS_CA_BUNDLE",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX",
    ],
)
def test_names_that_redirect_the_traffic(name: str) -> None:
    assert redirects_traffic(name)
    assert is_sensitive_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "MODEL",
        "ANTHROPIC_AUTH_TOKEN",
        "BASE",
        "URL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "DATABASE_URL",
    ],
)
def test_names_that_do_not_redirect_the_traffic(name: str) -> None:
    assert not redirects_traffic(name)


@pytest.mark.parametrize(
    "name", ["MODEL", "DATABASE_URL", "BASH_DEFAULT_TIMEOUT_MS", "apiKeyHelper"]
)
def test_ordinary_names_are_not_sensitive(name: str) -> None:
    assert not is_sensitive_name(name)


def test_masked_value_is_stable_and_hides_the_value() -> None:
    first = masked_value("sk-secret-123")
    assert first == masked_value("sk-secret-123")
    assert first != masked_value("sk-secret-124")
    assert first.startswith("sha256:")
    assert "secret" not in first


def test_masked_value_tells_types_apart() -> None:
    assert masked_value("1") != masked_value(1)


def test_mask_secrets_at_every_depth() -> None:
    data = {
        "env": {"ANTHROPIC_AUTH_TOKEN": "sk-1", "MODEL": "haiku"},
        "mcpServers": {
            "web": {"headers": {"Authorization": "Bearer abc", "Accept": "text/html"}},
        },
        "hooks": [{"command": "run.bat", "apiKey": "k-2"}, "plain"],
        "count": 3,
    }
    masked = mask_secrets(data)
    assert masked == {
        "env": {"ANTHROPIC_AUTH_TOKEN": masked_value("sk-1"), "MODEL": "haiku"},
        "mcpServers": {
            "web": {
                "headers": {"Authorization": masked_value("Bearer abc"), "Accept": "text/html"}
            },
        },
        "hooks": [{"command": "run.bat", "apiKey": masked_value("k-2")}, "plain"],
        "count": 3,
    }


def test_mask_secrets_replaces_a_whole_container_under_a_credential_key() -> None:
    masked = mask_secrets({"secrets": {"a": "1", "b": ["2"]}, "token": None})
    assert masked == {
        "secrets": masked_value({"a": "1", "b": ["2"]}),
        "token": masked_value(None),
    }


def test_mask_secrets_does_not_change_its_input() -> None:
    data = {"env": {"MY_TOKEN": "sk-1"}}
    mask_secrets(data)
    assert data == {"env": {"MY_TOKEN": "sk-1"}}


@pytest.mark.parametrize("data", [None, True, 3, 1.5, "text", [], {}, [1, "a", None]])
def test_mask_secrets_leaves_other_values_alone(data: object) -> None:
    assert mask_secrets(data) == data


def test_a_changed_secret_changes_the_copy_and_an_equal_one_does_not() -> None:
    before = mask_json_text('{"env": {"MY_TOKEN": "a"}}')
    same = mask_json_text('{"env":{"MY_TOKEN":"a"}}')
    after = mask_json_text('{"env": {"MY_TOKEN": "b"}}')
    assert before == same
    assert before != after


def test_mask_json_text_hides_the_secret_and_keeps_the_rest() -> None:
    text = mask_json_text('{"env": {"MY_TOKEN": "sk-very-secret", "NAME": "café"}}')
    assert text is not None
    assert "sk-very-secret" not in text
    assert "café" in text
    assert json.loads(text)["env"]["NAME"] == "café"
    assert text.endswith("\n")


@pytest.mark.parametrize("text", ["", "# A Markdown file", "{not json", '{"a": 1,}', "token=abc"])
def test_mask_json_text_gives_none_for_what_is_not_json(text: str) -> None:
    assert mask_json_text(text) is None


def hidden(url: str, shown: str) -> str:
    return f"{shown}/{masked_value(url)}"


@pytest.mark.parametrize(
    ("url", "shown"),
    [
        (
            "postgres://alice:pw@db.example.com:5432/prod?sslpassword=abc",
            "postgres://db.example.com:5432",
        ),
        ("https://hooks.slack.com/services/T000/B000/XXXX", "https://hooks.slack.com"),
        ("https://ghp_token@github.com/org/repo.git", "https://github.com"),
        ("https://api.example.com/v1#frag", "https://api.example.com"),
        ("redis://:pw@10.0.0.5:6379/0", "redis://10.0.0.5:6379"),
        ("http://[::1]:8080/path?x=1", "http://[::1]:8080"),
        ("mongodb+srv://u:p@cluster0.example.net/db", "mongodb+srv://cluster0.example.net"),
        ("https://example.com?token=abc", "https://example.com"),
    ],
)
def test_mask_url_keeps_only_scheme_host_and_port(url: str, shown: str) -> None:
    assert mask_url(url) == hidden(url, shown)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:1234",
        "https://api.deepseek.com/",
        "https://api.example.com",
        "http://localhost",
    ],
)
def test_mask_url_keeps_an_url_with_nothing_to_hide(url: str) -> None:
    assert mask_url(url) == url


def test_mask_url_tells_a_change_anywhere_in_the_url() -> None:
    assert mask_url("https://a.example.com/x") != mask_url("https://a.example.com/y")
    assert mask_url("https://u:1@a.example.com") != mask_url("https://u:2@a.example.com")


def test_mask_url_keeps_a_change_of_host_readable() -> None:
    assert mask_url("https://evil.example.net/x").startswith("https://evil.example.net/")


@pytest.mark.parametrize(
    "url",
    [
        "postgres://alice:pa/ss@db.example.com/prod",  # a raw "/" in the password
        "postgres://alice:pa?ss@db.example.com/prod",
        "http+unix://%2Fvar%2Frun%2Fsock/path",
        "https:///nohost?token=abc",
        "a://",
    ],
)
def test_mask_url_hides_an_url_whose_host_cannot_be_read(url: str) -> None:
    assert mask_url(url) == masked_value(url)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "haiku",
        "curl https://x.example.com?token=abc",
        "C:\\Users\\me",
        "mailto:me@x.org",
    ],
)
def test_mask_url_leaves_other_text_alone(text: str) -> None:
    assert mask_url(text) == text


def test_mask_secrets_masks_urls_in_values_and_lists() -> None:
    masked = mask_secrets(
        {
            "env": {"DATABASE_URL": "postgres://u:p@db.example.com/prod", "MODEL": "haiku"},
            "servers": ["https://hooks.example.com/T/B/X", "stdio"],
        }
    )
    assert masked == {
        "env": {
            "DATABASE_URL": hidden(
                "postgres://u:p@db.example.com/prod", "postgres://db.example.com"
            ),
            "MODEL": "haiku",
        },
        "servers": [
            hidden("https://hooks.example.com/T/B/X", "https://hooks.example.com"),
            "stdio",
        ],
    }
