import unittest

from mmif import Mmif, Document, AnnotationTypes
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
        self.assertAlmostEqual(3.337, vdh.framenum_to_second(self.video_doc, 100), places=0)

    def test_frames_to_milliseconds(self):
        self.assertAlmostEqual(3337.0, vdh.framenum_to_millisecond(self.video_doc, 100), places=0)

    def test_seconds_to_frames(self):
        self.assertAlmostEqual(100, vdh.second_to_framenum(self.video_doc, 3.337), places=0)

    def test_milliseconds_to_frames(self):
        self.assertAlmostEqual(100, vdh.millisecond_to_framenum(self.video_doc, 3337.0), places=0)
    
    def test_sample_frames(self):
        s_frame = vdh.second_to_framenum(self.video_doc, 3)
        e_frame = vdh.second_to_framenum(self.video_doc, 5.5)
        # note that int(29.97) = 29
        self.assertEqual(3, len(vdh.sample_frames(s_frame, e_frame, self.fps)))
        s_frame = vdh.second_to_framenum(self.video_doc, 3)
        e_frame = vdh.second_to_framenum(self.video_doc, 5)
        self.assertEqual(1, len(vdh.sample_frames(s_frame, e_frame, 60)))
        
    def test_convert_timepoint(self):
        timepoint_ann = self.a_view.new_annotation(AnnotationTypes.BoundingBox, timePoint=3, timeUnit='second', document='d1')
        self.assertEqual(vdh.convert(3, 's', 'f', self.fps), vdh.convert_timepoint(self.mmif_obj, timepoint_ann, 'f'))
    
    def test_convert_timeframe(self):
        self.a_view.metadata.new_contain(AnnotationTypes.TimeFrame, timeUnit='frame', document='d1')
        timeframe_ann = self.a_view.new_annotation(AnnotationTypes.TimeFrame, start=100, end=200)
        for times in zip((3.337, 6.674), vdh.convert_timeframe(self.mmif_obj, timeframe_ann, 's')):
            self.assertAlmostEqual(*times, places=0)

if __name__ == '__main__':
    unittest.main()
