import contextvars
import importlib
import sys
from enum import Enum

import math
import warnings
from io import StringIO
from typing import Iterable  # todo: replace with collections.abc.Iterable in Python 3.9
from typing import List, Union, Tuple

import mmif
from mmif import Annotation, Document, Mmif
from mmif.utils.timeunit_helper import convert
from mmif.vocabulary import DocumentTypes

_CV_DEPS = ('av', 'cv2', 'PIL', 'wurlitzer')
_cv_import_warning = (
    'Optional package "{}" is not found. '
    'You might want to install Computer-Vision dependencies '
    'by running `pip install mmif-python[cv]=={}`'
)

_PTS_BUG_NOTICE = (
    'Frame-number arithmetic ignores the video container\'s PTS start offset, '
    'so the returned frame can be misaligned by however many frames that '
    'offset spans (see issue #379).'
)


def _check_cv_dep(dep):
    """Import a CV dependency, raising ImportError with a helpful message."""
    try:
        return importlib.import_module(dep)
    except ImportError as e:
        raise ImportError(
            _cv_import_warning.format(e.name, mmif.__version__)
        ) from e


FPS_DOCPROP_KEY = 'fps'
FRAMECOUNT_DOCPROP_KEY = 'frameCount'
DURATION_DOCPROP_KEY = 'duration'


class SamplingMode(Enum):
    """Determines how timepoints are selected from a TimeFrame."""
    REPRESENTATIVES = "representatives"
    SINGLE = "single"
    ALL = "all"


SAMPLING_MODE_DESCRIPTIONS = {
    SamplingMode.REPRESENTATIVES: (
        "uses all representative timepoints if present, "
        "otherwise skips the TimeFrame."
    ),
    SamplingMode.SINGLE: (
        "uses the middle representative if present, otherwise "
        "extracts a frame from the midpoint of the start/end "
        "interval (midpoint is calculated by floor division "
        "of the sum of start and end)."
    ),
    SamplingMode.ALL: (
        "uses all target timepoints if present, otherwise "
        "extracts all frames from the time interval."
    ),
}
SAMPLING_MODE_DEFAULT = SamplingMode.REPRESENTATIVES


_sampling_mode = contextvars.ContextVar(
    'sampling_mode', default=SamplingMode.REPRESENTATIVES)


def open_container(video_document: Document):
    """
    Opens a video file and caches stream metadata on the document.

    Reads ``time_base``, ``start_time``, ``duration``, and ``average_rate``
    from the first video stream and writes ``fps``, ``frameCount``, and
    ``duration`` (in ms) to the document as informational properties.
    These properties are informational only; seek and extraction use
    actual PTS read from decoded frames.

    :param video_document: :py:class:`~mmif.serialize.annotation.Document`
        holding a video document (``"@type": ".../VideoDocument/..."``)
    :returns: open PyAV :py:class:`av.container.InputContainer`
    :rtype: av.container.InputContainer
    :raises ValueError: if ``video_document`` is missing or of the wrong type
    """
    av = _check_cv_dep('av')
    if video_document is None or video_document.at_type != DocumentTypes.VideoDocument:
        raise ValueError(f'The document does not exist.')

    container = av.open(video_document.location_path(nonexist_ok=False))
    stream = container.streams.video[0]
    time_base = float(stream.time_base)
    fps = round(float(stream.average_rate), 2)
    # `stream.frames` comes from the container header. Verified exact on
    # CFR H.264/MP4 inputs even with non-zero start offset; for VFR or
    # headerless streams it may be 0, in which case `duration * rate` is
    # the best available (approximate) estimate.
    if stream.frames > 0:
        frame_count = stream.frames
    elif stream.duration is not None and stream.average_rate is not None:
        frame_count = int(round(float(stream.duration) * time_base
                                * float(stream.average_rate)))
    else:
        frame_count = 0
    if stream.duration is not None:
        duration_ms = int(round(float(stream.duration) * time_base * 1000))
    elif frame_count > 0 and fps > 0:
        duration_ms = int(round(frame_count / fps * 1000))
    else:
        duration_ms = 0
    video_document.add_property(FPS_DOCPROP_KEY, fps)
    video_document.add_property(FRAMECOUNT_DOCPROP_KEY, frame_count)
    video_document.add_property(DURATION_DOCPROP_KEY, duration_ms)
    return container


