"""What WxClaude remembers about one workspace: its current conversation, the main agent of
each of its conversations (the name of a conversation is the one of its session, kept by the CLI)
and the alternative agent of the workspace.

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


@dataclass(slots=True)
class WatchRecord:
    """What was approved of one file of the workspace that can change what the CLI does.

    ``sha256`` is the hash of the approved content, empty when the file did not exist.
    """

    watched: bool = True
    sha256: str = ""


def state_file_name(workspace: Path) -> str:
    """The file name for ``workspace``: a 64-bit hash of its lower-case path."""
    digest = hashlib.blake2b(workspace_key(workspace).encode("utf-8"), digest_size=8)
    return f"{digest.hexdigest()}.json"


def _read_watch(value: object) -> dict[str, WatchRecord]:
    """The watch records of a file; an entry that is not well formed is left out."""
    records: dict[str, WatchRecord] = {}
    if not isinstance(value, dict):
        return records
    for path, entry in value.items():
        if not isinstance(entry, dict):
            continue
        sha256 = entry.get("sha256", "")
        if isinstance(sha256, str):
            records[path] = WatchRecord(entry.get("watched") is not False, sha256)
    return records


@dataclass(slots=True)
class WorkspaceState:
    """The memory of a workspace. Without ``store`` it stays in memory."""

    workspace: Path
    current_conversation: str = ""
    conversations: dict[str, ConversationRecord] = field(default_factory=dict)
    trusted: bool = False  # the user trusts the folder (``docs/security.md``)
    approval_asked: bool = False  # the user was offered to approve the folder (and chose)
    existed: bool = False  # the file of the workspace existed: it was used before
    max_turns: int = 0  # limit of turns of a message (``--max-turns``); 0: no limit
    alternative_agent: Agent = field(default_factory=Agent)  # complete once the workspace is opened
    watch: dict[str, WatchRecord] = field(default_factory=dict)  # by path relative to the folder
    store: Path | None = None
    warning: str = ""  # what went wrong while reading the file, for the user

    @property
    def watch_dir(self) -> Path | None:
        """The folder of the approved copies of the watched files, beside the state file."""
        return None if self.store is None else self.store.with_suffix(".watch")

    @classmethod
    def load(cls, workspace: Path, directory: Path | None) -> WorkspaceState:
        """The state of ``workspace`` kept in ``directory`` (None: in memory only)."""
        if directory is None:
            return cls(workspace)
        store = directory / state_file_name(workspace)
        state = cls(workspace, store=store)
        state.existed = store.exists()
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
        state.trusted = data.get("trusted") is True
        state.approval_asked = data.get("approval_asked") is True
        state.watch = _read_watch(data.get("watch"))
        turns = data.get("max_turns")
        if isinstance(turns, int) and not isinstance(turns, bool) and turns > 0:
            state.max_turns = turns
        state.alternative_agent = Agent.from_dict(data.get("alternative_agent"))
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
            "trusted": self.trusted,
            "approval_asked": self.approval_asked,
            "max_turns": self.max_turns,
            "alternative_agent": self.alternative_agent.to_dict(),
            "watch": {
                path: {"watched": record.watched, "sha256": record.sha256}
                for path, record in self.watch.items()
            },
        }
        write_json(self.store, data)

    def start_alternative_agent(self, preferences: Agent, conversation: Agent) -> None:
        """Give the alternative agent the fields it lacks, which is the case of a new workspace.

        A field comes from the alternative agent of the Preferences, and where that one is left on
        "same as the conversation", from ``conversation``. A field already set is kept: from then
        on only the user changes it.
        """
        self.alternative_agent = self.alternative_agent.over(preferences).over(conversation)

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
