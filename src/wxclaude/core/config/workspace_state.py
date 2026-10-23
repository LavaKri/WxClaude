"""What WxClaude remembers about one workspace: its current conversation, and the main agent of
each of its conversations (the name of a conversation is the one of its session, kept by the CLI).

One file per workspace, ``workspaces/<hash>.json`` next to ``settings.json``. The hash is made of
the lower-case path; the path itself is written in the file and checked when reading, so two paths
that would share a name are never mixed up.
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from wxclaude.core.config.agents import Agent
from wxclaude.core.config.jsonstore import read_json, write_json
from wxclaude.core.config.settings import workspace_key


@dataclass(slots=True)
class ConversationRecord:
    """The main agent of a conversation (never the alternative agent)."""

    agent: Agent


def state_file_name(workspace: Path) -> str:
    """The file name for ``workspace``: a 64-bit hash of its lower-case path."""
    digest = hashlib.blake2b(workspace_key(workspace).encode("utf-8"), digest_size=8)
    return f"{digest.hexdigest()}.json"


@dataclass(slots=True)
class WorkspaceState:
    """The memory of a workspace. Without ``store`` it stays in memory."""

    workspace: Path
    current_conversation: str = ""
    conversations: dict[str, ConversationRecord] = field(default_factory=dict)
    store: Path | None = None
    warning: str = ""  # what went wrong while reading the file, for the user

    @classmethod
    def load(cls, workspace: Path, directory: Path | None) -> WorkspaceState:
        """The state of ``workspace`` kept in ``directory`` (None: in memory only)."""
        if directory is None:
            return cls(workspace)
        store = directory / state_file_name(workspace)
        state = cls(workspace, store=store)
        result = read_json(store)
        state.warning = result.warning
        data = result.data
        if data is None:
            return state
        if str(data.get("workspace", "")).lower() != workspace_key(workspace):
            state.warning = f"The file {store} belongs to another workspace and was not used."
            return state
        current = data.get("current_conversation")
        if isinstance(current, str):
            state.current_conversation = current
        records = data.get("conversations")
        if isinstance(records, dict):
            for key, value in records.items():
                if isinstance(value, dict):
                    state.conversations[key] = ConversationRecord(
                        Agent.from_dict(value.get("agent"))
                    )
        return state

    def save(self) -> None:
        """Write the state; raises ``JsonStoreError``. Nothing is written without a store."""
        if self.store is None:
            return
        data: dict[str, object] = {
            "workspace": str(self.workspace),
            "current_conversation": self.current_conversation,
            "conversations": {
                key: {"agent": record.agent.to_dict()} for key, record in self.conversations.items()
            },
        }
        write_json(self.store, data)

    def remember(self, conversation_id: str, agent: Agent) -> None:
        """Remember the main agent of a conversation, and that it is the current one."""
        self.current_conversation = conversation_id
        self.conversations[conversation_id] = ConversationRecord(agent)

    def forget_missing(self, existing_ids: set[str]) -> None:
        """Drop the conversations whose session file no longer exists."""
        for key in [key for key in self.conversations if key not in existing_ids]:
            del self.conversations[key]
        if self.current_conversation not in existing_ids:
            self.current_conversation = ""
