import importlib
import shlex
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import mmif
from mmif import Document


def _check_av_dep(name: str = 'av') -> Any:
    """Imports a package of the ``av`` extra with an actionable message."""
    try:
        return importlib.import_module(name)
    except ImportError as e:
        raise ImportError(
            f'Optional package "{e.name}" is not found. '
            'Install PyAV support with '
            f'`pip install mmif-python[av]=={mmif.__version__}`'
        ) from e


def _media_check_hint(path: str, media_type: str) -> str:
    """Builds an FFmpeg command for checking a media stream."""
    stream_type = {'audio': 'a', 'video': 'v'}.get(media_type, media_type)
    return (
        'The file may be truncated or corrupted; container metadata does not '
        'reveal this, so to verify the file run '
        f'`ffmpeg -v error -i {shlex.quote(path)} -map 0:{stream_type}:0 '
        '-f null -` and treat any stderr output as a problem '
        '(ffmpeg exits with 0 either way).'
    )


@contextmanager
def _ffmpeg_op(
    action: str,
    document: Document,
    path: str,
    media_type: str,
) -> Iterator[None]:
    """
    Turns failed PyAV operations into actionable ``RuntimeError`` exceptions.

    :param action: operation attempted, as a verb phrase
    :param document: MMIF document being read
    :param path: resolved local path of the media document
    :param media_type: stream type being read, ``"audio"`` or ``"video"``
    :raises RuntimeError: if the operation fails
    """
    av = _check_av_dep()
    try:
        yield
    except (av.error.FFmpegError, IndexError) as e:
        raise RuntimeError(
            f'Cannot {action} {media_type} {document.id} ({path}). '
            f'{_media_check_hint(path, media_type)} '
            f'(original error: {type(e).__name__}: {e})'
        ) from e


def _check_document(document: Document, document_types: tuple[object, ...]) -> None:
    """
    :raises FileNotFoundError: if there is no document
    :raises ValueError: if the document has an unsupported type
    """
    if document is None:
        raise FileNotFoundError('The document does not exist.')
    if document.at_type not in document_types:
        accepted = ', '.join(str(document_type) for document_type in document_types)
        raise ValueError(f'The document must be one of: {accepted}.')


def _open_container_and_stream(
    document: Document,
    media_type: str,
    document_types: tuple[object, ...],
) -> tuple[Any, Any, str]:
    """
    Opens a media container and selects its first stream of the requested type.

    :param document: MMIF document holding the media file
    :param media_type: stream type to select, ``"audio"`` or ``"video"``
    :param document_types: accepted MMIF document types
    :returns: open PyAV container, selected stream, and resolved local path
    :raises FileNotFoundError: if there is no document or no file
    :raises ValueError: if the document has an unsupported type
    :raises RuntimeError: if the container or requested stream cannot be read
    """
    _check_document(document, document_types)
    av = _check_av_dep()
    path = str(document.location_path(nonexist_ok=False))
    container = None
    with _ffmpeg_op('open', document, path, media_type):
        try:
            container = av.open(path)
            stream = getattr(container.streams, media_type)[0]
        except BaseException:
            if container is not None:
                container.close()
            raise
    return container, stream, path
