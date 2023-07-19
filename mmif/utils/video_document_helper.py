import importlib
import warnings
from typing import List, Union, Tuple

import mmif
from mmif import Annotation, Document, Mmif
from mmif.vocabulary import DocumentTypes

for cv_dep in ('cv2', 'ffmpeg', 'PIL'):
    try:
        importlib.__import__(cv_dep)
    except ImportError as e:
        warnings.warn(f"Optional package \"{e.name}\" is not found. "
                      f"You might want to install Computer-Vision dependencies "
                      f"by running `pip install mmif-python[cv]=={mmif.__version__}`")


FPS_DOCPROP_KEY = 'fps'
UNIT_NORMALIZATION = {
    'm': 'millisecond',
    'ms': 'millisecond',
    'msec': 'millisecond',
    'millisecond': 'millisecond',
    'milliseconds': 'millisecond',
    's': 'second',
    'se': 'second',
    'sec': 'second',
    'second': 'second',
    'seconds': 'second',
    'f': 'frame',
    'fr': 'frame',
    'frame': 'frame',
    'frames': 'frame',
}


def capture(vd: Document):
    import cv2  # pytype: disable=import-error
    if vd is None or vd.at_type != DocumentTypes.VideoDocument:
        raise ValueError(f'The document does not exist.')

    v = cv2.VideoCapture(vd.location_path())
    vd.add_property(FPS_DOCPROP_KEY, v.get(cv2.CAP_PROP_FPS))
    return v


def get_framerate(vd: Document) -> float:
    if vd is None or vd.at_type != DocumentTypes.VideoDocument:
        raise ValueError(f'The document does not exist.')

    framerate_keys = (FPS_DOCPROP_KEY, 'framerate')
    for k in framerate_keys:
        if k in vd:
            fps = vd.get_property(k)
            return fps
    capture(vd)
    return vd.get_property(FPS_DOCPROP_KEY)


def extract_frames_as_images(vd: Document, framenums: List[int], as_PIL: bool = False):
    """
    Extracts frames from a video document as a list of numpy arrays.
    Use `sample_frames` function in this module to get the list of frame numbers first. 
    
    :param vd: VideoDocument object that holds the video file location
    :param framenums: integers representing the frame numbers to extract
    :param as_PIL: use PIL.Image instead of numpy.ndarray
    :return: frames as a list of numpy arrays or PIL.Image objects
    """
    import cv2  # pytype: disable=import-error
    if as_PIL:
        from PIL import Image
    frames = []
    video = capture(vd)
    for framenum in framenums:
        video.set(cv2.CAP_PROP_POS_FRAMES, framenum)
        ret, frame = video.read()
        if ret:
            frames.append(Image.fromarray(frame[:, :, ::-1]) if as_PIL else frame)
        else:
            break
    return frames


def extract_mid_frame(mmif: Mmif, tf: Annotation, as_PIL: bool = False):
    """
    Extracts the middle frame from a video document
    """
    timeunit = get_annotation_property(mmif, tf, 'timeUnit')
    vd = mmif[get_annotation_property(mmif, tf, 'document')]
    fps = get_framerate(vd)
    midframe = sum(convert(float(tf.get_property(timepoint_propkey)), timeunit, 'frame', fps) for timepoint_propkey in ('start', 'end')) // 2
    return extract_frames_as_images(vd, [midframe], as_PIL=as_PIL)[0]


def sample_frames(start_frame: int, end_frame: int, sample_ratio: int = 1) -> List[int]:
    """
    Helper function to sample frames from a time interval.
    When start_frame is 0 and end_frame is X, this function basically works as "cutoff". 
    
    :param start_frame: start frame of the interval
    :param end_frame: end frame of the interval
    :param sample_ratio: sample ratio or sample step, default is 1, meaning all consecutive frames are sampled
    """
    sample_ratio = int(sample_ratio)
    if sample_ratio < 1:
        raise ValueError(f"Sample ratio must be greater than 1, but got {sample_ratio}")
    frame_nums: List[int] = []
    for i in range(start_frame, end_frame, sample_ratio):
        frame_nums.append(i)
    return frame_nums