def capture(video_document: Document):
    """
    .. deprecated::
       Use :py:func:`open_container` instead. See issue #379.

    Captures a video file using OpenCV and adds fps, frame count, and duration as properties to the document.

    :param video_document: :py:class:`~mmif.serialize.annotation.Document` instance that holds a video document (``"@type": ".../VideoDocument/..."``)
    :return: `OpenCV VideoCapture <https://docs.opencv.org/3.4/d8/dfe/classcv_1_1VideoCapture.html>`_ object
    """
    warnings.warn(
        f'capture() is deprecated; use open_container() instead. '
        f'{_PTS_BUG_NOTICE}',
        DeprecationWarning, stacklevel=2,
    )
    cv2 = _check_cv_dep('cv2')
    if video_document is None or video_document.at_type != DocumentTypes.VideoDocument:
        raise ValueError(f'The document does not exist.')

    v = cv2.VideoCapture(video_document.location_path(nonexist_ok=False))
    fps = round(v.get(cv2.CAP_PROP_FPS), 2)
    fc = v.get(cv2.CAP_PROP_FRAME_COUNT)
    dur = round(fc / fps, 3) * 1000
    video_document.add_property(FPS_DOCPROP_KEY, fps)
    video_document.add_property(FRAMECOUNT_DOCPROP_KEY, fc)
    video_document.add_property(DURATION_DOCPROP_KEY, dur)
    return v


def get_framerate(video_document: Document) -> float:
    """
    Gets the frame rate of a video document. First by checking the fps
    property of the document, then by opening the video via PyAV.

    :param video_document: :py:class:`~mmif.serialize.annotation.Document` instance that holds a video document (``"@type": ".../VideoDocument/..."``)
    :return: frames per second as a float, rounded to 2 decimal places
    """
    if video_document is None or video_document.at_type != DocumentTypes.VideoDocument:
        raise ValueError(f'The document does not exist.')

    framerate_keys = (FPS_DOCPROP_KEY,
                      'framerate', 'frameRate', 'frame_rate', 'frame-rate',
                      'framespersecond', 'framesPerSecond', 'frames_per_second', 'frames-per-second',
                      'framepersecond', 'framePerSecond', 'frame_per_second', 'frame-per-second')
    for k in framerate_keys:
        if k in video_document:
            return round(video_document.get_property(k), 2)
    container = open_container(video_document)
    try:
        return video_document.get_property(FPS_DOCPROP_KEY)
    finally:
        container.close()


