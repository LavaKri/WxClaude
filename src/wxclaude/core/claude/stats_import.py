"""Counting the conversations that already exist when the statistics of a workspace start.

The totals of each session are read in its file (``cost_state.py``). Two things make a sum of the
sessions too big, and both are corrected here as far as the files allow:

- A branch (``--fork-session``) copies the first messages of another session and starts its totals
  from the ones of that session. It is told by the copied messages (the same identifiers) and by
  having no totals of its own among them; what the other session had reached at the end of the
  copied messages is taken away from the branch, and the copied messages are not counted again.
- A conversation that was deleted, or removed by the CLI after 30 days, is no longer there: the
  result is a minimum, which the statistics say.
"""

from collections.abc import Sequence

from wxclaude.core.claude.cost_state import CostState
from wxclaude.core.claude.session_reader import Session
from wxclaude.core.config.workspace_stats import WorkspaceStats
from wxclaude.core.conversation.conversations import is_conversation_id
from wxclaude.core.conversation.messages import Role


def _identifiers(session: Session) -> list[str]:
    """The identifiers of the messages that come from the file (the others are numbered)."""
    return [m.id if is_conversation_id(m.id) else "" for m in session.messages]


def _common_prefix(first: list[str], second: list[str]) -> int:
    count = 0
    for one, other in zip(first, second, strict=False):
        if not one or one != other:
            break
        count += 1
    return count


def _state_at(session: Session, messages: int) -> CostState | None:
    """The last totals written within the first ``messages`` messages of ``session``."""
    found = [state for state in session.cost_states if state.after_messages <= messages]
    return found[-1] if found else None


def _copied(session: Session, others: Sequence[Session]) -> tuple[int, CostState | None]:
    """How many messages ``session`` copies from another one, and what that session had reached.

    (0, None) when it is not a branch.
    """
    identifiers = _identifiers(session)
    best, candidates = 0, []
    for other in others:
        shared = _common_prefix(identifiers, _identifiers(other))
        if shared > best:
            best, candidates = shared, [other]
        elif shared == best and shared:
            candidates.append(other)
    if not best or any(state.after_messages <= best for state in session.cost_states):
        return 0, None  # nothing shared, or totals of its own among the shared messages
    # The conversation it comes from has totals within them; its siblings (other branches) do not.
    states = [state for other in candidates if (state := _state_at(other, best)) is not None]
    if not states:
        return 0, None
    return best, min(states, key=lambda state: state.cost)


def _models_of_prompts(session: Session, skip: int) -> tuple[int, dict[str, int]]:
    """The number of prompts of the user after the first ``skip`` messages, and by model of the
    answer that follows each."""
    prompts = 0
    by_model: dict[str, int] = {}
    waiting = False
    for message in session.messages[skip:]:
        if message.role is Role.USER and not message.hidden:
            prompts += 1
            waiting = True
        elif message.role is Role.ASSISTANT and waiting and message.model:
            by_model[message.model] = by_model.get(message.model, 0) + 1
            waiting = False
    return prompts, by_model


def _add_session(
    stats: WorkspaceStats, conversation_id: str, session: Session, others: Sequence[Session]
) -> None:
    skip, earlier = _copied(session, others)
    prompts, by_model = _models_of_prompts(session, skip)
    final = session.cost_states[-1] if session.cost_states else None
    if not prompts and final is None:
        return
    stats.add_conversation(conversation_id)
    stats.messages += prompts
    for model, count in by_model.items():
        stats.add_model(model, count, 0.0)
    if final is None:
        return
    own = final.minus(earlier) if earlier is not None else final
    stats.add_tokens(own.tokens())
    stats.activity_ms += own.activity_ms
    stats.cost += own.cost
    for model, totals in own.models.items():
        stats.add_model(model, 0, totals.cost)


def import_sessions(
    workspace_stats: WorkspaceStats, sessions: Sequence[tuple[str, Session]]
) -> None:
    """Add the conversations that exist (identifier and session) to ``workspace_stats``."""
    everything = [session for _id, session in sessions]
    for conversation_id, session in sessions:
        others = [other for other in everything if other is not session]
        _add_session(workspace_stats, conversation_id, session, others)
    days = sorted(session.started[:10] for session in everything if session.started)
    if days and workspace_stats.messages:
        workspace_stats.started = days[0]
    workspace_stats.includes_past = workspace_stats.messages > 0
