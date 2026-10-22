"""The standard input of the ``claude`` process: JSON lines written from several threads."""

import json
import threading
from typing import IO

from wxclaude.core.errors import RunnerError


class ProcessInput:
    """JSON lines written to the process from several threads, closed once."""

    def __init__(self, stream: IO[str] | None) -> None:
        self._stream = stream
        self._lock = threading.Lock()
        self._closed = stream is None

    def write(self, entry: dict[str, object]) -> None:
        """Write ``entry`` as a line; raises ``RunnerError`` if the input is closed or broken."""
        with self._lock:
            if self._closed or self._stream is None:
                raise RunnerError("Claude is not waiting for an answer.")
            try:
                self._stream.write(json.dumps(entry) + "\n")
                self._stream.flush()
            except OSError as error:
                raise RunnerError(f"Claude cannot be reached: {error}") from error

    def close(self) -> None:
        """Close the input (the CLI then ends); harmless the second time or if it is broken."""
        with self._lock:
            if self._closed or self._stream is None:
                return
            self._closed = True
            try:
                self._stream.close()
            except OSError:
                return  # the process is gone: there is nothing left to close
