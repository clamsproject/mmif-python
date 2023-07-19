import unittest

import numpy as np
from PIL import Image

from mmif import Mmif, Document
from mmif.utils import video_document_helper as vdh


class TestUtilsVideoDocuments(unittest.TestCase):
    def setUp(self):
        self.fps = 29.97
        self.mmif_obj = Mmif(validate=False)
        self.a_view = self.mmif_obj.new_view()
        self.video_doc = Document({
            "@type": "http://mmif.clams.ai/vocabulary/VideoDocument/v1",
            "properties": {
                "mime": "video",
                "id": "d1",
                "location": "file:///home/snewman/Documents/test_vid.mp4"
            }
        })
        self.video_doc.add_property('fps', self.fps)
        self.mmif_obj.add_document(self.video_doc)

    def test_get_framerate(self):
        self.assertAlmostEqual(29.97, vdh.get_framerate(self.video_doc), places=0)

    def test_frames_to_seconds(self):
        self.assertAlmostEqual(3.337, vdh.frames_to_seconds(self.video_doc, 100, 1), places=0)

    def test_frames_to_milliseconds(self):
        self.assertAlmostEqual(3337.0, vdh.frames_to_milliseconds(self.video_doc, 100, 1), places=0)

    def test_seconds_to_frames(self):
        self.assertAlmostEqual(100, vdh.seconds_to_frames(self.video_doc, 3.337, 1), places=0)

    def test_milliseconds_to_frames(self):
        self.assertAlmostEqual(100, vdh.milliseconds_to_frames(self.video_doc, 3337.0, 1), places=0)

    def test_extract_frames(self):
        frames = vdh.extract_frames(self.video_doc, 1, frame_cutoff=20)
        self.assertEqual(20, len(frames))
        self.assertEqual((360, 480, 3), frames[0].shape)
        self.assertEqual('uint8', frames[0].dtype)
        self.assertIsInstance(frames[0], np.ndarray)

    def test_extract_pil_images(self):
        frames = mmif_utils_videodocuments.extract_pil_images(self.video_doc, 1, frame_cutoff=20)
        self.assertEqual(20, len(frames))
        self.assertEqual((480, 360), frames[0].size)
        self.assertEqual('RGB', frames[0].mode)
        self.assertIsInstance(frames[0], Image.Image)


if __name__ == '__main__':
    unittest.main()
