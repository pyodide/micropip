import contextlib
import logging
import sys
from collections.abc import Generator
from typing import Any

_logger: logging.Logger | None = None
_indentation: int = 0


@contextlib.contextmanager
def indent_log(num: int = 2) -> Generator[None, None, None]:
    """
    A context manager which will cause the log output to be indented for any
    log messages emitted inside it.
    """
    global _indentation

    _indentation += num
    try:
        yield
    finally:
        _indentation -= num


# borrowed from pip._internal.utils.logging
class IndentingFormatter(logging.Formatter):
    default_time_format = "%Y-%m-%dT%H:%M:%S"

    def __init__(
        self,
        *args: Any,
        add_timestamp: bool = False,
        **kwargs: Any,
    ) -> None:
        """
        A logging.Formatter that obeys the indent_log() context manager.
        :param add_timestamp: A bool indicating output lines should be prefixed
            with their record's timestamp.
        """
        self.add_timestamp = add_timestamp
        super().__init__(*args, **kwargs)

    def get_message_start(self, formatted: str, levelno: int) -> str:
        """
        Return the start of the formatted log message (not counting the
        prefix to add to each line).
        """
        if levelno < logging.WARNING:
            return ""
        if levelno < logging.ERROR:
            return "WARNING: "

        return "ERROR: "

    def format(self, record: logging.LogRecord) -> str:
        """
        Calls the standard formatter, but will indent all of the log message
        lines by our current indentation level.
        """
        global _indentation

        formatted = super().format(record)
        message_start = self.get_message_start(formatted, record.levelno)
        formatted = message_start + formatted

        prefix = ""
        if self.add_timestamp:
            prefix = f"{self.formatTime(record)} "
        prefix += " " * _indentation
        formatted = "".join([prefix + line for line in formatted.splitlines(True)])
        return formatted


def _set_formatter_once() -> None:
    global _logger

    if _logger is not None:
        return

    _logger = logging.getLogger("micropip")

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.NOTSET)
    ch.setFormatter(IndentingFormatter())

    _logger.addHandler(ch)


def setup_logging(verbosity: int | bool) -> logging.Logger:
    _set_formatter_once()

    if verbosity >= 2:
        level_number = logging.DEBUG
    elif verbosity == 1:  # True == 1
        level_number = logging.INFO
    else:
        level_number = logging.WARNING

    assert _logger
    _logger.setLevel(level_number)

    return _logger
