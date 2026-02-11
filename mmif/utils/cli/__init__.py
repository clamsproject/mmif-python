"""
Package containing CLI modules.
"""

import sys
import os
from contextlib import contextmanager
from typing import IO, ContextManager, Optional, Union


def open_cli_io_arg(
    path_or_dash: Optional[Union[str, IO]],
    mode: str = 'r',
    encoding: Optional[str] = None,
    errors: Optional[str] = None,
    default_stdin: bool = False,
) -> ContextManager[IO]:
    """
    Context manager for opening files with stdin/stdout support.

    This is a native replacement for argparse.FileType which is deprecated as of Python 3.14
    due to resource leak issues. Unlike FileType, this defers file opening until actually needed
    and ensures proper cleanup via context manager.

    Handles the common CLI pattern where:
    - '-' means stdin (read mode) or stdout (write mode)
    - None means "argument not provided"; when default_stdin=True, it falls back to stdin/stdout
    - Regular paths open actual files with proper resource management

    :param path_or_dash: File path, '-' for stdin/stdout, None for no argument, or a file-like object
    :param mode: File mode ('r' for reading, 'w' for writing)
    :param encoding: Optional file encoding
    :param errors: Optional error handling strategy for encoding
    :param default_stdin: If True and path_or_dash is None, default to stdin (mode 'r') or stdout (mode 'w')
    :return: Context manager yielding file handle
    """

    def _requires_read(requested_mode: str) -> bool:
        return 'r' in requested_mode or '+' in requested_mode

    def _requires_write(requested_mode: str) -> bool:
        return any(flag in requested_mode for flag in ('w', 'a', 'x', '+'))

    @contextmanager
    def _open():
        # Determine if we should use stdin/stdout
        use_std = path_or_dash == '-' or (path_or_dash is None and default_stdin)
        needs_read = _requires_read(mode)
        needs_write = _requires_write(mode)

        if path_or_dash is None and default_stdin and needs_read and sys.stdin.isatty():
            raise SystemExit("error: No input MMIF provided.")

        if use_std:
            if needs_read and needs_write:
                raise ValueError(f"Mode '{mode}' not supported with stdin/stdout (use read or write only)")
            if needs_read:
                yield sys.stdin
            elif needs_write:
                yield sys.stdout
            else:
                raise ValueError(f"Mode '{mode}' not supported with stdin/stdout (use 'r' or 'w')")
        elif hasattr(path_or_dash, 'read') or hasattr(path_or_dash, 'write'):
            if needs_read and not hasattr(path_or_dash, 'read'):
                raise ValueError(f"Mode '{mode}' requires a readable file-like object")
            if needs_write and not hasattr(path_or_dash, 'write'):
                raise ValueError(f"Mode '{mode}' requires a writable file-like object")
            yield path_or_dash
        else:
            # Open actual file with proper cleanup
            if path_or_dash is None:
                raise ValueError("File path cannot be None when not using stdin/stdout")
            if needs_read and not os.path.exists(path_or_dash):
                raise FileNotFoundError(f"Input path does not exist: {path_or_dash}")
            f = open(path_or_dash, mode, encoding=encoding, errors=errors)
            try:
                yield f
            finally:
                f.close()

    return _open()


from mmif.utils.cli import describe
from mmif.utils.cli import rewind
from mmif.utils.cli import source
from mmif.utils.cli import summarize

