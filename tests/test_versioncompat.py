import unittest

import pytest

from mmif.serialize.view import ContainsDict, View
from mmif.vocabulary import DocumentTypes
from mmif.vocabulary.base_types import TypesBase

pytestmark = pytest.mark.filterwarnings("error")


class TestMMIFVersionCompatibility(unittest.TestCase):

    def test_compatibility(self):
        """
        Simply tests searching by @type queries that do not match MMIF file version works at only patch level
        """
        mmif_prefix = DocumentTypes.TextDocument.base_uri
        attype_prefix = f'{mmif_prefix}/vocabulary'
        tdv1_1 = TypesBase.from_str(f'{attype_prefix}/TextDocument/v1')
        tdv1_2 = TypesBase.from_str(f'{attype_prefix}/TextDocument/v1')
        tdv2_1 = TypesBase.from_str(f'{attype_prefix}/TextDocument/v2')
        self.assertEqual(tdv1_1, tdv1_2)
        d = {tdv1_1: 0, tdv1_2: 1}
        with pytest.warns(UserWarning, match='version difference'):
            self.assertIn(tdv2_1, d)
        view = View()
        view.new_contain(tdv1_1)
        with pytest.warns(UserWarning, match='version difference'):
            self.assertIn(tdv2_1, view.metadata.contains)
        
        with pytest.warns(UserWarning, match='version difference'):
            self.assertEqual(tdv1_1, tdv2_1)
        # disable fuzzy matching
        tdv2_1.fuzzy_eq = False
        self.assertNotEqual(tdv1_1, tdv2_1)
        
        # legacy mapping: see https://github.com/clamsproject/mmif/issues/14#issuecomment-1504439497
        ann_v1 = TypesBase.from_str(f'{attype_prefix}/Annotation/v1')
        ann_v2 = TypesBase.from_str(f'{attype_prefix}/Annotation/v2')
        ann_0_4_0 = TypesBase.from_str(f'{mmif_prefix}/0.4.0/vocabulary/Annotation')
        ann_0_4_2 = TypesBase.from_str(f'{mmif_prefix}/0.4.2/vocabulary/Annotation')
        self.assertEqual(ann_v1, ann_0_4_0)
        self.assertEqual(ann_v2, ann_0_4_2)
        with pytest.warns(UserWarning, match='version difference'):
            self.assertEqual(ann_v2, ann_0_4_0)
        with pytest.warns(UserWarning, match='version difference'):
            self.assertEqual(ann_v1, ann_0_4_2)

        tf_v1 = TypesBase.from_str(f'{attype_prefix}/TimeFrame/v1')
        tf_v2 = TypesBase.from_str(f'{attype_prefix}/TimeFrame/v2')
        for patch in range(3):
            tf_old = TypesBase.from_str(f'{mmif_prefix}/0.4.{patch}/vocabulary/TimeFrame')
            self.assertEqual(tf_v1, tf_old)
            with pytest.warns(UserWarning, match='version difference'):
                self.assertEqual(tf_v2, tf_old)
