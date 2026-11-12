"""The methods that ask a provider for its models and its credit (a fake opener, no network)."""

import io
import json
import urllib.error
import urllib.request
from collections.abc import Callable

import pytest

from wxclaude.core.config.provider_methods import (
    CREDIT_METHODS,
    DEFAULT_CREDIT_METHOD,
    DEFAULT_MODELS_METHOD,
    MODELS_METHODS,
    NONE,
    DeepSeekCredit,
    NoCredit,
    NoModels,
    Opener,
    ProviderMethod,
    V1Models,
    credit_method,
    models_method,
    origin_of,
    unavailable_line,
)
from wxclaude.core.errors import BalanceError, ModelListError

pytestmark = pytest.mark.unit

SECRET = "sk-secret-123"
BASE = "https://api.deepseek.com/anthropic"


class FakeResponse(io.BytesIO):
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class FakeServer:
    """Answers by address: a body, an error code or an exception; records the requests."""

    def __init__(self, answers: dict[str, bytes | int | Exception] | None = None) -> None:
        self.answers = answers or {}
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> FakeResponse:
        self.requests.append(request)
        answer = self.answers.get(request.full_url, 404)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, int):
            raise http_error(answer)
        return FakeResponse(answer)

    @property
    def urls(self) -> list[str]:
        return [request.full_url for request in self.requests]


def http_error(code: int, body: bytes = b"") -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://x", code, "msg", {}, io.BytesIO(body))  # type: ignore[arg-type]


def names(*ids: object) -> bytes:
    return json.dumps({"data": [{"id": name} for name in ids]}).encode()


# -- the registries -------------------------------------------------------------------------


def test_the_lists_of_the_form_start_with_no_method_and_the_defaults_are_known() -> None:
    assert [m.id for m in MODELS_METHODS] == [NONE, "v1"]
    assert [m.id for m in CREDIT_METHODS] == [NONE, "deepseek"]
    assert models_method(DEFAULT_MODELS_METHOD).id == "v1"
    assert credit_method(DEFAULT_CREDIT_METHOD).id == NONE


def test_a_method_that_is_not_known_is_no_method() -> None:
    assert isinstance(models_method("gone"), NoModels)
    assert isinstance(credit_method("gone"), NoCredit)
    assert isinstance(models_method(""), NoModels)


@pytest.mark.parametrize("method", [*MODELS_METHODS, *CREDIT_METHODS], ids=lambda m: m.id)
def test_every_method_keeps_to_the_contract(method: object) -> None:
    """Metadata, paths for the host (never an address), and no request leaves that host."""
    assert isinstance(method, ProviderMethod)
    assert method.id
    assert method.label
    for base in (BASE, "http://127.0.0.1:1234", "https://host.example:8443/a/v1/"):
        for path in method.paths(base):
            assert path.startswith("/")
            assert "://" not in path
            assert not path.startswith("//")
        server = FakeServer()  # everything is a 404: every path is tried
        with pytest.raises((ModelListError, BalanceError)):
            method.call(base, SECRET, opener=server)
        assert all(url.startswith(origin_of(base) + "/") for url in server.urls)


def test_ids_and_labels_are_unique_in_each_family() -> None:
    for family in (MODELS_METHODS, CREDIT_METHODS):
        assert len({m.id for m in family}) == len(family)
        assert len({m.label for m in family if m.id != NONE}) == len(family) - 1


def test_origin_of_keeps_the_scheme_and_the_host_only() -> None:
    assert origin_of("https://api.deepseek.com/anthropic/v1") == "https://api.deepseek.com"
    assert origin_of(" http://127.0.0.1:1234 ") == "http://127.0.0.1:1234"


# -- no method -------------------------------------------------------------------------------


def test_no_method_asks_nothing() -> None:
    server = FakeServer()
    assert not NoModels().available
    assert not NoCredit().available
    with pytest.raises(ModelListError, match="No way"):
        NoModels().fetch(BASE, SECRET, opener=server)
    assert NoCredit().credit("X", BASE, SECRET, opener=server) == []
    assert NoCredit().lines("X", BASE, SECRET, opener=server) == []
    assert server.requests == []


