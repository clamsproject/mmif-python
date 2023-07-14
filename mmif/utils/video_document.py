from mmif import Document
from mmif.vocabulary import DocumentTypes, AnnotationTypes

try:
    import cv2
    import ffmpeg
    import PIL
except ImportError as e:
    raise ImportError(
        f"Optional package {e.name} not found. You might want to install Computer-Vision dependencies by running `pip install mmif-python[cv]`")


def open_video(vd: Document) -> cv2.VideoCapture:
    if vd is None or vd.at_type != DocumentTypes.VideoDocument:
        raise ValueError(f'The document does not exist.')

    framerate_keys = ('fps', 'framerate')
    fps = None
    for k in framerate_keys:
        if k in vd:
            fps = vd.get_property(k)
            break
    cap = cv2.VideoCapture(vd.location_path())
    if fps is None:
        fps = cap.get(cv2.CAP_PROP_FPS)
        vd.add_property('fps', fps)
    return cap
