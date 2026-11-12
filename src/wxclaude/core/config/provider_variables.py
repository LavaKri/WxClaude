"""The environment variables of the CLI that a provider can set (``docs/providers.md``).

The list is closed on purpose: a free name could redefine the address or the key of the provider and
undo what the launch of WxClaude guarantees. Each value is a whole number above zero; an empty value
means that the variable is not set. A variable is added here, with one line, when it is needed.
"""

from wxclaude.i18n import _

API_TIMEOUT = "API_TIMEOUT_MS"
MAX_CONTEXT = "CLAUDE_CODE_MAX_CONTEXT_TOKENS"
COMPACT_WINDOW = "CLAUDE_CODE_AUTO_COMPACT_WINDOW"
MAX_OUTPUT = "CLAUDE_CODE_MAX_OUTPUT_TOKENS"

#: The variables a provider can set, in the order of the form. They describe the server and its
#: model (the wait, the window of context, the length of an answer); what depends on the folder
#: (the output of a command, the reading of a file) is set in the workspace settings.
PROVIDER_VARIABLES = (API_TIMEOUT, MAX_CONTEXT, COMPACT_WINDOW, MAX_OUTPUT)


def is_valid_value(value: str) -> bool:
    """Is ``value`` a whole number above zero, written with digits only?"""
    return value.isascii() and value.isdigit() and int(value) > 0


def variables_problem(values: dict[str, str]) -> str | None:
    """What is wrong with the variables of a provider for the user, or None."""
    for name in values:
        if name not in PROVIDER_VARIABLES:
            return _("The variable {name} cannot be set by a provider.").format(name=name)
    for name, value in values.items():
        if not is_valid_value(value):
            return _("The value of {name} is a whole number above zero.").format(name=name)
    return None
