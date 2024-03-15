import unittest

from mmif import Mmif, Document, AnnotationTypes
from mmif.utils import timeunit_helper as tuh
from mmif.utils import video_document_helper as vdh
from mmif.utils import sequence_helper as sqh


class TestTimeunitHelper(unittest.TestCase):
    
    FPS = 30
    
    def test_convert(self):
        self.assertEqual(1000, tuh.convert(1, 's', 'ms', self.FPS))
        self.assertEqual(1.1, tuh.convert(1100, 'ms', 's', self.FPS))
        self.assertEqual('00:01:30.000', tuh.convert(90, 's', 'i', self.FPS))
        self.assertEqual(3300, tuh.convert('00:00:03.300', 'i', 'ms', self.FPS))
        self.assertEqual(7.77, tuh.convert('00:00:07.770', 'i', 's', self.FPS))


class TestVideoDocumentHelper(unittest.TestCase):
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
    
    def test_extract_mid_frame(self):
        tf = self.a_view.new_annotation(AnnotationTypes.TimeFrame, start=100, end=200, timeUnit='frame', document='d1')
        self.assertEqual(150, vdh.get_mid_framenum(self.mmif_obj, tf))
        tf = self.a_view.new_annotation(AnnotationTypes.TimeFrame, start=0, end=200, timeUnit='frame', document='d1')
        self.assertEqual(100, vdh.get_mid_framenum(self.mmif_obj, tf))
        tf = self.a_view.new_annotation(AnnotationTypes.TimeFrame, start=0, end=3, timeUnit='seconds', document='d1')
        self.assertEqual(vdh.convert(1.5, 's', 'f', self.fps), vdh.get_mid_framenum(self.mmif_obj, tf))

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


class TestSequenceHelper(unittest.TestCase):
    def test_build_remapper(self):
        self.assertEqual({'a': 'a', 'b': 'b', 'c': 'c', 'd': 'd', 'e': 'e', 'f': 'f'},
                         sqh.build_label_remapper(list('abcdef'), {}))
        self.assertEqual({'a': 1, 'b': 2, 'c': 1, 'd': '-', 'e': '-', 'f': '-'},
                         sqh.build_label_remapper(list('abcdef'), {'a': 1, 'b': 2, 'c': 1}))
    
    def test_build_score_lists(self):
        c1 = {'a': 0.1, 'b': 0.2, 'c': 0.3}
        c2 = {'a': 0.6, 'b': 0.5, 'c': 0.4}
        remap = {'a': 'x', 'b': 'y', 'c': 'x'}
        _, scores = sqh.build_score_lists([c1, c2], remap)
        self.assertEqual({'x': [0.3, 0.6], 'y': [0.2, 0.5]}, scores)
        self.assertEqual(set(remap.values()), set(scores.keys()))
        _, scores = sqh.build_score_lists([c1, c2], remap, score_remap_op=min)
        self.assertEqual({'x': [0.1, 0.4], 'y': [0.2, 0.5]}, scores)
        _, scores = sqh.build_score_lists([c1, c2], remap, as_numpy=True)
        self.assertEqual(2, len(scores.shape))
        self.assertEqual(2, scores.shape[0])
        self.assertEqual(2, scores.shape[1])
    
    def test_width_based_smoothing(self):
        scores = [0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1]
        # idx = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        # res = [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1],
        self.assertEqual([(1, 13), (19, 20)],
                         sqh.smooth_short_intervals(scores, 1, 4))
        # idx = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        # res = [0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        self.assertEqual([(1, 7)],
                         sqh.smooth_short_intervals(scores, 4, 2))
        # idx = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        # res = [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0],
        self.assertEqual([(1, 13)],
                         sqh.smooth_short_intervals(scores, 4, 4))
        # special test case for not trimming short end peaks adjacent to short gaps
        scores = [1, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1]
        # idx = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        # res = [1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        self.assertEqual([(0, 7), (11, 20)],
                         sqh.smooth_short_intervals(scores, 4, 4))
        # special test case for stitching only mode
        scores = [0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1]
        # idx = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        # res = [0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1],
        self.assertEqual([(3, 7), (11, 15), (18, 20)],
                         sqh.smooth_short_intervals(scores, 1, 1))


if __name__ == '__main__':
    unittest.main()
