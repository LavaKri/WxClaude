"""Log file of the application: set-up, start-up report and uncaught errors.

The application has no console, so everything that goes wrong must end up in a file. The file sits
with the other data files of WxClaude. Errors that nobody caught (main thread, worker threads,
native crashes) are written there too.
"""

import ctypes
import faulthandler
import logging
import os
import platform
import sys
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import IO

from wxclaude import __version__

LOG_FILE_NAME = "wxclaude.log"
CRASH_FILE_NAME = "wxclaude-crash.log"
LOG_LEVELS = ("debug", "info", "error")
DEFAULT_LOG_LEVEL = "info"
MAX_LOG_BYTES = 1_000_000
LOG_BACKUPS = 2
ENCODING = "utf-8"

logger = logging.getLogger("wxclaude")
LINE_FORMAT = "%(asctime)s %(levelname)-8s %(threadName)s %(message)s"
_crash_file: IO[str] | None = None  # faulthandler needs the file to stay open
_handler: RotatingFileHandler | None = None


class _MemoryStatus(ctypes.Structure):
    """The ``MEMORYSTATUSEX`` structure of Windows."""

    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def total_memory_gib() -> float | None:
    """Installed physical memory in GiB, or None when the system does not say."""
    if sys.platform != "win32":
        return None
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(_MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined,unused-ignore]
        return None
    return float(status.ullTotalPhys) / 1024**3


def startup_report(
    started: datetime, executable: Path, config_dir: Path, log_level: str
) -> list[str]:
    """The lines written at the top of the log, grouped by subject."""
    memory = total_memory_gib()
    memory_text = "unknown" if memory is None else f"{memory:.1f} GiB"
    return [
        "=== WxClaude start ===",
        f"Started:       {started.isoformat(timespec='seconds')}",
        f"Log level:     {log_level}",
        "--- Application ---",
        f"Version:       {__version__}",
        f"Launched from: {executable}",
        f"Mode:          {'packaged' if getattr(sys, 'frozen', False) else 'from source'}",
        f"Python:        {platform.python_version()} ({platform.architecture()[0]})",
        "--- System ---",
        f"OS:            {platform.platform()} (build {platform.version()})",
        f"Machine:       {platform.machine()}",
        f"Processor:     {platform.processor() or 'unknown'}",
        f"Logical CPUs:  {os.cpu_count()}",
        f"Memory:        {memory_text}",
        "--- Folders ---",
        f"Preferences:   {config_dir}",
        "===",
    ]


def _log_uncaught(
    kind: type[BaseException], value: BaseException, trace: TracebackType | None
) -> None:
    """``sys.excepthook``: write the error of the main thread to the log."""
    logger.critical("Uncaught error in the main thread", exc_info=(kind, value, trace))


def _log_uncaught_thread(args: threading.ExceptHookArgs) -> None:
    """``threading.excepthook``: write the error of a worker thread to the log."""
    name = args.thread.name if args.thread else "unknown"
    if args.exc_type is SystemExit or args.exc_value is None:
        return
    logger.critical(
        "Uncaught error in thread %s",
        name,
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


def configure_logging(config_dir: Path, level: str = DEFAULT_LOG_LEVEL) -> Path:
    """Send the log to ``config_dir`` and catch uncaught errors; returns the log file."""
    global _crash_file, _handler
    config_dir.mkdir(parents=True, exist_ok=True)
    log_file = config_dir / LOG_FILE_NAME
    handler = RotatingFileHandler(
        log_file, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUPS, encoding=ENCODING
    )
    handler.setFormatter(logging.Formatter(LINE_FORMAT))
    _handler = handler
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False
    sys.excepthook = _log_uncaught
    threading.excepthook = _log_uncaught_thread
    # The crash file is apart: Windows cannot rotate a file that faulthandler keeps open.
    if _crash_file is None:
        _crash_file = (config_dir / CRASH_FILE_NAME).open("a", encoding=ENCODING)
        faulthandler.enable(_crash_file)
    return log_file


def log_startup(config_dir: Path, executable: Path, level: str) -> None:
    """Write the start-up report as plain lines, whatever the level (header of the file)."""
    if _handler is None:
        return
    _handler.setFormatter(logging.Formatter("%(message)s"))
    for line in startup_report(datetime.now().astimezone(), executable, config_dir, level):
        _handler.handle(logging.LogRecord("wxclaude", logging.INFO, "", 0, line, None, None))
    _handler.setFormatter(logging.Formatter(LINE_FORMAT))
