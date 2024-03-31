import importlib
import warnings
from typing import List, Union, Tuple

import mmif
from mmif import Annotation, Document, Mmif
from mmif.utils.timeunit_helper import convert
from mmif.vocabulary import DocumentTypes

for cv_dep in ('cv2', 'ffmpeg', 'PIL'):
    try:
        importlib.__import__(cv_dep)
    except ImportError as e:
        warnings.warn(f"Optional package \"{e.name}\" is not found. "
                      f"You might want to install Computer-Vision dependencies "
                      f"by running `pip install mmif-python[cv]=={mmif.__version__}`")


FPS_DOCPROP_KEY = 'fps'
FRAMECOUNT_DOCPROP_KEY = 'frameCount'
DURATION_DOCPROP_KEY = 'duration'
DURATIONUNIT_DOCPROP_KEY = 'durationTimeUnit'


def capture(video_document: Document):
    """
    Captures a video file using OpenCV and adds fps, frame count, and duration as properties to the document.

    :param video_document: :py:class:`~mmif.serialize.annotation.Document` instance that holds a video document (``"@type": ".../VideoDocument/..."``)
    :return: `OpenCV VideoCapture <https://docs.opencv.org/3.4/d8/dfe/classcv_1_1VideoCapture.html>`_ object
    """
    import cv2  # pytype: disable=import-error
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
    capture(video_document)
    return video_document.get_property(FPS_DOCPROP_KEY)


def extract_frames_as_images(video_document: Document, framenums: List[int], as_PIL: bool = False):
    """
    Extracts frames from a video document as a list of :py:class:`numpy.ndarray`.
    Use with :py:func:`sample_frames` function to get the list of frame numbers first. 
    
    :param video_document: :py:class:`~mmif.serialize.annotation.Document` instance that holds a video document (``"@type": ".../VideoDocument/..."``)
    :param framenums: integers representing the frame numbers to extract
    :param as_PIL: return :py:class:`PIL.Image.Image` instead of :py:class:`~numpy.ndarray`
    :return: frames as a list of :py:class:`~numpy.ndarray` or :py:class:`~PIL.Image.Image`
    """
    import cv2  # pytype: disable=import-error
    if as_PIL:
        from PIL import Image
    frames = []
    video = capture(video_document)
    cur_f = 0
    while True:
        if not framenums or cur_f > video_document.get_property(FRAMECOUNT_DOCPROP_KEY):
            break
        ret, frame = video.read()
        if cur_f == framenums[0]:
            if not ret:
                sec = convert(cur_f, 'f', 's', video_document.get_property(FPS_DOCPROP_KEY))
                warnings.warn(f'Frame #{cur_f} ({sec}s) could not be read from the video {video_document.id}.')
                continue
            frames.append(Image.fromarray(frame[:, :, ::-1]) if as_PIL else frame)
            framenums.pop(0)
        cur_f += 1
    return frames


def get_mid_framenum(mmif: Mmif, time_frame: Annotation):
    """
    Calculates the middle frame number of a time interval annotation.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation` instance that holds a time interval annotation (``"@type": ".../TimeFrame/..."``)
    :return: middle frame number as an integer
    """
    timeunit = time_frame.get_property('timeUnit')
    video_document = mmif[time_frame.get_property('document')]
    fps = get_framerate(video_document)
    return convert(time_frame.get_property('start') + time_frame.get_property('end'), timeunit, 'frame', fps) // 2


def extract_mid_frame(mmif: Mmif, time_frame: Annotation, as_PIL: bool = False):
    """
    Extracts the middle frame of a time interval annotation as a numpy ndarray.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation` instance that holds a time interval annotation (``"@type": ".../TimeFrame/..."``)
    :param as_PIL: return :py:class:`~PIL.Image.Image` instead of :py:class:`~numpy.ndarray`
    :return: frame as a :py:class:`numpy.ndarray` or :py:class:`PIL.Image.Image`
    """
    vd = mmif[time_frame.get_property('document')]
    return extract_frames_as_images(vd, [get_mid_framenum(mmif, time_frame)], as_PIL=as_PIL)[0]


def sample_frames(start_frame: int, end_frame: int, sample_ratio: int = 1) -> List[int]:
    """
    Helper function to sample frames from a time interval.
    Can also be used as a "cutoff" function when used with ``start_frame==0`` and ``sample_ratio==1``.
    
    :param start_frame: start frame of the interval
    :param end_frame: end frame of the interval
    :param sample_ratio: sample ratio (or step) to configure how often to take a frame, default is 1, meaning all consecutive frames are sampled

    """
    sample_ratio = int(sample_ratio)
    if sample_ratio < 1:
        raise ValueError(f"Sample ratio must be greater than 1, but got {sample_ratio}")
    frame_nums: List[int] = []
    for i in range(start_frame, end_frame, sample_ratio):
        frame_nums.append(i)
    return frame_nums


def get_annotation_property(mmif, annotation, prop_name):
    """
    .. deprecated:: 1.0.8
       Use :py:meth:`mmif.serialize.annotation.Annotation.get_property` method instead.
    
    Get a property value from an annotation. If the property is not found in the annotation, it will look up the metadata of the annotation's parent view and return the value from there.
    xisting
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


def convert_timeframe(mmif: Mmif, time_frame: Annotation, out_unit: str) -> Union[Tuple[Union[int, float, str], Union[int, float, str]]]:
    """
    Converts start and end points in a ``TimeFrame`` annotation a different time unit.

    :param mmif: :py:class:`~mmif.serialize.mmif.Mmif` instance
    :param time_frame: :py:class:`~mmif.serialize.annotation.Annotation` instance that holds a time interval annotation (``"@type": ".../TimeFrame/..."``)
    :param out_unit: time unit to which the point is converted
    :return: tuple of frame numbers (integer) or seconds/milliseconds (float) of input start and end
    """
    in_unit = time_frame.get_property('timeUnit')
    vd = mmif[time_frame.get_property('document')]
    return convert(mmif.get_start(time_frame), in_unit, out_unit, get_framerate(vd)), \
        convert(mmif.get_end(time_frame), in_unit, out_unit, get_framerate(vd))


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