def extract_timepoints_as_images(
    video_document: Document,
    timepoints_ms: Iterable[int],
    as_PIL: bool = False,
):
    """
    Extracts frames at the given media-timeline timepoints (in milliseconds).

    For each requested timepoint, returns the frame whose actual
    presentation timestamp (PTS) is closest to it. Duplicate timepoints
    produce duplicate frames at the same list positions as the input.

    :param video_document: :py:class:`~mmif.serialize.annotation.Document`
        holding a video document (``"@type": ".../VideoDocument/..."``)
    :param timepoints_ms: iterable of timepoint values in milliseconds
    :param as_PIL: return :py:class:`PIL.Image.Image` (RGB) instead of
        :py:class:`~numpy.ndarray` (BGR)
    :returns: frames in the same order (and with the same multiplicity) as
        ``timepoints_ms``
    :rtype: list
    """
    original_timepoints = list(timepoints_ms)
    if not original_timepoints:
        return []
    unique_sorted_ms = sorted(set(original_timepoints))

    Image = _check_cv_dep('PIL.Image') if as_PIL else None

    container = open_container(video_document)
    result_map = {}
    try:
        stream = container.streams.video[0]
        time_base = float(stream.time_base)
        # convert each target ms to stream ticks (PTS units)
        target_ticks = [int(round(t_ms / 1000.0 / time_base))
                        for t_ms in unique_sorted_ms]

        # seek to the nearest keyframe at or before the earliest target
        container.seek(target_ticks[0], backward=True, any_frame=False,
                       stream=stream)

        targets = iter(zip(unique_sorted_ms, target_ticks))
        cur_ms, cur_pts = next(targets, (None, None))
        prev_frame = None
        prev_pts = None

        def _emit(frame, t_ms):
            result_map[t_ms] = (frame.to_image() if as_PIL
                                else frame.to_ndarray(format='bgr24'))

        for frame in container.decode(stream):
            if frame.pts is None:
                continue
            pts = frame.pts
            while cur_ms is not None and pts >= cur_pts:
                # pick whichever of (prev, current) is closer to target
                if prev_pts is None or (pts - cur_pts) <= (cur_pts - prev_pts):
                    _emit(frame, cur_ms)
                else:
                    _emit(prev_frame, cur_ms)
                cur_ms, cur_pts = next(targets, (None, None))
            prev_frame = frame
            prev_pts = pts
            if cur_ms is None:
                break

        # targets past the last decoded frame: fall back to the last frame
        while cur_ms is not None:
            if prev_frame is not None:
                warnings.warn(
                    f'Timepoint {cur_ms}ms is beyond the video duration; '
                    f'returning the last decoded frame for {video_document.id}.'
                )
                _emit(prev_frame, cur_ms)
            else:
                warnings.warn(
                    f'No frames decoded for timepoint {cur_ms}ms from '
                    f'video {video_document.id}.'
                )
            cur_ms, cur_pts = next(targets, (None, None))
    finally:
        container.close()

    return [result_map[t] for t in original_timepoints if t in result_map]


def extract_frames_as_images(video_document: Document, framenums: Iterable[int], as_PIL: bool = False, record_ffmpeg_errors: bool = False):
    """
    .. deprecated::
       Use :py:func:`extract_timepoints_as_images` instead. See issue #379.

    Extracts frames from a video document as a list of :py:class:`numpy.ndarray`.
    Use with :py:func:`sample_frames` function to get the list of frame numbers first.

    :param video_document: :py:class:`~mmif.serialize.annotation.Document` instance that holds a video document (``"@type": ".../VideoDocument/..."``)
    :param framenums: iterable integers representing the frame numbers to extract
    :param as_PIL: return :py:class:`PIL.Image.Image` instead of :py:class:`~numpy.ndarray`
    :param record_ffmpeg_errors: if True, records and warns about FFmpeg stderr output during extraction
    :return: frames as a list of :py:class:`~numpy.ndarray` or :py:class:`~PIL.Image.Image`
    """
    warnings.warn(
        f'extract_frames_as_images() is deprecated; use '
        f'extract_timepoints_as_images() instead. {_PTS_BUG_NOTICE}',
        DeprecationWarning, stacklevel=2,
    )
    cv2 = _check_cv_dep('cv2')
    # deduplicate and sort frame numbers for extraction, then map back to original order
    original_framenums = list(framenums)
    unique_framenums = sorted(set(original_framenums))
    if as_PIL:
        Image = _check_cv_dep('PIL.Image')
    unique_frames = {}
    video = capture(video_document)
    cur_f = 0
    tot_fcount = video_document.get_property(FRAMECOUNT_DOCPROP_KEY)
    # when the target frame is more than this frames away, fast-forward instead of reading frame by frame
    # this is sanity-checked with a small number of video samples
    # (frame-by-frame ndarrays are compared with fast-forwarded ndarrays)
    skip_threadhold = 1000
    framenumi = iter(unique_framenums)
    next_target_f = next(framenumi, None)
    cpipes = _check_cv_dep('wurlitzer').pipes
    ffmpeg_errs = StringIO()
    with cpipes(stderr=ffmpeg_errs, stdout=sys.stdout):
        while True:
            if next_target_f is None or cur_f > tot_fcount or next_target_f > tot_fcount:
                break
            if next_target_f - cur_f > skip_threadhold:
                while next_target_f - cur_f > skip_threadhold:
                    cur_f += skip_threadhold
                else:
                    video.set(cv2.CAP_PROP_POS_FRAMES, cur_f)
            ret, frame = video.read()
            if cur_f == next_target_f:
                if not ret:
                    sec = convert(cur_f, 'f', 's', video_document.get_property(FPS_DOCPROP_KEY))
                    warnings.warn(f'Frame #{cur_f} ({sec}s) could not be read from the video {video_document.id} @ {video_document.location} .')
                else:
                    unique_frames[cur_f] = Image.fromarray(frame[:, :, ::-1]) if as_PIL else frame
                next_target_f = next(framenumi, None)
            cur_f += 1
    ffmpeg_err_str = ffmpeg_errs.getvalue()
    if ffmpeg_err_str and record_ffmpeg_errors:
        warnings.warn(f'FFmpeg output during extracting frames: {ffmpeg_err_str}')
    video.release()
    # return frames in original input order, duplicating where needed
    return [unique_frames[f] for f in original_framenums if f in unique_frames]


