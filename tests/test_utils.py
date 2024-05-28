import unittest

import pytest

from mmif import Mmif, Document, AnnotationTypes
from mmif.utils import sequence_helper as sqh
from mmif.utils import timeunit_helper as tuh
from mmif.utils import video_document_helper as vdh


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

    def test_extract_representative_frame(self):
        tp = self.a_view.new_annotation(AnnotationTypes.TimePoint, timePoint=1500, timeUnit='milliseconds', document='d1')
        tf = self.a_view.new_annotation(AnnotationTypes.TimeFrame, start=1000, end=2000, timeUnit='milliseconds', document='d1')
        tf.add_property('representatives', [tp.id])
        rep_frame_num = vdh.get_representative_framenum(self.mmif_obj, tf)
        expected_frame_num = vdh.millisecond_to_framenum(self.video_doc, tp.get_property('timePoint'))
        self.assertEqual(expected_frame_num, rep_frame_num)
        # check there is an error if no representatives
        tf = self.a_view.new_annotation(AnnotationTypes.TimeFrame, start=1000, end=2000, timeUnit='milliseconds', document='d1')
        with pytest.raises(ValueError):
            vdh.get_representative_framenum(self.mmif_obj, tf)
        # check there is an error if there is a representative referencing a timepoint that
        # does not exist
        tf.add_property('representatives', ['fake_tp_id'])
        with pytest.raises(ValueError):
            vdh.get_representative_framenum(self.mmif_obj, tf)

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

    def test_convert_roundtrip(self):
        # ms for 1 frame
        tolerance = 1000 / self.video_doc.get_property('fps')
        for ms in [1000, 1234, 4321, 44444, 789789]:
            m2f = vdh.millisecond_to_framenum(self.video_doc, ms)
            m2f2m = vdh.framenum_to_millisecond(self.video_doc, m2f)
            self.assertAlmostEqual(ms, m2f2m, delta=tolerance)

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
    
    def test_validate_labelset(self):
        mmif_obj = Mmif(validate=False)
        view = mmif_obj.new_view()
        anns = [view.new_annotation(AnnotationTypes.TimePoint, labelset=['a', 'b', 'c']) for _ in range(3)]
        self.assertTrue(sqh.validate_labelset(anns))
        anns.append(view.new_annotation(AnnotationTypes.TimePoint, labelset=['a', 'b', 'c', 'd']))
        with pytest.raises(ValueError):
            self.assertFalse(sqh.validate_labelset(anns))
        anns.pop()
        anns.append(view.new_annotation(AnnotationTypes.TimePoint))
        with pytest.raises(KeyError):
            self.assertFalse(sqh.validate_labelset(anns))

    def test_build_remapper(self):
        self.assertEqual({'a': 'a', 'b': 'b', 'c': 'c', 'd': 'd', 'e': 'e', 'f': 'f'},
                         sqh.build_label_remapper(list('abcdef'), {}))
        self.assertEqual({'a': 1, 'b': 2, 'c': 1, 'd': '-', 'e': '-', 'f': '-'},
                         sqh.build_label_remapper(list('abcdef'), {'a': 1, 'b': 2, 'c': 1}))

    def test_build_score_lists(self):
        c1 = {'a': 0.1, 'b': 0.2, 'c': 0.3}
        c2 = {'a': 0.6, 'b': 0.5, 'c': 0.4}
        remap = {'a': 'x', 'b': 'y', 'c': 'x'}
        lblmap, scores = sqh.build_score_lists([c1, c2], remap)
        self.assertEqual(2, len(scores.shape))
        self.assertEqual(2, scores.shape[0])
        self.assertEqual(2, scores.shape[1])
        self.assertEqual({'x': [0.3, 0.6], 'y': [0.2, 0.5]}, {lbl: list(scores[idx]) for lbl, idx in lblmap.items()})
        _, scores = sqh.build_score_lists([c1, c2], remap, score_remap_op=min)
        self.assertEqual({'x': [0.1, 0.4], 'y': [0.2, 0.5]}, {lbl: list(scores[idx]) for lbl, idx in lblmap.items()})

    def test_width_based_smoothing(self):
        scores = [0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1]
        # idx = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        # res = [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1],
        # cannot pass non-positive threshold for sequence sizes
        with pytest.raises(ValueError):
            sqh.smooth_outlying_short_intervals(scores, 1, 0)
        with pytest.raises(ValueError):
            sqh.smooth_outlying_short_intervals(scores, 0, 1)
        with pytest.raises(ValueError):
            sqh.smooth_outlying_short_intervals(scores, 0, 0)
        self.assertEqual([(1, 13), (19, 20)],
                         sqh.smooth_outlying_short_intervals(scores, 1, 4))
        # idx = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        # res = [0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        self.assertEqual([(1, 7)],
                         sqh.smooth_outlying_short_intervals(scores, 4, 2))
        # idx = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        # res = [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0],
        self.assertEqual([(1, 13)],
                         sqh.smooth_outlying_short_intervals(scores, 4, 4))
        # special test case for not trimming short end peaks adjacent to short gaps
        scores = [1, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1]
        # idx = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        # res = [1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        self.assertEqual([(0, 7), (11, 20)],
                         sqh.smooth_outlying_short_intervals(scores, 4, 4))
        # special test case for stitching only mode
        scores = [0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1]
        # idx = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        # res = [0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1],
        self.assertEqual([(3, 7), (11, 15), (18, 20)],
                         sqh.smooth_outlying_short_intervals(scores, 1, 1))


if __name__ == '__main__':
    unittest.main()
