"""A view of the security presenter for the tests: answers the offer and the alert with what the
test set, and records what was shown and said."""

from pathlib import Path

from wxclaude.core.list_spec import ListSpec
from wxclaude.core.speech.announcements import Announce
from wxclaude.presenters.security_presenter import AlertChoice, ApprovalChoice


class FakeView:
    """Answers the offer and the alert with what the test set; records what was said."""

    def __init__(
        self,
        approval: ApprovalChoice = ApprovalChoice.KEEP_RESTRICTED,
        alert: AlertChoice | None = None,
    ) -> None:
        self.approval = approval
        self.alert = alert
        self.offers: list[tuple[Path, bool, list[str]]] = []
        self.alerts: list[ListSpec] = []
        self.said: list[tuple[Announce, dict[str, object]]] = []
        self.errors: list[str] = []

    def ask_approval(self, folder: Path, used_before: bool, files: list[str]) -> ApprovalChoice:
        self.offers.append((folder, used_before, files))
        return self.approval

    def show_alert(self, spec: ListSpec) -> AlertChoice | None:
        self.alerts.append(spec)
        return self.alert

    def say(self, announce: Announce, **values: object) -> None:
        self.said.append((announce, values))

    def show_error(self, message: str) -> None:
        self.errors.append(message)

    @property
    def announces(self) -> list[Announce]:
        return [announce for announce, _values in self.said]
