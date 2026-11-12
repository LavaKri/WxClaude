"""AI providers: where a message can be sent, and the key to use there (``docs/providers.md``).

The built-in provider ``claude`` adds nothing to the launch of the CLI, cannot be changed or deleted
and is the default. The others are defined once for the application and kept in ``providers.json``
next to ``settings.json``. The key of a provider is kept there encrypted by a ``KeyVault``, never in
clear and never in ``settings.json``.
"""

import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from wxclaude.core.config.agents import DEFAULT_PROVIDER, MODELS
from wxclaude.core.config.jsonstore import read_json, write_json
from wxclaude.core.config.provider_methods import DEFAULT_CREDIT_METHOD, DEFAULT_MODELS_METHOD
from wxclaude.core.config.provider_variables import PROVIDER_VARIABLES, variables_problem
from wxclaude.core.errors import KeyVaultError, ProviderError
from wxclaude.core.security.vault import KeyVault
from wxclaude.i18n import _

CLAUDE_ID = DEFAULT_PROVIDER
KEY_STORED = "stored"  # the key is kept encrypted by WxClaude
KEY_NONE = "none"  # a local server that needs no key: a placeholder is given to the CLI
KEY_SOURCES = (KEY_STORED, KEY_NONE)
ALIASES = ("haiku", "sonnet", "opus")  # the models the CLI lets a provider answer to
TIER_COUNT = len(MODELS)  # small, medium, large, largest: the same ranks as the models of Claude
NAME_MAX = 15  # characters in the name of a provider
MODEL_MAX = 64  # characters in a model name (an identifier sent to the server: never cut)
_URL_SCHEMES = ("http://", "https://")
_SLUG = re.compile(r"[^a-z0-9]+")


def fill_tiers(entries: list[str]) -> list[str]:
    """The four model names of a provider, none empty: each empty one takes the weakest model
    given (the first filled in the order small to largest). No name at all gives an empty list."""
    names = [entry.strip() for entry in entries[:TIER_COUNT]]
    names += [""] * (TIER_COUNT - len(names))
    weakest = next((name for name in names if name), "")
    return [name or weakest for name in names] if weakest else []


@dataclass(slots=True)
class Provider:
    """One provider. ``tiers`` holds its model names from the smallest to the largest (four, none
    empty, a name may come more than once); they are sent to the server as they are. The first three
    answer to the names ``haiku``, ``sonnet`` and ``opus`` that the CLI may ask for by itself."""

    id: str
    name: str
    base_url: str = ""
    key_source: str = KEY_STORED
    tiers: list[str] = field(default_factory=list)
    send_effort: bool = True
    models_method: str = DEFAULT_MODELS_METHOD  # how to ask the models (``provider_methods``)
    credit_method: str = DEFAULT_CREDIT_METHOD  # how to ask the credit (``provider_methods``)
    #: The variables of the CLI this provider sets (``provider_variables``): name -> value.
    env: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.tiers = fill_tiers(self.tiers)
        self.env = {name: value.strip() for name, value in self.env.items() if value.strip()}

    @property
    def models(self) -> list[str]:
        """The models to choose from, each once, from the smallest to the largest."""
        return list(dict.fromkeys(self.tiers))

    @property
    def aliases(self) -> dict[str, str]:
        """The model each of ``haiku``, ``sonnet`` and ``opus`` stands for."""
        return dict(zip(ALIASES, self.tiers, strict=False))

    @property
    def is_builtin(self) -> bool:
        """Is this Claude, which adds nothing to the launch?"""
        return self.id == CLAUDE_ID

    @property
    def needs_key(self) -> bool:
        """Does the CLI need a key for this provider?"""
        return not self.is_builtin and self.key_source == KEY_STORED

    def problem(self) -> str | None:
        """What is wrong with the provider for the user, or None. Claude is always valid."""
        if self.is_builtin:
            return None
        if not self.name.strip():
            return _("A provider needs a name.")
        if len(self.name.strip()) > NAME_MAX:
            return _("The name of a provider has at most {limit} characters.").format(
                limit=NAME_MAX
            )
        if not self.base_url.startswith(_URL_SCHEMES) or " " in self.base_url:
            return _("The address of a provider starts with http:// or https://.")
        return self._models_problem() or variables_problem(self.env)

    def _models_problem(self) -> str | None:
        if not self.tiers:
            return _("A provider needs at least one model.")
        if any(len(model) > MODEL_MAX for model in self.tiers):
            return _("A model name has at most {limit} characters.").format(limit=MODEL_MAX)
        return None

    def to_dict(self) -> dict[str, object]:
        """The provider as written in ``providers.json`` (without its key)."""
        return {
            "id": self.id,
            "name": self.name,
            "base_url": self.base_url,
            "key_source": self.key_source,
            "tiers": list(self.tiers),
            "send_effort": self.send_effort,
            "models_method": self.models_method,
            "credit_method": self.credit_method,
            "env": dict(self.env),
        }

    @classmethod
    def from_dict(cls, data: object) -> Provider | None:
        """A provider from JSON data; None if it has no usable id or name. A file written before
        the four ranks (a list ``models``) gives its first four models as ranks."""
        if not isinstance(data, dict):
            return None
        identifier, name = data.get("id"), data.get("name")
        if not (isinstance(identifier, str) and identifier and isinstance(name, str) and name):
            return None
        source = data.get("key_source")
        tiers = data.get("tiers") if isinstance(data.get("tiers"), list) else data.get("models")
        base_url = data.get("base_url")
        models_method, credit_method = data.get("models_method"), data.get("credit_method")
        return cls(
            id=identifier,
            name=name,
            base_url=base_url if isinstance(base_url, str) else "",
            key_source=source if source in KEY_SOURCES else KEY_STORED,
            tiers=_names(tiers) if isinstance(tiers, list) else [],
            send_effort=data.get("send_effort") is not False,
            models_method=_text(models_method, DEFAULT_MODELS_METHOD),
            credit_method=_text(credit_method, DEFAULT_CREDIT_METHOD),
            env=_variables(data.get("env")),
        )


