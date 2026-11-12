"""The ways to ask a provider for its models and for its credit (``docs/providers.md``).

A provider is data; what WxClaude knows about how to question a service is in these classes. There
are two families, each with a base class that holds what they share: ``ModelsMethod`` (which models
the server offers) and ``CreditMethod`` (what is left of the credit). A method gives only the paths
to ask and how to read the answer; the base class makes the call. The user chooses a method for
each provider (two lists in its form), so a provider can use the method of another service.

The base class sends the key only to the host of the address the user typed: a method gives paths,
never addresses, so it cannot send the key elsewhere. The calls are made on request only, from a
worker thread, and never follow a redirect.
"""

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from http.client import HTTPException
from typing import IO, Any, ClassVar
from urllib.parse import urlsplit

from wxclaude.core.errors import BalanceError, ModelListError, WxClaudeError
from wxclaude.i18n import N_, _

TIMEOUT_SECONDS = 15.0
_ANTHROPIC_VERSION = "2023-06-01"
_MAX_DETAIL = 200
_NOT_FOUND = 404
NONE = "none"  # the identifier of "no method", in both families
DEFAULT_MODELS_METHOD = "v1"
DEFAULT_CREDIT_METHOD = NONE

#: What opens a request: a fake in the tests.
type Opener = Callable[[urllib.request.Request, float], IO[Any]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def default_open(request: urllib.request.Request, timeout: float) -> IO[Any]:
    response: IO[Any] = urllib.request.build_opener(_NoRedirect).open(request, timeout=timeout)
    return response


def origin_of(base_url: str) -> str:
    """The scheme and host of an address (``https://api.example.com``), without a path."""
    parts = urlsplit(base_url.strip())
    return f"{parts.scheme}://{parts.netloc}"


class ProviderMethod(ABC):
    """What the two families share: the call to the server and the messages for its failures.

    A subclass gives ``id``, ``label`` (a message id, shown in the list of the form), ``paths`` and
    the reading of the answer in its family. ``error`` is the exception of the family.
    """

    id: ClassVar[str]
    label: ClassVar[str]
    error: ClassVar[type[WxClaudeError]]
    max_bytes: ClassVar[int] = 1_000_000  # an answer bigger than that is not what was asked
    not_found: ClassVar[str]  # message ids of the failures that depend on the family
    malformed: ClassVar[str]

    @abstractmethod
    def paths(self, base_url: str) -> list[str]:
        """The paths to try, in order, each starting with ``/`` and meant for the host of
        ``base_url``. The next one is tried only after a 404."""

    def headers(self, key: str) -> dict[str, str]:
        """The headers of the call; the key as a bearer token."""
        headers = {"Accept": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def call(
        self,
        base_url: str,
        key: str,
        *,
        opener: Opener = default_open,
        timeout: float = TIMEOUT_SECONDS,
    ) -> object:
        """The JSON document the server answers. Raises ``error`` with a message for the user
        (never holding the key) when it cannot be reached, refuses, or answers something else."""
        origin = origin_of(base_url)
        last: urllib.error.HTTPError | None = None
        for path in self.paths(base_url):
            request = urllib.request.Request(origin + path, headers=self.headers(key), method="GET")
            try:
                with opener(request, timeout) as response:
                    return self._document(response.read(self.max_bytes + 1))
            except urllib.error.HTTPError as error:
                if error.code != _NOT_FOUND:
                    raise self.error(self._error_text(error, key)) from error
                last = error
            except (urllib.error.URLError, HTTPException, OSError, ValueError) as error:
                reason = str(error).replace(key, "***") if key else str(error)
                raise self.error(
                    _("The server cannot be reached: {reason}").format(reason=reason)
                ) from error
        raise self.error(_(self.not_found)) from last

    # -- inside ---------------------------------------------------------------------------

    def _document(self, body: bytes) -> object:
        if len(body) > self.max_bytes:
            raise self.error(_(self.malformed))
        try:
            return json.loads(body.decode("utf-8"))
        except UnicodeDecodeError, json.JSONDecodeError:
            raise self.error(_(self.malformed)) from None

    def _error_text(self, error: urllib.error.HTTPError, key: str) -> str:
        if error.code in (401, 403):
            return _("The server refused the key (error {code}).").format(code=error.code)
        if error.code in (301, 302, 303, 307, 308):
            return _("The server redirects to another address; enter that address instead.")
        return _("The server answered with the error {code}.{detail}").format(
            code=error.code, detail=_detail(error, key, self.max_bytes)
        )


def _detail(error: urllib.error.HTTPError, key: str, limit: int) -> str:
    """The message the server gave, short and without the key, with a space before it; or ''."""
    try:
        data = json.loads(error.read(limit).decode("utf-8"))
    except OSError, ValueError:
        return ""
    node = data.get("error") if isinstance(data, dict) else None
    message = node.get("message") if isinstance(node, dict) else node
    if not isinstance(message, str) or not message.strip():
        return ""
    text = message.strip()[:_MAX_DETAIL]
    return " " + (text.replace(key, "***") if key else text)


# -- the models -------------------------------------------------------------------------------


class ModelsMethod(ProviderMethod):
    """A way to ask which models a server offers."""

    error = ModelListError
    not_found = N_("This server does not offer a list of models (error 404). Type the names.")
    malformed = N_("The server did not answer with a list of models. Type the names.")
    available: ClassVar[bool] = True  # False: nothing can be asked (the check button is greyed)

    @abstractmethod
    def parse(self, data: object) -> list[str]:
        """The model names in the document, each once. Raises ``ModelListError``."""

    def fetch(
        self,
        base_url: str,
        key: str = "",
        *,
        opener: Opener = default_open,
        timeout: float = TIMEOUT_SECONDS,
    ) -> list[str]:
        """The model names the server at ``base_url`` offers, in the order it gives them."""
        return self.parse(self.call(base_url, key, opener=opener, timeout=timeout))


class NoModels(ModelsMethod):
    """No way to ask: the user types the names."""

    id = NONE
    label = N_("No method")
    available = False

    def paths(self, base_url: str) -> list[str]:
        return []

    def parse(self, data: object) -> list[str]:
        return []

    def fetch(
        self,
        base_url: str,
        key: str = "",
        *,
        opener: Opener = default_open,
        timeout: float = TIMEOUT_SECONDS,
    ) -> list[str]:
        raise ModelListError(_("No way to ask the models is chosen for this provider."))


class V1Models(ModelsMethod):
    """``GET /v1/models``, the names in ``data[].id``: the Anthropic API, and the OpenAI format of
    the local servers (LM Studio, Ollama). Some providers keep the list at the root of their host
    (DeepSeek: ``/models`` while the Anthropic API sits under ``/anthropic``): it is tried when the
    path after the address is not found."""

    id = "v1"
    label = N_("V1")

    def paths(self, base_url: str) -> list[str]:
        base = urlsplit(base_url.strip()).path.rstrip("/")
        first = f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"
        return list(dict.fromkeys([first, "/v1/models", "/models"]))

    def headers(self, key: str) -> dict[str, str]:
        headers = super().headers(key)
        headers["anthropic-version"] = _ANTHROPIC_VERSION
        if key:
            headers["x-api-key"] = key  # the Anthropic API wants it, the others the bearer token
        return headers

    def parse(self, data: object) -> list[str]:
        entries = data.get("data") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            raise ModelListError(_(self.malformed))
        names: list[str] = []
        for entry in entries:
            name = entry.get("id") if isinstance(entry, dict) else None
            if isinstance(name, str) and name.strip() and name.strip() not in names:
                names.append(name.strip())
        if not names:
            raise ModelListError(_("The server offers no model."))
        return names


# -- the credit -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Balance:
    """The credit in one currency. ``granted`` is offered by the service, ``topped_up`` is paid."""

    currency: str
    total: str
    granted: str = ""
    topped_up: str = ""


def unavailable_line(name: str, reason: str) -> str:
    """The line that says the credit of the provider ``name`` could not be known."""
    return _("{name}: balance not available. {reason}").format(name=name, reason=reason)


def balance_lines(name: str, balances: list[Balance], *, available: bool = True) -> list[str]:
    """The lines that tell the credit of ``name``, one per currency, for the dialog of the gauge."""
    lines: list[str] = []
    for balance in balances:
        parts = [
            _("{name}: balance {total} {currency}").format(
                name=name, total=balance.total, currency=balance.currency
            )
        ]
        if balance.topped_up:
            parts.append(_("topped up {amount}").format(amount=balance.topped_up))
        if balance.granted:
            parts.append(_("offered {amount}").format(amount=balance.granted))
        lines.append(", ".join(parts) + ".")
    if not available:
        lines.append(_("{name}: the balance is too low to be answered.").format(name=name))
    return lines


class CreditMethod(ProviderMethod):
    """A way to ask what is left of the credit of a provider."""

    error = BalanceError
    not_found = N_("The server does not offer this information (error 404).")
    malformed = N_("The server did not answer with a balance.")
    max_bytes = 100_000
    available: ClassVar[bool] = True  # False: nothing to ask, the provider is not in the gauge

    @abstractmethod
    def parse(self, data: object, name: str) -> list[str]:
        """The lines of the credit of the provider ``name``. Raises ``BalanceError``."""

    def credit(
        self,
        name: str,
        base_url: str,
        key: str,
        *,
        opener: Opener = default_open,
        timeout: float = TIMEOUT_SECONDS,
    ) -> list[str]:
        """The lines of the credit; raises ``BalanceError`` with a message for the user."""
        return self.parse(self.call(base_url, key, opener=opener, timeout=timeout), name)

    def lines(
        self,
        name: str,
        base_url: str,
        key: str,
        *,
        opener: Opener = default_open,
        timeout: float = TIMEOUT_SECONDS,
    ) -> list[str]:
        """The lines to add to the dialog of the gauge; a failure is a line too, never an error."""
        try:
            return self.credit(name, base_url, key, opener=opener, timeout=timeout)
        except BalanceError as error:
            return [unavailable_line(name, str(error))]


class NoCredit(CreditMethod):
    """No way to ask: the provider is not in the gauge."""

    id = NONE
    label = N_("No method")
    available = False

    def paths(self, base_url: str) -> list[str]:
        return []

    def parse(self, data: object, name: str) -> list[str]:
        return []

    def credit(
        self,
        name: str,
        base_url: str,
        key: str,
        *,
        opener: Opener = default_open,
        timeout: float = TIMEOUT_SECONDS,
    ) -> list[str]:
        return []


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


class DeepSeekCredit(CreditMethod):
    """``GET /user/balance`` on the host of the provider: ``{"is_available": true,
    "balance_infos": [{"currency", "total_balance", "granted_balance", "topped_up_balance"}]}``."""

    id = "deepseek"
    label = N_("DeepSeek")

    def paths(self, base_url: str) -> list[str]:
        return ["/user/balance"]

    def parse(self, data: object, name: str) -> list[str]:
        infos = data.get("balance_infos") if isinstance(data, dict) else None
        if not isinstance(infos, list):
            raise BalanceError(_(self.malformed))
        balances = [
            Balance(
                _text(info.get("currency")),
                _text(info.get("total_balance")),
                _text(info.get("granted_balance")),
                _text(info.get("topped_up_balance")),
            )
            for info in infos
            if isinstance(info, dict) and _text(info.get("total_balance"))
        ]
        if not balances:
            raise BalanceError(_(self.malformed))
        available = data.get("is_available") if isinstance(data, dict) else None
        return balance_lines(name, balances, available=available is not False)


# -- the registries ---------------------------------------------------------------------------

#: The methods, in the order of the lists of the form. A method is added here.
MODELS_METHODS: tuple[ModelsMethod, ...] = (NoModels(), V1Models())
CREDIT_METHODS: tuple[CreditMethod, ...] = (NoCredit(), DeepSeekCredit())


def models_method(identifier: str) -> ModelsMethod:
    """The method named ``identifier``; "no method" when it is not known."""
    return next((m for m in MODELS_METHODS if m.id == identifier), MODELS_METHODS[0])


def credit_method(identifier: str) -> CreditMethod:
    """The method named ``identifier``; "no method" when it is not known."""
    return next((m for m in CREDIT_METHODS if m.id == identifier), CREDIT_METHODS[0])