def convert(time: Union[int, float], in_unit: str, out_unit: str, fps: float) -> Union[int, float]:
    try:
        in_unit = UNIT_NORMALIZATION[in_unit]
    except KeyError:
        raise ValueError(f"Not supported time unit: {in_unit}")
    try:
        out_unit = UNIT_NORMALIZATION[out_unit]
    except KeyError:
        raise ValueError(f"Not supported time unit: {out_unit}")
    # s>s, ms>ms, f>f
    if in_unit == out_unit:
        return time
    elif out_unit == 'frame':
        # ms>f
        if 'millisecond' == in_unit:
            return int(time / 1000 * fps)
        # s>f
        elif 'second' == in_unit:
            return int(time * fps)
    # s>ms
    elif in_unit == 'second':
        return time * 1000
    # ms>s
    elif in_unit == 'millisecond':
        return time // 1000
    # f>ms, f>s
    else:
        return (time / fps) if out_unit == 'second' else (time / fps * 1000)  # pytype: disable=bad-return-type

def get_annotation_property(mmif, annotation, prop_name):
    # TODO (krim @ 7/18/23): this probably should be merged to the main mmif.serialize packge
    if prop_name in annotation:
        return annotation.get_property(prop_name)
    try:
        return mmif[annotation.parent].metadata.contains[annotation.at_type][prop_name]
    except KeyError:
        raise KeyError(f"Annotation {annotation.id} does not have {prop_name} property.")

def convert_timepoint(mmif: Mmif, timepoint: Annotation, out_unit: str) -> Union[int, float]:
    """
    Converts a time point included in an annotation to a different time unit.
    The input annotation must have ``timePoint`` property. 

    :param mmif: input MMIF to obtain fps and input timeunit
    :param timepoint: annotation with ``timePoint`` property
    :param out_unit: time unit to which the point is converted
    :return: frame number (integer) or second/millisecond (float) of input timepoint
    """
    in_unit = get_annotation_property(mmif, timepoint, 'timeUnit')
    vd = mmif[get_annotation_property(mmif, timepoint, 'document')]
    return convert(timepoint.get_property('timePoint'), in_unit, out_unit, get_framerate(vd))

def convert_timeframe(mmif: Mmif, timeframe: Annotation, out_unit: str) -> Union[Tuple[int, int], Tuple[float, float]]:
    """
    Converts start and end points in a TimeFrame annotation a different time unit.

    :param mmif: input MMIF to obtain fps and input timeunit
    :param timeframe: ``TimeFrame` type annotation
    :param out_unit: time unit to which the point is converted
    :return: tuple of frame numbers (integer) or seconds/milliseconds (float) of input start and end
    """
    in_unit = get_annotation_property(mmif, timeframe, 'timeUnit')
    vd = mmif[get_annotation_property(mmif, timeframe, 'document')]
    return convert(timeframe.get_property('start'), in_unit, out_unit, get_framerate(vd)), \
        convert(timeframe.get_property('end'), in_unit, out_unit, get_framerate(vd))



def framenum_to_second(video_doc: Document, frame: int):
    fps = get_framerate(video_doc)
    return convert(frame, 'f', 's', fps)


def framenum_to_millisecond(video_doc: Document, frame: int):
    fps = get_framerate(video_doc)
    return convert(frame, 'f', 'ms', fps)


def second_to_framenum(video_doc: Document, second) -> int:
    fps = get_framerate(video_doc)
    return int(convert(second, 's', 'f', fps))


def millisecond_to_framenum(video_doc: Document, millisecond: float) -> int:
    fps = get_framerate(video_doc)
    return int(convert(millisecond, 'ms', 'f', fps))
