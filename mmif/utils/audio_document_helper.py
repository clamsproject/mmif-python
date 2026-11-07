import warnings
from collections.abc import Iterator
from typing import TYPE_CHECKING

from mmif import Document
from mmif.utils.av_helper import (
    _check_av_dep,
    _check_document,
    _ffmpeg_op,
    _media_check_hint,
    _open_container_and_stream,
)
from mmif.utils.timeunit_helper import iter_time_windows
from mmif.vocabulary import DocumentTypes

if TYPE_CHECKING:
    import numpy

AUDIO_DOCUMENT_TYPES = (DocumentTypes.AudioDocument, DocumentTypes.VideoDocument)
# encoder padding can leave the decoded audio a few tens of ms short of the
# stated duration; anything shorter than this is not reported as truncation
TRUNCATION_TOLERANCE_MS = 100


def iter_audio_windows(
    document: Document,
    window_ms: int,
    stride_ms: int | None = None,
    sample_rate: int = 16000,
    min_last_window_ms: int = 0,
) -> Iterator[tuple["numpy.ndarray", int, int]]:
    """
    Reads the audio of an audio or video document as windows of samples.

    The audio is mixed down to mono and resampled to ``sample_rate``. The
    file is decoded while the windows are read, so a long file is never held
    in memory. Times are in ms on the media timeline: the first window
    starts where the audio stream starts, which in a video can be later than
    0. The last window ends at the end of the audio and can be shorter than
    ``window_ms``.

    :param document: audio or video document with an audio stream
    :param window_ms: window length in ms
    :param stride_ms: distance between window starts in ms; defaults to
        ``window_ms``, which gives back-to-back windows
    :param sample_rate: output sample rate in Hz
    :param min_last_window_ms: a last window shorter than this is left out
    :returns: ``(samples, start_ms, end_ms)`` per window, with ``samples`` a
        1-D ``float32`` array
    :raises ValueError: if a size is not positive, ``min_last_window_ms`` is
        outside ``[0, window_ms]``, or the document has an unsupported type
    :raises FileNotFoundError: if there is no document or no file
    :raises RuntimeError: if the file cannot be opened, has no audio stream,
        or fails to decode
    :warns UserWarning: if the audio ends more than
        ``TRUNCATION_TOLERANCE_MS`` before the length the file states, which
        usually means the file is truncated
    """
    if window_ms <= 0:
        raise ValueError('window_ms must be positive')
    if stride_ms is None:
        stride_ms = window_ms
    elif stride_ms <= 0:
        raise ValueError('stride_ms must be positive')
    if sample_rate <= 0:
        raise ValueError('sample_rate must be positive')
    if not 0 <= min_last_window_ms <= window_ms:
        raise ValueError('min_last_window_ms must be between 0 and window_ms')
    _check_document(document, AUDIO_DOCUMENT_TYPES)
    return _iter_audio_windows(document, window_ms, stride_ms, sample_rate, min_last_window_ms)