def _text(value: object, default: str) -> str:
    return value if isinstance(value, str) else default


def _variables(value: object) -> dict[str, str]:
    """The variables of a file: only the known names (``provider_variables``) with a text value; a
    file edited by hand cannot make a provider set another variable."""
    if not isinstance(value, dict):
        return {}
    return {name: text for name in PROVIDER_VARIABLES if isinstance(text := value.get(name), str)}


def _names(values: list[object]) -> list[str]:
    """The texts of a list, in order; anything else counts as an empty name."""
    return [value.strip() if isinstance(value, str) else "" for value in values]


#: The built-in provider.
CLAUDE = Provider(id=CLAUDE_ID, name="Claude", key_source=KEY_NONE, tiers=list(MODELS))


#: The providers a user who has none yet starts with. DeepSeek needs a key (to add in the page
#: Providers); Ollama is a local server without one. Both were tried (``docs/providers.md``): the
#: names of the models are the ones the servers gave, the user changes them in the form.
DEFAULT_PROVIDERS: tuple[Provider, ...] = (
    Provider(
        id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com/anthropic",
        tiers=["deepseek-v4-flash", "deepseek-v4-flash", "deepseek-v4-pro", "deepseek-v4-pro"],
        credit_method="deepseek",
    ),
    Provider(
        id="ollama",
        name="Ollama",
        base_url="http://localhost:11434",
        key_source=KEY_NONE,
        tiers=["qwen3:4b"],
    ),
)


def new_provider_id(name: str, taken: set[str]) -> str:
    """A stable identifier made from ``name`` (``My server`` gives ``my-server``), not in ``taken``
    and never ``claude``."""
    base = _SLUG.sub("-", name.lower()).strip("-") or "provider"
    identifier, number = base, 1
    while identifier in taken or identifier == CLAUDE_ID:
        number += 1
        identifier = f"{base}-{number}"
    return identifier


