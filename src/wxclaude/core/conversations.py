"""Identifiers and names of conversations.

A conversation is a session of the Claude Code CLI. Its identifier is a UUID that the application
chooses when the conversation is created (``--session-id``), then gives back to resume it.
"""

import uuid

from wxclaude.i18n import _


def new_conversation_id() -> str:
    """A new identifier for a conversation."""
    return str(uuid.uuid4())


def is_conversation_id(text: object) -> bool:
    """Is ``text`` the written form of a conversation identifier?"""
    if not isinstance(text, str):
        return False
    try:
        return str(uuid.UUID(text)) == text.lower()
    except ValueError:
        return False


def default_name(number: int) -> str:
    """The name proposed for the conversation number ``number`` (``Conversation 3``)."""
    return _("Conversation {number}").format(number=number)


def branch_name(parent_name: str, number: int) -> str:
    """The name proposed for the ``number``-th branch of ``parent_name``."""
    return _("{name} branch {number}").format(name=parent_name, number=number)
