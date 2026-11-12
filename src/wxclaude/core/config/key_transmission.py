"""How the key of a provider reaches the CLI: the choice of the user (``docs/providers.md``).

*Masked* leaves the key in the environment of the CLI but asks it to hide it from the commands that
Claude runs (``CLAUDE_CODE_SUBPROCESS_ENV_SCRUB``); the CLI then forces the permission mode to
manual. *Shared* leaves it in that environment: every mode works, but the commands can read the
key. *Relayed* keeps the key in WxClaude: the CLI gets a throw-away token and the address of a local
relay (``core/security/key_relay.py``) that adds the key when it forwards each request.
"""

from wxclaude.i18n import N_

MASKED = "masked"
SHARED = "shared"
RELAYED = "relayed"
CHOICES = (MASKED, SHARED, RELAYED)
DEFAULT = MASKED

LABELS = {
    MASKED: N_("Masked"),
    SHARED: N_("Shared"),
    RELAYED: N_("Relayed"),
}

EXPLANATIONS = {
    MASKED: N_(
        "The application sends the key to Claude Code, but Claude Code hides it from its models "
        "and tools.\n"
        "In return, Claude Code forces the permission mode to manual.\n"
        "The modes Plan, Accept edits, Auto and Don't ask are therefore not applied and every "
        "question is asked."
    ),
    SHARED: N_(
        "The application shares the key in the environment of Claude Code.\n"
        "Warning: the key is visible to all the models and tools, so it may end up in messages "
        "or exports.\n"
        "This method is therefore rather meant for tests."
    ),
    RELAYED: N_(
        "The application does not give the key to Claude Code.\n"
        "In this mode, Claude Code only receives a throw-away token and its requests go through "
        "a relay.\n"
        "\n"
        "The relay replaces the tokens with the key in each request forwarded to the provider.\n"
        "It starts on demand and keeps no trace of the exchanges."
    ),
}


def from_legacy_scrub(scrub: bool) -> str:
    """The choice that stands for the old setting ``scrub_credentials``."""
    return MASKED if scrub else SHARED
