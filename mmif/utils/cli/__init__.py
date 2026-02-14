"""
Package containing CLI modules.
"""

import contextlib
import io
import os
import sys
from typing import Iterator, Optional, TextIO, cast


@contextlib.contextmanager
def open_cli_io_arg(path_or_dash: Optional[str],
                    mode: str = 'r',
                    encoding: Optional[str] = None,
                    errors: Optional[str] = None,
                    default_stdin: bool = False,
                    ) -> Iterator[TextIO]:
    """
    Context manager for opening files with stdin/stdout support.

    This function is intended for plain text streams (e.g. JSON/MMIF) and does
    not support binary modes (e.g., 'rb', 'wb').

    This is a native replacement for argparse.FileType which is deprecated as
    of Python 3.14 due to resource leak issues. Unlike FileType, this defers
    file opening until actually needed and ensures proper cleanup via context
    manager.

    Handles the common CLI pattern where:

    - '-' means stdin (read mode) or stdout (write mode)
    - None means "argument not provided"; when default_stdin=True, it falls back
      to stdin/stdout
    - Regular paths open actual files with proper resource management

    :param path_or_dash: File path, '-' for stdin/stdout, or None for no argument
    :param mode: File mode ('r' for reading, 'w' for writing). Binary modes are
        not supported.
    :param encoding: Optional file encoding
    :param errors: Optional error handling strategy for encoding
    :param default_stdin: If True and path_or_dash is None, default to stdin
        (mode 'r') or stdout (mode 'w')
    :returns: Context manager yielding text-mode file handle
    :rtype: Iterator[TextIO]

    Example usage::

        # Read from file or stdin
        with open_cli_io_arg(args.input, 'r', default_stdin=True) as f:
            content = f.read()

        # Write to file or stdout
        with open_cli_io_arg(args.output, 'w', default_stdin=True) as f:
            f.write(content)
    """
    # Valid text modes for file operations
    _READ_FLAGS = frozenset({'r', '+'})
    _WRITE_FLAGS = frozenset({'w', 'a', 'x', '+'})

    if 'b' in mode:
        raise ValueError(
            f"Binary mode '{mode}' is not supported. "
            "Use text modes ('r', 'w', 'a', 'x') instead."
        )

    needs_read = bool(set(mode) & _READ_FLAGS)
    needs_write = bool(set(mode) & _WRITE_FLAGS)

    should_use_stdio = path_or_dash == '-' or (
        path_or_dash is None and default_stdin
    )

    file_handle: Optional[TextIO] = None
    should_close = False

    try:
        if should_use_stdio:
            if needs_read and needs_write:
                raise ValueError(
                    f"Mode '{mode}' not supported with stdin/stdout "
                    "(use read or write only)"
                )

            if needs_read:
                # Check for missing input when stdin is a terminal
                if (
                    path_or_dash is None
                    and default_stdin
                    and sys.stdin.isatty()
                ):
                    raise SystemExit("error: No input provided.")
                file_handle = sys.stdin

            elif needs_write:
                file_handle = sys.stdout

            else:
                raise ValueError(
                    f"Mode '{mode}' not supported with stdin/stdout "
                    "(use 'r' or 'w')"
                )

        elif isinstance(path_or_dash, str):
            if needs_read and not os.path.exists(path_or_dash):
                raise FileNotFoundError(f"Input path does not exist: {path_or_dash}")
            file_handle = cast(TextIO, io.open(path_or_dash, mode, encoding=encoding, errors=errors))
            should_close = True

        elif path_or_dash is None:
            # None without default_stdin means no file specified
            raise ValueError(
                "No file path provided. Use '-' for stdin/stdout or set default_stdin=True."
            )
        else:
            raise TypeError(
                f"Invalid type for path_or_dash: {type(path_or_dash).__name__}. "
                "Expected str or None."
            )

        if file_handle is not None:
            yield file_handle

    finally:
        if should_close and file_handle is not None:
            file_handle.close()


# keep imports of CLI modules for historical reasons
# keep them here in the bottom to avoid circular imports
from mmif.utils.cli import rewind
from mmif.utils.cli import source