class ProviderStore:
    """The providers of the user and their keys. Without ``path`` they stay in memory."""

    def __init__(self, vault: KeyVault, path: Path | None = None) -> None:
        self._vault = vault
        self._path = path
        self._providers: dict[str, Provider] = {}
        self._keys: dict[str, str] = {}  # the encrypted key by provider id
        self.warning = ""  # what went wrong while reading the file, for the user

    @classmethod
    def load(cls, path: Path | None, vault: KeyVault) -> ProviderStore:
        """Read ``providers.json``; a damaged file is set aside and the file's backup, else
        only Claude, is used (``warning`` says it). Without a file (the first start) the user
        starts with ``DEFAULT_PROVIDERS``; once a file exists, what it holds is all there is, so a
        provider that was deleted does not come back."""
        store = cls(vault, path)
        if path is None:
            return store
        first_start = not path.exists()
        result = read_json(path)
        store.warning = result.warning
        if first_start and not result.warning:
            for default in DEFAULT_PROVIDERS:
                store._providers[default.id] = replace(default)
            return store
        entries = result.data.get("providers") if result.data else None
        for entry in entries if isinstance(entries, list) else []:
            provider = Provider.from_dict(entry)
            if provider is None or provider.is_builtin or provider.id in store._providers:
                continue
            store._providers[provider.id] = provider
            key = entry.get("key") if isinstance(entry, dict) else None
            if isinstance(key, str) and key:
                store._keys[provider.id] = key
        return store

    def save(self) -> None:
        """Write the file; raises ``JsonStoreError``. Nothing is written without a path."""
        if self._path is None:
            return
        entries: list[dict[str, object]] = []
        for provider in self._providers.values():
            entry = provider.to_dict()
            if provider.id in self._keys:
                entry["key"] = self._keys[provider.id]
            entries.append(entry)
        write_json(self._path, {"providers": entries})

    # -- the providers --------------------------------------------------------------------

    def providers(self) -> list[Provider]:
        """Claude first, then the providers of the user in the order they were added."""
        return [CLAUDE, *self._providers.values()]

    def get(self, identifier: str | None) -> Provider:
        """The provider ``identifier``; Claude when it is not set or no longer exists."""
        return self._providers.get(identifier or "", CLAUDE)

    def add(self, provider: Provider) -> None:
        """Add a provider; raises ``ProviderError`` if it is not valid or its id is taken."""
        if provider.is_builtin or provider.id in self._providers:
            raise ProviderError(_("The provider {name} already exists.").format(name=provider.name))
        self._check(provider)
        self._providers[provider.id] = replace(provider)

    def update(self, provider: Provider) -> None:
        """Replace the provider of the same id; raises ``ProviderError``."""
        if provider.is_builtin:
            raise ProviderError(_("Claude cannot be changed."))
        if provider.id not in self._providers:
            raise ProviderError(_("The provider {name} does not exist.").format(name=provider.name))
        self._check(provider)
        self._providers[provider.id] = replace(provider)

    def remove(self, identifier: str) -> None:
        """Delete a provider and its key; raises ``ProviderError`` for Claude or an unknown one."""
        if identifier == CLAUDE_ID:
            raise ProviderError(_("Claude cannot be deleted."))
        if identifier not in self._providers:
            raise ProviderError(_("The provider {name} does not exist.").format(name=identifier))
        del self._providers[identifier]
        self._keys.pop(identifier, None)

    def _check(self, provider: Provider) -> None:
        problem = provider.problem()
        if problem is not None:
            raise ProviderError(problem)

    # -- the keys -------------------------------------------------------------------------

    def has_key(self, identifier: str) -> bool:
        """Is a key saved for this provider?"""
        return identifier in self._keys

    def set_key(self, identifier: str, secret: str) -> None:
        """Encrypt and keep the key of a provider; raises ``ProviderError`` or ``KeyVaultError``."""
        if identifier not in self._providers:
            raise ProviderError(_("The provider {name} does not exist.").format(name=identifier))
        if not secret.strip():
            raise ProviderError(_("The key is empty."))
        self._keys[identifier] = self._vault.encrypt(secret.strip())

    def remove_key(self, identifier: str) -> None:
        """Forget the key of a provider (nothing happens if it has none)."""
        self._keys.pop(identifier, None)

    def key(self, identifier: str) -> str:
        """The key of a provider in clear, for the environment of one launch only.

        Raises ``ProviderError`` if none is saved and ``KeyVaultError`` (with a message for the
        user) if it cannot be decrypted here.
        """
        blob = self._keys.get(identifier)
        if blob is None:
            raise ProviderError(
                _("No key is saved for {name}.").format(name=self.get(identifier).name)
            )
        try:
            return self._vault.decrypt(blob)
        except KeyVaultError as error:
            raise KeyVaultError(
                _(
                    "The key of {name} cannot be read. It was saved by another Windows account or "
                    "on another computer: enter it again."
                ).format(name=self.get(identifier).name)
            ) from error
