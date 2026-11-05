from collections.abc import Iterator
from typing import TYPE_CHECKING

from mmif import Document
from mmif.utils.av_helper import (
    _check_av_dep,
    _check_document,
    _ffmpeg_op,
    _open_container_and_stream,
)
from mmif.utils.timeunit_helper import iter_windows
from mmif.vocabulary import DocumentTypes

if TYPE_CHECKING:
    import numpy

AUDIO_DOCUMENT_TYPES = (DocumentTypes.AudioDocument, DocumentTypes.VideoDocument)


def iter_audio_windows(
    document: Document,
    window_ms: int,
    stride_ms: int | None = None,
    sample_rate: int = 16000,
    min_last_window_ms: int = 0,
) -> Iterator[tuple["numpy.ndarray", int, int]]:
    """
    Decodes an audio document, or the audio track of a video, into windows.

    Samples are resampled to mono ``float32`` at ``sample_rate`` and decoded
    incrementally, so memory use is bounded by one window plus its overlap.
    The windows are those of :func:`~mmif.utils.timeunit_helper.iter_windows`
    from the start of the audio stream, which can be later than zero. After
    the last full window, one window runs from the next window start to the
    end of the stream, unless it is shorter than ``min_last_window_ms``.

    :param document: audio or video document with an audio stream
    :param window_ms: window length in milliseconds
    :param stride_ms: distance between window starts; defaults to ``window_ms``
    :param sample_rate: output sample rate in Hz
    :param min_last_window_ms: shortest final window to keep
    :returns: ``(samples, start_ms, end_ms)`` triples
    :raises ValueError: if a size is not positive, ``min_last_window_ms`` is
        outside ``[0, window_ms]``, or the document has an unsupported type
    :raises FileNotFoundError: if there is no document or no file
    :raises RuntimeError: if the file cannot be opened, has no audio stream,
        or fails to decode
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
    window_samples = round(window_ms * sample_rate / 1000)
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

    try:
        with _ffmpeg_op('decode', document, path, 'audio'):
            for frame in resampled_frames():
                frame_s = None
                if frame.pts is not None and frame.time_base is not None:
                    frame_s = float(frame.pts * frame.time_base)
                if origin_ms is None:
                    origin_s = frame_s if frame_s is not None else stream_start_s
                    origin_ms = round(origin_s * 1000)
                    windows = iter_windows(origin_ms, None, window_ms, stride_ms)
                samples = frame.to_ndarray().mean(axis=0, dtype=numpy.float32)
                if frame_s is not None:
                    # a timestamp jump is a gap (filled with silence) or an
                    # overlap (dropped) on the sample timeline
                    frame_start = round((frame_s - origin_s) * sample_rate)
                    gap = frame_start - decoded_end
                    while gap > 0:
                        append(numpy.zeros(min(gap, window_samples), numpy.float32))
                        yield from emit()
                        gap = frame_start - decoded_end
                    if gap < 0:
                        samples = samples[-gap:]
                append(samples)
                yield from emit()
            if origin_ms is not None:
                yield from emit(final=True)
    finally:
        container.close()
