"""Which names look like a credential or redirect the traffic, and how a secret is masked.

One rule for the copies of the watched files and for the tab *Environment variables*. A name is cut
into words (``ANTHROPIC_AUTH_TOKEN`` gives ``ANTHROPIC``, ``AUTH``, ``TOKEN``; ``apiKey`` gives
``API``, ``KEY``) and the words are compared as wholes, so ``MAX_OUTPUT_TOKENS`` or ``KEYBOARD`` are
not taken for a credential. The lists are the constants below: they are meant to be edited.
"""

import hashlib
import json
import re
from itertools import pairwise

# A word of this list makes the name a credential.
CREDENTIAL_WORDS = frozenset(
    {
        "KEY",
        "APIKEY",
        "TOKEN",
        "SECRET",
        "SECRETS",
        "PASSWORD",
        "PASSWORDS",
        "PASSWD",
        "PWD",
        "CREDENTIAL",
        "CREDENTIALS",
        "AUTH",
        "AUTHORIZATION",
        "BEARER",
        "COOKIE",
        "DSN",
    }
)

# A word of this list makes the name a setting that sends the traffic somewhere else (``BASE_URL``
# is the two words ``BASE`` and ``URL`` next to each other, see ``_REDIRECT_PAIRS``).
REDIRECT_WORDS = frozenset(
    {
        "PROXY",
        "ENDPOINT",
        "CERT",
        "CERTS",
        "CERTIFICATE",
        "CERTIFICATES",
        "TLS",
        "SSL",
        "BEDROCK",
        "VERTEX",
        "FOUNDRY",
    }
)
_REDIRECT_PAIRS = frozenset({("BASE", "URL"), ("CA", "BUNDLE"), ("CA", "CERTS")})

# A name with one of these words holds a command the CLI runs (``apiKeyHelper``, ``awsAuthRefresh``,
# ``awsCredentialExport``), not a secret: its content matters more than hiding it, so it is shown.
_COMMAND_WORDS = frozenset({"HELPER", "REFRESH", "EXPORT"})

_WORD_BOUNDARY = re.compile(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_HASH_LENGTH = 16

_URL = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*)://(?P<authority>[^/?#]*)(?P<rest>.*)", re.DOTALL
)
_SPACE = re.compile(r"\s")
# A host name, an IPv4 address or an IPv6 address in brackets, then an optional port.
_HOST = re.compile(r"(?:\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9._-]+)(?::[0-9]{1,5})?")


def name_words(name: str) -> list[str]:
    """The words of ``name`` in upper case, cut at separators and at the humps of camel case."""
    return [word.upper() for word in _WORD_BOUNDARY.split(name) if word]


def is_credential_name(name: str) -> bool:
    """Whether the value of ``name`` is probably a secret (``ANTHROPIC_AUTH_TOKEN``, ``apiKey``)."""
    words = name_words(name)
    if _COMMAND_WORDS.intersection(words):
        return False
    return bool(CREDENTIAL_WORDS.intersection(words))


def redirects_traffic(name: str) -> bool:
    """Whether ``name`` sets where the traffic goes (``ANTHROPIC_BASE_URL``, ``HTTPS_PROXY``)."""
    words = name_words(name)
    if REDIRECT_WORDS.intersection(words):
        return True
    return any(pair in _REDIRECT_PAIRS for pair in pairwise(words))


def is_sensitive_name(name: str) -> bool:
    """Whether ``name`` is a credential or redirects the traffic: the tab marks it *sensitive*."""
    return is_credential_name(name) or redirects_traffic(name)


def masked_value(value: object) -> str:
    """What stands for ``value`` in a copy: a short hash, equal for equal values.

    Two copies tell whether the value changed without holding it.
    """
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:_HASH_LENGTH]}"


def mask_url(value: str) -> str:
    """``value`` with all of an URL hidden but its scheme, host and port; other text is unchanged.

    What follows the host (user and password, path, query, fragment) may hold a secret in a form
    nobody can list (a token in the path of a webhook, a user that is a token), so it is replaced
    whole by the hash of the value: ``postgres://db.example.com:5432/sha256:0123456789abcdef``. A
    change anywhere in the URL changes the hash, and a change of host stays readable. An URL with
    nothing to hide (``http://127.0.0.1:1234``) is kept as it is; one whose host cannot be read is
    hidden whole. A text with spaces (a command) is not an URL and is not touched.
    """
    match = _URL.match(value)
    if match is None or _SPACE.search(value):
        return value
    scheme, authority, rest = match["scheme"], match["authority"], match["rest"]
    host = authority.rpartition("@")[2]
    # An ``@`` after the authority is a password with a raw ``/``, ``?`` or ``#`` in it: the host
    # found above would be a piece of the password.
    if "@" in rest or _HOST.fullmatch(host) is None:
        return masked_value(value)
    if host == authority and rest in ("", "/"):
        return value
    return f"{scheme}://{host}/{masked_value(value)}"


def mask_secrets(data: object) -> object:
    """A copy of parsed JSON where the secrets are replaced by their hash.

    The keys are looked at at every depth and in lists of objects; the value under a credential key
    is replaced whole, whatever its type, and a text that is an URL goes through ``mask_url``.
    ``data`` is not changed.
    """
    if isinstance(data, str):
        return mask_url(data)
    if isinstance(data, dict):
        return {
            key: masked_value(value)
            if isinstance(key, str) and is_credential_name(key)
            else mask_secrets(value)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [mask_secrets(item) for item in data]
    return data


def mask_json_text(text: str) -> str | None:
    """``text`` as JSON with its secrets masked, or ``None`` if it is not JSON.

    The caller decides what a text that is not JSON becomes (a copy as it is, for a file of
    Markdown; no copy of the content for a ``.json`` file that cannot be read, as it may hold a
    secret).
    """
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return json.dumps(mask_secrets(data), indent=2, ensure_ascii=False) + "\n"
