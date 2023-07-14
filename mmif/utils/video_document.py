import math
from typing import List
import numpy as np
from PIL import Image

from mmif import Mmif, View, Annotation, Document
from mmif.vocabulary import DocumentTypes, AnnotationTypes

try:
    import cv2
    import ffmpeg
    import PIL
except ImportError as e:
    raise ImportError(
        f"Optional package {e.name} not found. You might want to install Computer-Vision dependencies by running `pip install mmif-python[cv]`")

FPS_DOCPROP_KEY = 'fps'


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


def frames_to_seconds(video_doc: Document, frames: int, sample_ratio: int) -> float:
    # Needs to take fps and sample ratio
    fps = get_framerate(video_doc)
    return frames / (fps * sample_ratio)


def frames_to_milliseconds(video_doc: Document, frames: int, sample_ratio: int) -> float:
    # Needs to take fps and sample ratio
    return frames_to_seconds(video_doc, frames, sample_ratio) * 1000


def seconds_to_frames(video_doc: Document, seconds: float, sample_ratio: int) -> int:
    fps = get_framerate(video_doc)
    return int(seconds * fps * sample_ratio)


def milliseconds_to_frames(video_doc: Document, milliseconds: float, sample_ratio: int) -> int:
    return seconds_to_frames(video_doc, milliseconds / 1000, sample_ratio)
