"""The ways messages can be sent to a screen reader (Preferences > Announcements).

An output only names a method and the platforms it works on; the code that really sends the
message is in ``ui/message_sinks.py``.
"""

import sys
from dataclasses import dataclass

from wxclaude.i18n import N_


@dataclass(frozen=True, slots=True)
class Output:
    """A way to send messages to the screen reader; ``label`` is a message id.

    ``platforms`` are the ``sys.platform`` values it works on; empty means everywhere.
    """

    id: str
    label: str
    platforms: tuple[str, ...] = ()

    def available_on(self, platform: str) -> bool:
        """Does this output work on ``platform``?"""
        return not self.platforms or platform in self.platforms


NONE = Output("none", N_("No output"))
UIA = Output("uia", N_("UI Automation (Windows)"), ("win32",))

#: Every output, in the order of the list in the options ("No output" first).
OUTPUTS = (NONE, UIA)


def available_outputs(platform: str = sys.platform) -> tuple[Output, ...]:
    """The outputs that work on ``platform``."""
    return tuple(output for output in OUTPUTS if output.available_on(platform))


def default_output(platform: str = sys.platform) -> Output:
    """The output used until the user chooses one: UI Automation on Windows, none elsewhere."""
    return UIA if UIA.available_on(platform) else NONE


def output_named(output_id: str, platform: str = sys.platform) -> Output | None:
    """The output with this id if it exists and works on ``platform``."""
    return next((o for o in available_outputs(platform) if o.id == output_id), None)
