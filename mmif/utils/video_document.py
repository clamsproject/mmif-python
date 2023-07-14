from typing import List
import numpy as np
from PIL import Image

from mmif import Document
from mmif.vocabulary import DocumentTypes, AnnotationTypes

try:
    import cv2
    import ffmpeg
    import PIL
except ImportError as e:
    raise ImportError(
        f"Optional package {e.name} not found. You might want to install Computer-Vision dependencies by running `pip install mmif-python[cv]`")


def capture(vd: Document) -> cv2.VideoCapture:
    v = cv2.VideoCapture(vd.location_path())
    vd.add_property('fps', v.get(cv2.CAP_PROP_FPS))
    return v


def get_framerate(vd: Document) -> float:
    if vd is None or vd.at_type != DocumentTypes.VideoDocument:
        raise ValueError(f'The document does not exist.')

    framerate_keys = ('fps', 'framerate')
    fps = None
    for k in framerate_keys:
        if k in vd:
            fps = vd.get_property(k)
            return fps
    cap = cv2.VideoCapture(vd.location_path())
    fps = cap.get(cv2.CAP_PROP_FPS)
    vd.add_property('fps', fps)
    return fps


def extract_frames(video_doc: Document, sample_ratio: int, frame_cutoff: int = None) -> List[np.ndarray]:
    video_frames = []
    video_filename = video_doc.location_path()

    # Open the video file
    video = cv2.VideoCapture(video_filename)
    current_frame = 0
    while video.isOpened():
        # Read the current frame
        ret, frame = video.read()

        if ret:
            video_frames.append(frame)
        else:
            break

        # Skip sampleRatio frames
        current_frame += sample_ratio
        video.set(cv2.CAP_PROP_POS_FRAMES, current_frame)

        if frame_cutoff is not None and len(video_frames) > frame_cutoff - 1:
            break

    # Potentially print some statistics like how many frames extracted, sampleRatio, cutoff
    print(f'Extracted {len(video_frames)} frames from {video_filename}')
    return video_frames


def extract_pil_images(video_doc: Document, sample_ratio: int = 15, frame_cutoff: int = None) -> List[Image]:
    video_frames = []
    video_filename = video_doc.location_path()

    # Open the video file
    video = cv2.VideoCapture(video_filename)
    current_frame = 0
    while video.isOpened():
        # Read the current frame
        ret, frame = video.read()

        if ret:
            # Convert it to a PIL image
            video_frames.append(Image.fromarray(frame[:, :, ::-1]))
        else:
            break

        # Skip sampleRatio frames
        if sample_ratio is not None:
            current_frame += sample_ratio
            video.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        else:
            current_frame += 1
            video.set(cv2.CAP_PROP_POS_FRAMES, current_frame)

        if frame_cutoff is not None and len(video_frames) > frame_cutoff - 1:
            break

    # Potentially print some statistics like how many frames extracted, sampleRatio, cutoff
    print(f'Extracted {len(video_frames)} frames from {video_filename}')
    return video_frames


def frames_to_seconds(video_doc: Document, frames: int, sample_ratio: int) -> float:
    # Needs to take fps and sample ratio
    fps = get_framerate(video_doc)
    return frames / (fps * sample_ratio)


def frames_to_milliseconds(video_doc: Document, frames: int, sample_ratio: int) -> float:
    # Needs to take fps and sample ratio
    fps = get_framerate(video_doc)
    return frames / (fps * sample_ratio) * 1000


def seconds_to_frames(video_doc: Document, seconds: float, sample_ratio: int) -> int:
    fps = get_framerate(video_doc)
    return int(seconds * fps * sample_ratio)


def milliseconds_to_frames(video_doc: Document, milliseconds: float, sample_ratio: int) -> int:
    fps = get_framerate(video_doc)
    return int(milliseconds / 1000 * fps * sample_ratio)