def _iter_audio_windows(document, window_ms, stride_ms, sample_rate, min_last_window_ms):
    av = _check_av_dep()
    numpy = _check_av_dep('numpy')
    container, stream, path = _open_container_and_stream(document, 'audio', AUDIO_DOCUMENT_TYPES)
    # channels are averaged here, as librosa does; swresample's own downmix
    # scales a stereo pair by the square root of two
    resampler = None
    stream_start_s = 0.0
    if stream.start_time is not None and stream.time_base is not None:
        stream_start_s = float(stream.start_time * stream.time_base)

    # sample indices count from the first decoded sample; `origin_ms` is its
    # time on the stream timeline and the start of the window grid
    origin_ms = None
    origin_s = 0.0
    windows: Iterator[tuple[int, int]] = iter(())
    window = None
    chunks = []  # decoded samples from `buffer_start` on, in arrival order
    buffer_start = 0
    decoded_end = 0
    min_last_samples = max(1, round(min_last_window_ms * sample_rate / 1000))

    def to_sample(ms):
        return round((ms - origin_ms) * sample_rate / 1000)

    def to_ms(sample):
        return origin_ms + round(sample * 1000 / sample_rate)

    def append(samples):
        nonlocal decoded_end
        # a stride longer than the window leaves samples that no window needs
        skipped = buffer_start - decoded_end
        decoded_end += len(samples)
        if skipped > 0:
            samples = samples[skipped:]
        if len(samples):
            chunks.append(samples)

    def buffered():
        if len(chunks) != 1:
            chunks[:] = [numpy.concatenate(chunks)] if chunks else [numpy.empty(0, numpy.float32)]
        return chunks[0]

    def emit(final=False):
        nonlocal window, buffer_start
        while True:
            if window is None:
                window = next(windows)
            start_ms, end_ms = window
            start, end = to_sample(start_ms), to_sample(end_ms)
            if end > decoded_end:
                if not final or decoded_end - start < min_last_samples:
                    return
                end, end_ms = decoded_end, to_ms(decoded_end)
            yield buffered()[start - buffer_start:end - buffer_start].copy(), start_ms, end_ms
            if final:
                return
            window = None
            keep_from = to_sample(start_ms + stride_ms)
            chunks[:] = [buffered()[keep_from - buffer_start:]]
            buffer_start = keep_from

    def resampled_frames():
        nonlocal resampler
        for decoded in container.decode(stream):
            if resampler is None:
                resampler = av.AudioResampler(format='fltp', layout=decoded.layout, rate=sample_rate)
            yield from resampler.resample(decoded)
        if resampler is not None:
            yield from resampler.resample(None)

    # contiguous resampled frames wait here, so that numpy runs once per
    # second of audio and not once per (often 1024-sample) frame
    fifo = av.AudioFifo()

    def flush():
        if fifo.samples:
            append(fifo.read().to_ndarray().mean(axis=0, dtype=numpy.float32))
            yield from emit()

    stated_end_s = _stated_end_s(av, container, stream, stream_start_s)

    try:
        with _ffmpeg_op('decode', document, path, 'audio'):
            for frame in resampled_frames():
                frame_s = None
                if frame.pts is not None and frame.time_base is not None:
                    frame_s = float(frame.pts * frame.time_base)
                if origin_ms is None:
                    origin_s = frame_s if frame_s is not None else stream_start_s
                    origin_ms = round(origin_s * 1000)
                    windows = iter_time_windows(origin_ms, None, window_ms, stride_ms)
                # the fifo checks pts against its own count from zero
                frame.pts = None
                fifo.write(frame)
                if fifo.samples >= sample_rate:
                    yield from flush()
            yield from flush()
            if origin_ms is not None:
                yield from emit(final=True)
    finally:
        container.close()
    # a cut that ends on a packet boundary decodes cleanly, so only the
    # duration the file states shows that audio is missing
    decoded_end_ms = to_ms(decoded_end) if origin_ms is not None else round(stream_start_s * 1000)
    if stated_end_s is not None:
        stated_end_ms = round(stated_end_s * 1000)
        if stated_end_ms - decoded_end_ms > TRUNCATION_TOLERANCE_MS:
            warnings.warn(
                f'The audio of {document.id} ends at {decoded_end_ms} ms, '
                f'{stated_end_ms - decoded_end_ms} ms before the end its file '
                f'states ({stated_end_ms} ms); the windows stop there. '
                f'{_media_check_hint(path, "audio")}',
                stacklevel=2)


def _stated_end_s(av, container, stream, stream_start_s):
    """
    End of the audio stream in seconds as the file metadata states it, or
    ``None``. The container duration is used only when the file has no other
    stream, because it is the length of the longest stream. A truncated WAV
    file states its truncated length, so it is not detected.
    """
    if stream.duration is not None and stream.time_base is not None:
        return stream_start_s + float(stream.duration * stream.time_base)
    if container.duration and len(container.streams) == 1:
        start_s = (container.start_time or 0) / av.time_base
        return start_s + container.duration / av.time_base
    return None