# -- the models: V1 ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        ("http://127.0.0.1:1234", ["/v1/models", "/models"]),
        ("https://api.deepseek.com/anthropic/", ["/anthropic/v1/models", "/v1/models", "/models"]),
        ("http://localhost:11434/v1", ["/v1/models", "/models"]),
    ],
)
def test_v1_paths(base: str, expected: list[str]) -> None:
    assert V1Models().paths(base) == expected


def test_v1_names_in_order_each_once() -> None:
    server = FakeServer({"http://s/v1/models": names("b", "a", "b", " c ", "", 3)})
    assert V1Models().fetch("http://s", opener=server) == ["b", "a", "c"]


def test_v1_key_goes_in_both_headers_and_without_key_in_none() -> None:
    server = FakeServer({"http://s/v1/models": names("m")})
    V1Models().fetch("http://s", SECRET, opener=server)
    request = server.requests[0]
    assert request.get_method() == "GET"
    assert request.get_header("X-api-key") == SECRET
    assert request.get_header("Authorization") == f"Bearer {SECRET}"
    V1Models().fetch("http://s", opener=server)
    assert not server.requests[1].has_header("X-api-key")
    assert not server.requests[1].has_header("Authorization")


def test_v1_tries_the_root_of_the_host_when_the_address_is_not_found() -> None:
    server = FakeServer({"https://api.deepseek.com/models": names("flash", "pro")})
    assert V1Models().fetch(BASE, SECRET, opener=server) == ["flash", "pro"]
    assert server.urls == [
        "https://api.deepseek.com/anthropic/v1/models",
        "https://api.deepseek.com/v1/models",
        "https://api.deepseek.com/models",
    ]


def test_v1_found_nowhere_says_to_type_the_names() -> None:
    with pytest.raises(ModelListError, match="Type the names"):
        V1Models().fetch("http://s", opener=FakeServer())


@pytest.mark.parametrize("code", [401, 403])
def test_v1_a_refused_key_stops_at_once(code: int) -> None:
    server = FakeServer({"http://s/v1/models": code})
    with pytest.raises(ModelListError, match="key"):
        V1Models().fetch("http://s", SECRET, opener=server)
    assert len(server.requests) == 1


def test_v1_another_error_gives_its_code_and_the_message_of_the_server() -> None:
    body = json.dumps({"error": {"message": "overloaded"}}).encode()

    def opener(request: urllib.request.Request, timeout: float) -> FakeResponse:
        raise http_error(500, body)

    with pytest.raises(ModelListError, match=r"500.*overloaded"):
        V1Models().fetch("http://s", opener=opener)


def test_v1_a_redirect_is_not_followed_and_is_said() -> None:
    server = FakeServer({"http://s/v1/models": 302})
    with pytest.raises(ModelListError, match="another address"):
        V1Models().fetch("http://s", opener=server)


def test_the_key_is_never_in_an_error() -> None:
    body = json.dumps({"error": {"message": f"bad token {SECRET}"}}).encode()

    def failing(request: urllib.request.Request, timeout: float) -> FakeResponse:
        raise http_error(400, body)

    def unreachable(request: urllib.request.Request, timeout: float) -> FakeResponse:
        raise urllib.error.URLError(f"refused for {SECRET}")

    calls: tuple[Callable[[Opener], object], ...] = (
        lambda o: V1Models().fetch("http://s", SECRET, opener=o),
        lambda o: DeepSeekCredit().credit("X", "http://s", SECRET, opener=o),
    )
    for opener in (failing, unreachable):
        for call in calls:
            with pytest.raises((ModelListError, BalanceError)) as raised:
                call(opener)
            assert SECRET not in str(raised.value)


def test_v1_an_unreachable_server_is_said() -> None:
    server = FakeServer({"http://s/v1/models": urllib.error.URLError("refused")})
    with pytest.raises(ModelListError, match="refused"):
        V1Models().fetch("http://s", opener=server)


@pytest.mark.parametrize(
    "body",
    [b"not json", b"[]", b'{"data": "x"}', b'{"data": []}', b'{"data": [{"name": "m"}]}', b"\xff"],
)
def test_v1_other_answers_are_refused(body: bytes) -> None:
    with pytest.raises(ModelListError):
        V1Models().fetch("http://s", opener=FakeServer({"http://s/v1/models": body}))


