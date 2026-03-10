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

_CV_DEPS = ('cv2', 'PIL', 'wurlitzer')
_cv_import_warning = (
    'Optional package "{}" is not found. '
    'You might want to install Computer-Vision dependencies '
    'by running `pip install mmif-python[cv]=={}`'
)


def _check_cv_dep(dep):
    """Import a CV dependency, raising ImportError with a helpful message."""
    try:
        return importlib.__import__(dep)
    except ImportError as e:
        raise ImportError(
            _cv_import_warning.format(e.name, mmif.__version__)
        ) from e


FPS_DOCPROP_KEY = 'fps'
FRAMECOUNT_DOCPROP_KEY = 'frameCount'
DURATION_DOCPROP_KEY = 'duration'
DURATIONUNIT_DOCPROP_KEY = 'durationTimeUnit'


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


def capture(video_document: Document):
    """
    Captures a video file using OpenCV and adds fps, frame count, and duration as properties to the document.

    :param video_document: :py:class:`~mmif.serialize.annotation.Document` instance that holds a video document (``"@type": ".../VideoDocument/..."``)
    :return: `OpenCV VideoCapture <https://docs.opencv.org/3.4/d8/dfe/classcv_1_1VideoCapture.html>`_ object
    """
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
    video_document.add_property(DURATIONUNIT_DOCPROP_KEY, 'milliseconds')
    return v


def get_framerate(video_document: Document) -> float:
    """
    Gets the frame rate of a video document. First by checking the fps property of the document, then by capturing the video.

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
            fps = round(video_document.get_property(k), 2)
            return fps
    cap = capture(video_document)
    fps = video_document.get_property(FPS_DOCPROP_KEY)
    cap.release()
    return fps


def extract_frames_as_images(video_document: Document, framenums: Iterable[int], as_PIL: bool = False, record_ffmpeg_errors: bool = False):
    """
    Extracts frames from a video document as a list of :py:class:`numpy.ndarray`.
    Use with :py:func:`sample_frames` function to get the list of frame numbers first.

    :param video_document: :py:class:`~mmif.serialize.annotation.Document` instance that holds a video document (``"@type": ".../VideoDocument/..."``)
    :param framenums: iterable integers representing the frame numbers to extract
    :param as_PIL: return :py:class:`PIL.Image.Image` instead of :py:class:`~numpy.ndarray`
    :param record_ffmpeg_errors: if True, records and warns about FFmpeg stderr output during extraction
    :return: frames as a list of :py:class:`~numpy.ndarray` or :py:class:`~PIL.Image.Image`
    """
    cv2 = _check_cv_dep('cv2')
    # deduplicate and sort frame numbers for extraction, then map back to original order
    original_framenums = list(framenums)
    unique_framenums = sorted(set(original_framenums))
    if as_PIL:
        Image = _check_cv_dep('PIL').Image
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
    return extract_frames_as_images(vd, [get_mid_framenum(mmif, time_frame)], as_PIL=as_PIL)[0]


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


def _tp_ids_to_framenums(mmif: Mmif, tp_ids: List[str]) -> List[int]:
    """
    Converts a list of timepoint annotation IDs to frame numbers.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param tp_ids: list of timepoint annotation IDs
    :return: list of frame numbers
    """
    return [
        int(convert_timepoint(mmif, mmif[tp_id], 'f'))
        for tp_id in tp_ids
    ]


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


def _timeframe_to_frame_range(
    mmif: Mmif, time_frame: Annotation
) -> Tuple[int, int]:
    """
    Converts a TimeFrame's start/end to frame numbers.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation`
        instance of a TimeFrame with ``start``, ``end``,
        ``timeUnit``, and ``document`` properties
    :return: tuple of (start_frame, end_frame)
    """
    start, end = convert_timeframe(mmif, time_frame, 'f')
    return int(start), int(end)


def _sample_all(mmif: Mmif, time_frame: Annotation) -> List[int]:
    """
    Samples all frame numbers from a TimeFrame. Uses all
    ``targets`` if present, otherwise generates every frame
    in the start/end interval.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation`
        instance of a TimeFrame
    :return: list of frame numbers
    """
    if 'targets' in time_frame.properties:
        return _tp_ids_to_framenums(
            mmif, time_frame.get_property('targets'))
    start, end = _timeframe_to_frame_range(mmif, time_frame)
    return sample_frames(start, end)


def _sample_representatives(
    mmif: Mmif, time_frame: Annotation
) -> List[int]:
    """
    Samples frame numbers from a TimeFrame's representatives.
    Returns an empty list if ``representatives`` is not present
    (skips the TimeFrame).

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation`
        instance of a TimeFrame
    :return: list of frame numbers (empty if no representatives)
    """
    if 'representatives' in time_frame.properties:
        reps = time_frame.get_property('representatives')
        if reps:
            return _tp_ids_to_framenums(mmif, reps)
    return []


def _sample_single(mmif: Mmif, time_frame: Annotation) -> List[int]:
    """
    Samples a single frame number from a TimeFrame. Uses the
    middle representative if ``representatives`` is present,
    otherwise computes the midpoint of the start/end interval
    via floor division.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation`
        instance of a TimeFrame
    :return: list containing a single frame number
    """
    if 'representatives' in time_frame.properties:
        reps = time_frame.get_property('representatives')
        if reps:
            mid = reps[len(reps) // 2]
            return _tp_ids_to_framenums(mmif, [mid])
    start, end = _timeframe_to_frame_range(mmif, time_frame)
    return [(start + end) // 2]


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
    frame_nums = _tp_ids_to_framenums(mmif, selected_target_ids)
    video_doc = _resolve_video_document(mmif, annotation)
    images = extract_frames_as_images(video_doc, frame_nums, as_PIL=as_PIL)
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
        frame_nums = _sample_all(mmif, time_frame)
    elif mode == SamplingMode.REPRESENTATIVES:
        frame_nums = _sample_representatives(mmif, time_frame)
    else:
        frame_nums = _sample_single(mmif, time_frame)
    if not frame_nums:
        return []
    video_doc = _resolve_video_document(mmif, time_frame)
    return extract_frames_as_images(video_doc, frame_nums, as_PIL=as_PIL)


def sample_frames(start_frame: int, end_frame: int, sample_rate: float = 1) -> List[int]:
    """
    Helper function to sample frames from a time interval.
    Can also be used as a "cutoff" function when used with ``start_frame==0`` and ``sample_rate==1``.

    :param start_frame: start frame of the interval
    :param end_frame: end frame of the interval
    :param sample_rate: sampling rate (or step) to configure how often to take a frame, default is 1, meaning all consecutive frames are sampled
    :return: list of frame numbers to extract
    """
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
    Converts a frame number to a second value.
    """
    fps = get_framerate(video_doc)
    return convert(frame, 'f', 's', fps)


def framenum_to_millisecond(video_doc: Document, frame: int):
    """
    Converts a frame number to a millisecond value.
    """
    fps = get_framerate(video_doc)
    return convert(frame, 'f', 'ms', fps)


def second_to_framenum(video_doc: Document, second) -> int:
    """
    Converts a second value to a frame number.
    """
    fps = get_framerate(video_doc)
    return int(convert(second, 's', 'f', fps))


def millisecond_to_framenum(video_doc: Document, millisecond: float) -> int:
    """
    Converts a millisecond value to a frame number.
    """
    fps = get_framerate(video_doc)
    return int(convert(millisecond, 'ms', 'f', fps))
