import json
import unittest

from mmif import Mmif, View
from mmif.serialize.model import MmifObjectEncoder
from mmif.vocabulary import AnnotationTypes, DocumentTypes
from tests.mmif_examples import *


class TestAnnotationTypes(unittest.TestCase):

    def setUp(self) -> None:
        self.maxDiff = None

    def test_encode(self):
        list_of_two = [AnnotationTypes.Annotation, AnnotationTypes.Chapter]
        string_of_two = f'[\"http://mmif.clams.ai/vocabulary/Annotation/{AnnotationTypes.typevers["Annotation"]}\", \"http://mmif.clams.ai/vocabulary/Chapter/{AnnotationTypes.typevers["Chapter"]}\"]'
        string_out = json.dumps(list_of_two, indent=None, cls=MmifObjectEncoder)
        self.assertEqual(string_of_two, string_out)

    def test_use_in_mmif(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        view_obj: View = mmif_obj.get_view_by_id('v1')
        view_obj.new_annotation(AnnotationTypes.Polygon, 'p1')
        view_obj.new_annotation(AnnotationTypes.TimeFrame, 'bb2')
        self.assertEqual(list(view_obj.metadata.contains.keys()), [f'http://mmif.clams.ai/vocabulary/TimeFrame/{AnnotationTypes.typevers["TimeFrame"]}', f'http://mmif.clams.ai/vocabulary/Polygon/{AnnotationTypes.typevers["Polygon"]}'])

    def test_type_checking(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        ann_obj = mmif_obj.get_view_by_id('v1').annotations['s1']
        self.assertTrue(ann_obj.is_type(ann_obj.at_type))
        self.assertTrue(ann_obj.is_type(str(ann_obj.at_type)))
        self.assertFalse(ann_obj.is_type(DocumentTypes.VideoDocument))

    def test_serialize_within_mmif(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        view_obj = mmif_obj.get_view_by_id('v5')
        view_obj.annotations._items.pop('bb25')
        anno_obj = view_obj.new_annotation(AnnotationTypes.BoundingBox, 'bb25')
        anno_obj.add_property('coordinates', [[150, 810], [1120, 810], [150, 870], [1120, 870]])
        anno_obj.add_property('timePoint', 21000)
        anno_obj.add_property('boxType', 'text')
        expected = json.loads(Mmif(MMIF_EXAMPLES['everything']).serialize())
        actual = json.loads(mmif_obj.serialize())
        bb_type = str(AnnotationTypes.BoundingBox)
        expected['views'][4]['metadata']['contains'][bb_type]['gen_time'] = 'dummy'
        actual['views'][4]['metadata']['contains'][bb_type]['gen_time'] = 'dummy'
        self.assertEqual(expected, actual)


if __name__ == '__main__':
    unittest.main()