def test_v1_too_big_an_answer_is_refused() -> None:
    with pytest.raises(ModelListError):
        V1Models().fetch("http://s", opener=FakeServer({"http://s/v1/models": b" " * 1_000_002}))


# -- the credit: DeepSeek ---------------------------------------------------------------------

BALANCE_URL = "https://api.deepseek.com/user/balance"


def balance(**changes: object) -> bytes:
    data: dict[str, object] = {
        "is_available": True,
        "balance_infos": [
            {
                "currency": "USD",
                "total_balance": "4.99",
                "granted_balance": "0.00",
                "topped_up_balance": "4.99",
            }
        ],
    }
    data.update(changes)
    return json.dumps(data).encode()


def test_deepseek_asks_the_host_of_the_provider_and_tells_the_credit() -> None:
    server = FakeServer({BALANCE_URL: balance()})
    lines = DeepSeekCredit().credit("DeepSeek", BASE, SECRET, opener=server)
    assert lines == ["DeepSeek: balance 4.99 USD, topped up 4.99, offered 0.00."]
    request = server.requests[0]
    assert request.full_url == BALANCE_URL
    assert request.get_method() == "GET"
    assert request.get_header("Authorization") == f"Bearer {SECRET}"
    assert not request.has_header("X-api-key")


def test_the_key_goes_only_to_the_host_of_the_provider_not_to_deepseek() -> None:
    mirror = "https://mirror.example.com/anthropic"
    server = FakeServer({"https://mirror.example.com/user/balance": balance()})
    assert DeepSeekCredit().credit("Mirror", mirror, SECRET, opener=server)
    assert server.urls == ["https://mirror.example.com/user/balance"]
    assert all("deepseek.com" not in url for url in server.urls)


def test_deepseek_two_currencies_and_a_balance_too_low() -> None:
    infos = [
        {"currency": "CNY", "total_balance": "0.00"},
        {"currency": "USD", "total_balance": "0.00"},
    ]
    server = FakeServer({BALANCE_URL: balance(balance_infos=infos, is_available=False)})
    assert DeepSeekCredit().credit("DeepSeek", BASE, SECRET, opener=server) == [
        "DeepSeek: balance 0.00 CNY.",
        "DeepSeek: balance 0.00 USD.",
        "DeepSeek: the balance is too low to be answered.",
    ]


@pytest.mark.parametrize("code", [401, 403])
def test_deepseek_a_refused_key_is_said(code: int) -> None:
    with pytest.raises(BalanceError, match="refused the key"):
        DeepSeekCredit().credit("X", BASE, SECRET, opener=FakeServer({BALANCE_URL: code}))


def test_deepseek_another_error_gives_its_code() -> None:
    with pytest.raises(BalanceError, match="500"):
        DeepSeekCredit().credit("X", BASE, SECRET, opener=FakeServer({BALANCE_URL: 500}))


def test_deepseek_not_found_says_the_server_does_not_offer_it() -> None:
    with pytest.raises(BalanceError, match="does not offer"):
        DeepSeekCredit().credit("X", BASE, SECRET, opener=FakeServer())


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"[]",
        b"{}",
        b'{"balance_infos": []}',
        b'{"balance_infos": [{"x": 1}]}',
        b"\xff",
    ],
)
def test_deepseek_an_answer_that_is_not_a_balance_is_refused(body: bytes) -> None:
    with pytest.raises(BalanceError, match="balance"):
        DeepSeekCredit().credit("X", BASE, SECRET, opener=FakeServer({BALANCE_URL: body}))


def test_lines_turns_a_failure_into_a_line_for_the_dialog() -> None:
    server = FakeServer({BALANCE_URL: 401})
    lines = DeepSeekCredit().lines("DeepSeek", BASE, SECRET, opener=server)
    assert lines == [
        unavailable_line("DeepSeek", "The server refused the key (error 401)."),
    ]
    assert lines[0].startswith("DeepSeek: balance not available.")
