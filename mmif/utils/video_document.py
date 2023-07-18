import math
from typing import List, Union

import numpy as np
from PIL import Image

from mmif import Annotation, Document
from mmif.vocabulary import DocumentTypes

try:
    import cv2
    import ffmpeg
    import PIL
except ImportError as e:
    raise ImportError(
        f"Optional package {e.name} not found. You might want to install Computer-Vision dependencies by running `pip install mmif-python[cv]`")

FPS_DOCPROP_KEY = 'fps'
UNIT_NORMALIZATION = {
    'ms': 'millisecond',
    'msec': 'millisecond',
    'millisecond': 'millisecond',
    'milliseconds': 'millisecond',
    's': 'second',
    'sec': 'second',
    'second': 'second',
    'seconds': 'second',
    'frame': 'frame',
    'f': 'frame',
}


def capture(vd: Document) -> cv2.VideoCapture:
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

def extract_frames_as_images(vd: Document, framenums: List[int], as_PIL: bool = False) -> List[np.ndarray]:
    """
    Extracts frames from a video document as a list of numpy arrays.
    Use `sample_frames` function in this module to get the list of frame numbers first. 
    
    :param vd: VideoDocument object that holds the video file location
    :param framenums: integers representing the frame numbers to extract
    :param as_PIL: use PIL.Image instead of numpy.ndarray
    :return: 
    """
    # TODO (krim @ 7/17/23): replace the below `extract_frames` with this function
    raise NotImplementedError

def extract_frames(vd: Document, sample_ratio: int, frames_cutoff: int = math.inf, as_PIL: bool = False) -> List[np.ndarray]:
    video_frames = []
    video = capture(vd)
    current_frame = 0
    while video.isOpened() and len(video_frames) < frames_cutoff:
        # Read the current frame
        ret, frame = video.read()

        if ret:
            video_frames.append(Image.fromarray(frame[:, :, ::-1]) if as_PIL else frame)
        else:
            break

        # Skip sampleRatio frames
        current_frame += sample_ratio if sample_ratio is not None else 1
        video.set(cv2.CAP_PROP_POS_FRAMES, current_frame)

    # Potentially print some statistics like how many frames extracted, sampleRatio, cutoff
    print(f'Extracted {len(video_frames)} frames from {vd.location}')
    return video_frames

def sample_frames(start_frame: int, end_frame: int, sample_ratio: int = 1) ->  List[int]:
    """
    Helper function to sample frames from a time interval.
    When start_frame is 0 and end_frame is X, this function basically works as "cutoff". 
    
    :param start_frame: start frame of the interval
    :param end_frame: end frame of the interval
    :param sample_ratio: sample ratio or sample step, default is 1, meaning all consecutive frames are sampled
    """
    if sample_ratio < 1:
        raise ValueError(f"Sample ratio must be greater than 1, but got {sample_ratio}")
    # TODO (krim @ 7/17/23): replace the below `get_images_from_timeframe` with this function
    raise NotImplementedError

def get_images_from_timeframe(video_doc: Document, timeframe: Annotation, frames: int) -> List[Image]:
    video_frames = []
    video_filename = video_doc.location_path()

    # Open the video file
    video = cv2.VideoCapture(video_filename)
    # Get middle frame or frames spaced out based on frames
    if frames == 1:
        video.set(cv2.CAP_PROP_POS_FRAMES, int(timeframe.properties['start'] + timeframe.properties['end']) / 2)
        ret, frame = video.read()
        if not ret:
            raise ValueError(f'Could not read frame at {int(timeframe.properties["start"] + timeframe.properties["end"]) / 2}')
        video_frames.append(Image.fromarray(frame[:, :, ::-1]))
    else:
        for i in range(frames):
            video.set(cv2.CAP_PROP_POS_FRAMES, int(timeframe.properties['start'] + timeframe.properties['end']) / frames * i)
            ret, frame = video.read()
            if not ret:
                raise ValueError(f'Could not read frame at {int(timeframe.properties["start"] + timeframe.properties["end"]) / frames * i}')
            video_frames.append(Image.fromarray(frame[:, :, ::-1]))

    return video_frames


def convert(time: Union[int, float], in_unit: str, out_unit: str, fps: Union[int, float]) -> Union[int, float]:
    try:
        in_unit = UNIT_NORMALIZATION[in_unit]
    except KeyError:
        raise ValueError(f"Not supported time unit: {in_unit}")
    try:
        out_unit = UNIT_NORMALIZATION[out_unit]
    except KeyError:
        raise ValueError(f"Not supported time unit: {out_unit}")
    if in_unit == out_unit:
        return time
    elif out_unit == 'frame':
        if 'millisecond' == in_unit:
            return int(time / 1000 * fps)
        elif 'second' == in_unit:
            return int(time * fps)
    elif in_unit == 'second':
        return time * 1000
    elif in_unit == 'millisecond':
        return time // 1000
    else:
        time = time if out_unit == 'second' else time // 1000
        return int(time * fps)


def framenum_to_second(video_doc: Document, frame: int):
    fps = get_framerate(video_doc)
    return convert(frame, 'f', 's', fps)


def framenum_to_millisecond(video_doc: Document, frame: int):
    fps = get_framerate(video_doc)
    return convert(frame, 'f', 'ms', fps)


def second_to_framenum(video_doc: Document, second) -> int:
    fps = get_framerate(video_doc)
    return convert(second, 's', 'f', fps)


def millisecond_to_framenum(video_doc: Document, millisecond: float) -> int:
    fps = get_framerate(video_doc)
    return convert(millisecond, 'ms', 'f', fps)
