"""
Package containing CLI modules.
"""

import contextlib
import io
import os
import sys
from typing import Iterator, Optional, TextIO, Type, Union, cast, get_args, get_origin

from pydantic import BaseModel


@contextlib.contextmanager
def open_cli_io_arg(
    path_or_dash: Optional[str],
    mode: str = "r",
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
    _READ_FLAGS = frozenset({"r", "+"})
    _WRITE_FLAGS = frozenset({"w", "a", "x", "+"})

    if "b" in mode:
        raise ValueError(
            f"Binary mode '{mode}' is not supported. "
            "Use text modes ('r', 'w', 'a', 'x') instead."
        )

    needs_read = bool(set(mode) & _READ_FLAGS)
    needs_write = bool(set(mode) & _WRITE_FLAGS)

    should_use_stdio = path_or_dash == "-" or (path_or_dash is None and default_stdin)

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
                if path_or_dash is None and default_stdin and sys.stdin.isatty():
                    raise SystemExit("error: No input provided.")
                file_handle = sys.stdin

            elif needs_write:
                file_handle = sys.stdout

            else:
                raise ValueError(
                    f"Mode '{mode}' not supported with stdin/stdout (use 'r' or 'w')"
                )

        elif isinstance(path_or_dash, str):
            if needs_read and not os.path.exists(path_or_dash):
                raise FileNotFoundError(f"Input path does not exist: {path_or_dash}")
            file_handle = cast(
                TextIO, io.open(path_or_dash, mode, encoding=encoding, errors=errors)
            )
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


def generate_model_summary(model: Type[BaseModel], indent: int = 0) -> str:
    lines = []
    prefix = " " * indent

    # model_fields is a dictionary of FieldInfo objects
    for name, field in model.model_fields.items():
        # Get the alias if available, otherwise use the field name
        field_name = field.alias if field.alias else name

        # Get type annotation
        type_annotation = field.annotation

        def format_type(t) -> str:
            origin = get_origin(t)
            args = get_args(t)

            # Handle Optional (Union[T, None])
            if origin is Union and type(None) in args:
                non_none_args = [arg for arg in args if arg is not type(None)]
                if len(non_none_args) == 1:
                    return f"{format_type(non_none_args[0])}, optional"

            # Handle List
            if origin is list:
                if args:
                    return f"[{format_type(args[0])}]"
                return "[]"

            # Handle Dict
            if origin is dict:
                return "obj"

            # Handle Pydantic Models (Custom Classes)
            if isinstance(t, type) and issubclass(t, BaseModel):
                return "obj"

            # Handle basic types and cleanup
            t_str = str(t)
            if t_str.startswith("<class '"):
                t_str = t_str[8:-2]
            if t_str.startswith("typing."):
                t_str = t_str[7:]

            # Remove module prefix if present
            if "." in t_str:
                t_str = t_str.split(".")[-1]

            return t_str

        display_type = format_type(type_annotation)

        description = field.description if field.description else ""

        line_content = f"{prefix}- {field_name} ({display_type})"
        if description:
            line_content += f": {description}"
        lines.append(line_content)

        # Check if it's a Pydantic model or a list/dict of Pydantic models
        origin = get_origin(type_annotation)
        args = get_args(type_annotation)

        nested_model = None
        # Handle Optional wrappers for nesting check
        check_type = type_annotation
        if origin is Union and type(None) in args:
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                check_type = non_none_args[0]
                origin = get_origin(check_type)
                args = get_args(check_type)

        if isinstance(check_type, type) and issubclass(check_type, BaseModel):
            nested_model = check_type
        elif (
            origin is list
            and args
            and isinstance(args[0], type)
            and issubclass(args[0], BaseModel)
        ):
            nested_model = args[0]
        elif (
            origin is dict
            and args
            and len(args) > 1
            and isinstance(args[1], type)
            and issubclass(args[1], BaseModel)
        ):
            nested_model = args[1]

        if nested_model:
            lines.append(generate_model_summary(nested_model, indent + 4))

    return "\n".join(lines)


# keep imports of CLI modules for historical reasons
# keep them here in the bottom to avoid circular imports
from mmif.utils.cli import rewind
from mmif.utils.cli import source