def get_mid_framenum(mmif: Mmif, time_frame: Annotation) -> int:
    """
    .. deprecated::
       Use :py:func:`extract_frames_by_mode` instead.
    """
    warnings.warn('This function is deprecated. Use ``extract_frames_by_mode()`` instead.', DeprecationWarning, stacklevel=2)
    return _get_mid_framenum(mmif, time_frame)


def _get_mid_framenum(mmif: Mmif, time_frame: Annotation) -> int:
    """
    Calculates the middle frame number of a time interval annotation.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation` instance that holds a time interval annotation (``"@type": ".../TimeFrame/..."``)
    :return: middle frame number as an integer
    """
    timeunit = time_frame.get_property('timeUnit')
    video_document = mmif[time_frame.get_property('document')]
    fps = get_framerate(video_document)
    return int(convert(time_frame.get_property('start') + time_frame.get_property('end'), timeunit, 'frame', fps) // 2)


def extract_mid_frame(mmif: Mmif, time_frame: Annotation, as_PIL: bool = False):
    """
    .. deprecated::
       Use :py:func:`extract_frames_by_mode` instead.

    Extracts the middle frame of a time interval annotation as a numpy ndarray.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation` instance that holds a time interval annotation (``"@type": ".../TimeFrame/..."``)
    :param as_PIL: return :py:class:`~PIL.Image.Image` instead of :py:class:`~numpy.ndarray`
    :return: frame as a :py:class:`numpy.ndarray` or :py:class:`PIL.Image.Image`
    """
    warnings.warn('This function is deprecated. Use ``extract_frames_by_mode()`` instead.', DeprecationWarning, stacklevel=2)
    vd = mmif[time_frame.get_property('document')]
    fn = get_mid_framenum(mmif, time_frame)
    return extract_frames_as_images(vd, [fn], as_PIL=as_PIL)[0]


def get_representative_framenums(mmif: Mmif, time_frame: Annotation) -> List[int]:
    """
    .. deprecated::
       Use :py:func:`extract_frames_by_mode` instead.

    Calculates the representative frame numbers from an annotation. To pick the representative frames, it first looks
    up the ``representatives`` property of the ``TimeFrame`` annotation. If it is not found, it will calculate the
    number of the middle frame.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation` instance that holds a time interval annotation containing a `representatives` property (``"@type": ".../TimeFrame/..."``)
    :return: representative frame number as an integer
    """
    warnings.warn('This function is deprecated. Use ``extract_frames_by_mode()`` instead.', DeprecationWarning, stacklevel=2)
    if 'representatives' not in time_frame.properties:
        return [_get_mid_framenum(mmif, time_frame)]
    timeunit = time_frame.get_property('timeUnit')
    video_document = mmif[time_frame.get_property('document')]
    fps = get_framerate(video_document)
    representatives = time_frame.get_property('representatives')
    ref_frams = []
    for rep_id in representatives:
        try:
            rep_anno = mmif[rep_id]
        except KeyError as ke:
            raise ValueError(f'Representative timepoint {rep_id} not found in any view. ({ke})')
        ref_frams.append(int(convert(rep_anno.get_property('timePoint'), timeunit, 'frame', fps)))
    return ref_frams


def get_representative_framenum(mmif: Mmif, time_frame: Annotation) -> int:
    """
    .. deprecated::
       Use :py:func:`extract_frames_by_mode` instead.

    A thin wrapper around :py:func:`get_representative_framenums` to return a single representative frame number. Always
    return the first frame number found.
    """
    warnings.warn('This function is deprecated. Use ``extract_frames_by_mode()`` instead.', DeprecationWarning, stacklevel=2)
    try:
        return get_representative_framenums(mmif, time_frame)[0]
    except IndexError:
        raise ValueError(f'No representative frame found in the TimeFrame annotation {time_frame.id}.')


def extract_representative_frame(mmif: Mmif, time_frame: Annotation, as_PIL: bool = False, first_only: bool = True):
    """
    .. deprecated::
       Use :py:func:`extract_frames_by_mode` instead.

    Extracts the representative frame of an annotation as a numpy ndarray or PIL Image.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation` instance that holds a time interval annotation (``"@type": ".../TimeFrame/..."``)
    :param as_PIL: return :py:class:`~PIL.Image.Image` instead of :py:class:`~numpy.ndarray`
    :param first_only: return the first representative frame only
    :return: frame as a :py:class:`numpy.ndarray` or :py:class:`PIL.Image.Image`
    """
    warnings.warn('This function is deprecated. Use ``extract_frames_by_mode()`` instead.', DeprecationWarning, stacklevel=2)
    video_document = mmif[time_frame.get_property('document')]
    rep_frame_num = [get_representative_framenum(mmif, time_frame)] if first_only else get_representative_framenums(mmif, time_frame)
    return extract_frames_as_images(video_document, rep_frame_num, as_PIL=as_PIL)[0]


def _tp_ids_to_timepoints_ms(mmif: Mmif, tp_ids: List[str]) -> List[int]:
    """
    Converts a list of timepoint annotation IDs to media-timeline timepoints in milliseconds.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param tp_ids: list of timepoint annotation IDs
    :return: list of timepoint values in ms
    :rtype: list
    """
    # TODO: when a source annotation has timeUnit='frame', convert_timepoint
    # falls back to `frame / fps` ms math that ignores the container's PTS
    # start offset. Fully resolving this requires retiring timeUnit='frame'
    # (tracked in clams-vocabulary#15).
    return [int(round(convert_timepoint(mmif, mmif[tp_id], 'ms')))
            for tp_id in tp_ids]


def _resolve_video_document(mmif: Mmif, time_frame: Annotation):
    """
    Resolves the video document associated with a TimeFrame.
    Checks the TimeFrame's own ``document`` property first,
    then falls back to the ``document`` property of the first
    target timepoint.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation`
        instance of a TimeFrame
    :return: :py:class:`~mmif.serialize.annotation.Document`
    """
    if 'document' in time_frame.properties:
        return mmif[time_frame.get_property('document')]
    if 'targets' in time_frame.properties:
        targets = time_frame.get_property('targets')
        if targets:
            tp = mmif[targets[0]]
            return mmif[tp.get_property('document')]
    raise ValueError(
        f'Cannot resolve video document for TimeFrame '
        f'{time_frame.id}.')


def _timeframe_to_timepoint_range_ms(
    mmif: Mmif, time_frame: Annotation
) -> Tuple[int, int]:
    """
    Converts a TimeFrame's start/end to media-timeline timepoints in ms.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation`
        instance of a TimeFrame with ``start``, ``end``,
        ``timeUnit``, and ``document`` properties
    :return: tuple of (start_ms, end_ms)
    :rtype: tuple
    """
    start, end = convert_timeframe(mmif, time_frame, 'ms')
    return int(round(start)), int(round(end))


def _sample_all_timepoints_ms(mmif: Mmif, time_frame: Annotation) -> List[int]:
    """
    Samples all timepoints (ms) from a TimeFrame. Uses all ``targets`` if
    present, otherwise samples the start/end interval at the stream's
    average frame rate.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation`
        instance of a TimeFrame
    :return: list of timepoint values in ms
    :rtype: list
    """
    if 'targets' in time_frame.properties:
        return _tp_ids_to_timepoints_ms(
            mmif, time_frame.get_property('targets'))
    start_ms, end_ms = _timeframe_to_timepoint_range_ms(mmif, time_frame)
    video_document = _resolve_video_document(mmif, time_frame)
    fps = get_framerate(video_document)
    step_ms = 1000.0 / fps
    return sample_timepoints(start_ms, end_ms, step_ms)


def _sample_representatives_timepoints_ms(
    mmif: Mmif, time_frame: Annotation
) -> List[int]:
    """
    Samples timepoints (ms) from a TimeFrame's representatives. Returns an
    empty list if ``representatives`` is not present (skips the TimeFrame).

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation`
        instance of a TimeFrame
    :return: list of timepoint values in ms (empty if no representatives)
    :rtype: list
    """
    if 'representatives' in time_frame.properties:
        reps = time_frame.get_property('representatives')
        if reps:
            return _tp_ids_to_timepoints_ms(mmif, reps)
    return []


def _sample_single_timepoint_ms(
    mmif: Mmif, time_frame: Annotation
) -> List[int]:
    """
    Samples a single timepoint (ms) from a TimeFrame. Uses the middle
    representative if ``representatives`` is present, otherwise the
    midpoint of the start/end interval.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation`
        instance of a TimeFrame
    :return: list containing a single timepoint value in ms
    :rtype: list
    """
    if 'representatives' in time_frame.properties:
        reps = time_frame.get_property('representatives')
        if reps:
            mid = reps[len(reps) // 2]
            return _tp_ids_to_timepoints_ms(mmif, [mid])
    start_ms, end_ms = _timeframe_to_timepoint_range_ms(mmif, time_frame)
    return [(start_ms + end_ms) // 2]


def extract_target_frames(mmif: Mmif, annotation: Annotation, min_timepoints: int = 0, max_timepoints: int = sys.maxsize, fraction: float = 1.0, as_PIL: bool = False):
    """
    Extracts frames corresponding to the timepoints listed in the ``targets`` property of an annotation.
    Selection of timepoints is based on minimum, maximum, and fraction of targets to include.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param annotation: :py:class:`~mmif.serialize.annotation.Annotation` instance containing a ``targets`` property
    :param min_timepoints: minimum number of timepoints to include
    :param max_timepoints: maximum number of timepoints to include
    :param fraction: fraction of targets to include (ideally)
    :param as_PIL: return :py:class:`~PIL.Image.Image` instead of :py:class:`~numpy.ndarray`
    :return: a tuple containing (list of frames, list of selected target IDs)
    """
    if 'targets' not in annotation.properties:
        raise ValueError(f'Annotation {annotation.id} does not have a "targets" property.')

    targets = annotation.get_property('targets')
    num_targets = len(targets)
    if num_targets == 0:
        return [], []

    ideal_count = int(num_targets * fraction)
    count = max(min_timepoints, ideal_count)
    count = min(max_timepoints, count)
    count = min(num_targets, count)

    if count == 1:
        indices = [num_targets // 2]
    else:
        indices = [int(i * (num_targets - 1) / (count - 1)) for i in range(count)]

    selected_target_ids = [targets[i] for i in indices]
    timepoints_ms = _tp_ids_to_timepoints_ms(mmif, selected_target_ids)
    video_doc = _resolve_video_document(mmif, annotation)
    images = extract_timepoints_as_images(video_doc, timepoints_ms, as_PIL=as_PIL)
    return images, selected_target_ids


def extract_frames_by_mode(
    mmif: Mmif,
    time_frame: Annotation,
    mode: Union[SamplingMode, None] = None,
    as_PIL: bool = False
) -> List:
    """
    Extracts frames from a TimeFrame annotation based on a
    sampling mode. If ``mode`` is not specified, uses the
    context-level default (set via
    :py:data:`_sampling_mode` context variable).

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: TimeFrame annotation to sample from
    :param mode: :py:class:`SamplingMode`, or None to use
        the context default
    :param as_PIL: return PIL Images instead of ndarrays
    :return: list of frames (may be empty for
        ``REPRESENTATIVES`` mode when no representatives exist)
    """
    if mode is None:
        mode = _sampling_mode.get()
    if mode == SamplingMode.ALL:
        timepoints_ms = _sample_all_timepoints_ms(mmif, time_frame)
    elif mode == SamplingMode.REPRESENTATIVES:
        timepoints_ms = _sample_representatives_timepoints_ms(mmif, time_frame)
    else:
        timepoints_ms = _sample_single_timepoint_ms(mmif, time_frame)
    if not timepoints_ms:
        return []
    video_doc = _resolve_video_document(mmif, time_frame)
    return extract_timepoints_as_images(video_doc, timepoints_ms, as_PIL=as_PIL)


def sample_timepoints(
    start_ms: int,
    end_ms: int,
    step_ms: Union[int, float],
) -> List[int]:
    """
    Samples timepoints (in ms) from a half-open time interval
    ``[start_ms, end_ms)`` with a fixed step.

    :param start_ms: start of the interval (inclusive), in ms
    :param end_ms: end of the interval (exclusive), in ms
    :param step_ms: step size between adjacent timepoints, in ms;
        may be fractional (e.g. ``1000/fps``), but emitted timepoints
        are always integer ms
    :returns: list of integer timepoint values in ms
    :rtype: list
    :raises ValueError: if ``step_ms`` is not positive
    """
    if step_ms <= 0:
        raise ValueError(
            f'step_ms must be positive, got {step_ms}')
    timepoints: List[int] = []
    i = 0
    while True:
        t = start_ms + i * step_ms
        if t >= end_ms:
            break
        timepoints.append(int(round(t)))
        i += 1
    return timepoints


def sample_frames(start_frame: int, end_frame: int, sample_rate: float = 1) -> List[int]:
    """
    .. deprecated::
       Use :py:func:`sample_timepoints` instead. See issue #379.

    Helper function to sample frames from a time interval.
    Can also be used as a "cutoff" function when used with ``start_frame==0`` and ``sample_rate==1``.

    :param start_frame: start frame of the interval
    :param end_frame: end frame of the interval
    :param sample_rate: sampling rate (or step) to configure how often to take a frame, default is 1, meaning all consecutive frames are sampled
    :return: list of frame numbers to extract
    """
    warnings.warn(
        f'sample_frames() is deprecated; use sample_timepoints() instead. '
        f'{_PTS_BUG_NOTICE}',
        DeprecationWarning, stacklevel=2,
    )
    if sample_rate < 1:
        raise ValueError(f"Sample rate must be greater than 1, but got {sample_rate}")
    frame_nums: List[int] = []
    cur_f = start_frame
    while cur_f < end_frame:
        ceiling = math.ceil(cur_f)
        if ceiling < end_frame:
            frame_nums.append(math.ceil(cur_f))
        cur_f += sample_rate
    return frame_nums


def get_annotation_property(mmif, annotation, prop_name):
    """
    .. deprecated:: 1.0.8
       Will be removed in 2.0.0.
       Use :py:meth:`mmif.serialize.annotation.Annotation.get_property` method instead.

    Get a property value from an annotation. If the property is not found in the annotation, it will look up the metadata of the annotation's parent view and return the value from there.

    :param mmif: MMIF object containing the annotation
    :param annotation: Annotation object to get property from
    :param prop_name: name of the property to retrieve
    :return: the property value
    """
    warnings.warn(f'{__name__}() is deprecated. '
                  f'Directly ask the annotation for a property by calling annotation.get_property() instead.',
                  DeprecationWarning)
    return annotation.get_property(prop_name)


def convert_timepoint(mmif: Mmif, timepoint: Annotation, out_unit: str) -> Union[int, float, str]:
    """
    Converts a time point included in an annotation to a different time unit.
    The input annotation must have ``timePoint`` property.

    :param mmif: input MMIF to obtain fps and input timeunit
    :param timepoint: :py:class:`~mmif.serialize.annotation.Annotation` instance with ``timePoint`` property
    :param out_unit: time unit to which the point is converted (``frames``, ``seconds``, ``milliseconds``)
    :return: frame number (integer) or second/millisecond (float) of input timepoint
    """
    in_unit = timepoint.get_property('timeUnit')
    vd = mmif[timepoint.get_property('document')]
    return convert(timepoint.get_property('timePoint'), in_unit, out_unit, get_framerate(vd))


def convert_timeframe(mmif: Mmif, time_frame: Annotation, out_unit: str) -> Tuple[Union[int, float, str], Union[int, float, str]]:
    """
    Converts start and end points in a ``TimeFrame`` annotation a different time unit.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation` instance that holds a time interval annotation (``"@type": ".../TimeFrame/..."``)
    :param out_unit: time unit to which the point is converted
    :return: tuple of frame numbers, seconds/milliseconds, or ISO notation of TimeFrame's start and end
    """
    in_unit = time_frame.get_property('timeUnit')
    vd = mmif[time_frame.get_property('document')]
    fps = get_framerate(vd)
    return convert(time_frame.get_property('start'), in_unit, out_unit, fps), convert(time_frame.get_property('end'), in_unit, out_unit, fps)


def framenum_to_second(video_doc: Document, frame: int):
    """
    .. deprecated::
       Use :py:func:`~mmif.utils.timeunit_helper.convert` with ``ms``/``s``
       directly. See issue #379.
    """
    warnings.warn(
        f'framenum_to_second() is deprecated. {_PTS_BUG_NOTICE}',
        DeprecationWarning, stacklevel=2,
    )
    fps = get_framerate(video_doc)
    return convert(frame, 'f', 's', fps)


def framenum_to_millisecond(video_doc: Document, frame: int):
    """
    .. deprecated::
       Use :py:func:`~mmif.utils.timeunit_helper.convert` with ``ms``/``s``
       directly. See issue #379.
    """
    warnings.warn(
        f'framenum_to_millisecond() is deprecated. {_PTS_BUG_NOTICE}',
        DeprecationWarning, stacklevel=2,
    )
    fps = get_framerate(video_doc)
    return convert(frame, 'f', 'ms', fps)


def second_to_framenum(video_doc: Document, second) -> int:
    """
    .. deprecated::
       Use :py:func:`extract_timepoints_as_images` or stay in the time
       domain. See issue #379.
    """
    warnings.warn(
        f'second_to_framenum() is deprecated. {_PTS_BUG_NOTICE}',
        DeprecationWarning, stacklevel=2,
    )
    fps = get_framerate(video_doc)
    return int(convert(second, 's', 'f', fps))


def millisecond_to_framenum(video_doc: Document, millisecond: float) -> int:
    """
    .. deprecated::
       Use :py:func:`extract_timepoints_as_images` or stay in the time
       domain. See issue #379.
    """
    warnings.warn(
        f'millisecond_to_framenum() is deprecated. {_PTS_BUG_NOTICE}',
        DeprecationWarning, stacklevel=2,
    )
    fps = get_framerate(video_doc)
    return int(convert(millisecond, 'ms', 'f', fps))
