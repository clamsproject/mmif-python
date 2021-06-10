import unittest
from string import Template

from mmif import Mmif
from mmif.vocabulary import DocumentTypes
from tests.mmif_examples import *


class TestMMIFVersionCompatibility(unittest.TestCase):

    def setUp(self) -> None:
        self.major = 0
        self.minor = 4
        self.patch = 3
        self.specver = self.version(self.major, self.minor, self.patch)
        self.mmif_cur = Mmif(Template(EVERYTHING_JSON).substitute(VERSION=self.specver))
        self.mmif_pat_past = Mmif(Template(EVERYTHING_JSON).substitute(VERSION=self.version(self.major, self.minor, self.patch-1)))
        self.mmif_pat_futr = Mmif(Template(EVERYTHING_JSON).substitute(VERSION=self.version(self.major, self.minor, self.patch+1)))
        self.mmif_min_past = Mmif(Template(EVERYTHING_JSON).substitute(VERSION=self.version(self.major, self.minor-1, self.patch)))
        self.mmif_min_futr = Mmif(Template(EVERYTHING_JSON).substitute(VERSION=self.version(self.major, self.minor+1, self.patch)))
        self.mmif_maj_past = Mmif(Template(EVERYTHING_JSON).substitute(VERSION=self.version(self.major-1, self.minor, self.patch)))
        self.mmif_maj_futr = Mmif(Template(EVERYTHING_JSON).substitute(VERSION=self.version(self.major+1, self.minor, self.patch)))

    @staticmethod
    def version(*major_minor_patch):
        return '.'.join(map(str, major_minor_patch))
    
    def test_compatibility(self):
        """
        Simply tests searching by @type queries that do not match MMIF file version works at only patch level
        """
        DocumentTypes.TextDocument.version = self.specver
        td_url_prefix = f'{DocumentTypes.TextDocument.base_uri}/{DocumentTypes.TextDocument.version}'
        text_documents = self.mmif_cur.get_documents_by_type(DocumentTypes.TextDocument)
        views_with_text_documents = self.mmif_cur.get_views_contain(DocumentTypes.TextDocument)
        self.assertEqual(td_url_prefix, self.mmif_cur.metadata['mmif'])
        self.assertNotEqual(td_url_prefix, self.mmif_pat_past.metadata['mmif'])
        self.assertEqual(len(self.mmif_pat_past.get_documents_by_type(DocumentTypes.TextDocument)), len(text_documents))
        self.assertNotEqual(td_url_prefix, self.mmif_pat_futr.metadata['mmif'])
        self.assertEqual(len(self.mmif_pat_futr.get_views_contain(DocumentTypes.TextDocument)), len(views_with_text_documents))
        self.assertNotEqual(td_url_prefix, self.mmif_min_past.metadata['mmif'])
        self.assertEqual(len(self.mmif_min_past.get_documents_by_type(DocumentTypes.TextDocument)), 0)
        self.assertNotEqual(td_url_prefix, self.mmif_min_futr.metadata['mmif'])
        self.assertEqual(len(self.mmif_min_futr.get_documents_by_type(DocumentTypes.TextDocument)), 0)
