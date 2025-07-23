import json
import tempfile
import unittest
import warnings
from io import StringIO
from pathlib import Path
import random
from unittest.mock import patch

import hypothesis_jsonschema
import pytest
from hypothesis import given, settings, HealthCheck
from jsonschema import ValidationError

import mmif as mmifpkg
from mmif.serialize import *
from mmif.serialize.model import *
from mmif.serialize.view import ContainsDict, ErrorDict
from mmif.vocabulary import AnnotationTypes, DocumentTypes, ThingType
from tests.mmif_examples import *

# Flags for skipping tests
DEBUG = False
SKIP_SCHEMA = True, "Not skipping TestSchema by default"
# skipping jsonschema testing until vocab-type level validation is fully implemented 
# (https://github.com/clamsproject/mmif-python/issues/309)
not_existing_attype = 'http://not.existing/type'
tester_appname = 'http://not.existing/app'


class TestMmif(unittest.TestCase):

    def setUp(self) -> None:
        self.mmif_examples_json = {k: json.loads(v) for k, v in MMIF_EXAMPLES.items()}

    @pytest.mark.skip("comparing two `Mmif` objs with an arbitrary file path included won't work until https://github.com/seperman/deepdiff/issues/357 is addressed")
    def test_init_from_bytes(self):
        mmif_from_str = Mmif(EVERYTHING_JSON)
        mmif_from_bytes = Mmif(EVERYTHING_JSON.encode('utf8'))
        self.assertEqual(mmif_from_str, mmif_from_bytes)

    def test_str_mmif_deserialize(self):
        for i, example in MMIF_EXAMPLES.items():
            if i.startswith('mmif_'):
                try:
                    mmif_obj = Mmif(example)
                except ValidationError:
                    self.fail(f"example {i}")
                self.assertEqual(mmif_obj.serialize(True), Mmif(mmif_obj.serialize()).serialize(True), f'Failed on {i}')

    def test_json_mmif_deserialize(self):
        for i, example in MMIF_EXAMPLES.items():
            example = json.loads(example)
            try:
                mmif_obj = Mmif(example)
            except ValidationError as ve:
                self.fail(ve.message)
            for document in mmif_obj.documents:
                self.assertIn('_type', document.__dict__)
            for view in mmif_obj.views:
                for annotation in view.annotations:
                    self.assertIn('_type', annotation.__dict__)
            self.assertTrue('id' in list(mmif_obj.views._items.values())[0].__dict__)
            self.assertEqual(mmif_obj.serialize(True), Mmif(json.loads(mmif_obj.serialize())).serialize(True), f'Failed on {i}')

    def test_str_vs_json_deserialize(self):
        for i, example in MMIF_EXAMPLES.items():
            if not i.startswith('mmif_'):
                continue
            str_mmif_obj = Mmif(example)
            json_mmif_obj = Mmif(json.loads(example))
            self.assertEqual(str_mmif_obj.serialize(True), json_mmif_obj.serialize(True), f'Failed on {i}')

    def test_bad_mmif_deserialize_no_metadata(self):
        self.mmif_examples_json['everything'].pop('metadata')
        json_str = json.dumps(self.mmif_examples_json['everything'])
        try:
            _ = Mmif(json_str)
            self.fail()
        except ValidationError:
            pass

    def test_bad_mmif_deserialize_no_documents(self):
        self.mmif_examples_json['everything'].pop('documents')
        json_str = json.dumps(self.mmif_examples_json['everything'])
        try:
            _ = Mmif(json_str)
            self.fail()
        except ValidationError:
            pass

    def test_bad_mmif_deserialize_no_views(self):
        self.mmif_examples_json['everything'].pop('views')
        json_str = json.dumps(self.mmif_examples_json['everything'])
        try:
            _ = Mmif(json_str)
            self.fail()
        except ValidationError:
            pass

    def test_sanitized_serialize(self):
        mmif: Mmif = Mmif(self.mmif_examples_json['everything'])
        mmif.views.empty()
        v = mmif.new_view()
        v.metadata.app = tester_appname
        v.new_contain(AnnotationTypes.TimeFrame)
        self.assertEqual(0, len(Mmif(mmif.serialize(sanitize=True))[v.id].metadata.contains))
        v.new_annotation(AnnotationTypes.Annotation, fps='30', document=v.id)
        self.assertEqual(1, len(Mmif(mmif.serialize())[v.id].metadata.contains))
        self.assertEqual(1, len(Mmif(mmif.serialize(sanitize=True))[v.id].metadata.contains))
        
    def test_new_view(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        old_view_count = len(mmif_obj.views)
        mmif_obj.new_view()  # just raise exception if this fails
        self.assertEqual(old_view_count+1, len(mmif_obj.views))

    def test_document_text(self):
        text = "Karen flew to New York."
        en = 'en'
        document = Document()
        document.id = 'm998'
        document.at_type = DocumentTypes.TextDocument
        document.properties.text_value = text
        self.assertEqual(document.properties.text_value, text)
        document.text_value = text
        self.assertEqual(document.text_value, text)
        document.properties.text_language = en
        serialized = document.serialize()
        plain_json = json.loads(serialized)
        deserialized = Document(serialized)
        self.assertEqual(deserialized.text_value, text)
        self.assertEqual(deserialized.text_language, en)
        self.assertEqual(deserialized.properties.text_value, text)
        self.assertEqual(deserialized.properties.text_language, en)
        self.assertEqual({'@value', '@language'}, plain_json['properties']['text'].keys())

    def test_document_empty_text(self):
        document = Document()
        document.id = 'm997'
        document.at_type = f"http://mmif.clams.ai/vocabulary/TextDocument/{DocumentTypes._typevers['TextDocument']}"
        serialized = document.serialize()
        deserialized = Document(serialized)
        self.assertEqual(deserialized.properties.text_value, '')
        self.assertEqual(deserialized.properties.text_language, '')

    def test_document(self):
        document = Document(FRACTIONAL_EXAMPLES['doc_only'])
        serialized = document.serialize()
        plain_json = json.loads(serialized)
        self.assertEqual({'@type', 'properties'}, plain_json.keys())
        self.assertEqual({'id', 'location', 'mime'}, plain_json['properties'].keys())

    def test_add_documents(self):
        document_json = json.loads(FRACTIONAL_EXAMPLES['doc_only'])
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        old_documents_count = len(mmif_obj.documents)
        mmif_obj.add_document(Document(document_json))  
        self.assertEqual(old_documents_count+1, len(mmif_obj.documents))
        view_obj = mmif_obj.get_view_by_id('v1')
        doc_obj = Document(document_json)
        view_obj.add_document(doc_obj)
        self.assertEqual(doc_obj.parent, view_obj.id)
        
    def test_get_documents_by_view_id(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        self.assertEqual(len(mmif_obj.get_documents_in_view('v6')), 25)
        self.assertEqual(mmif_obj.get_documents_in_view('v6')[0],
                         mmif_obj['v6:td1'])
        self.assertEqual(len(mmif_obj.get_documents_in_view('v1')), 0)
        self.assertEqual(len(mmif_obj.get_documents_in_view('xxx')), 0)
        new_document = Document(FRACTIONAL_EXAMPLES['doc_only'])
        mmif_obj.add_document(new_document)
        self.assertEqual(len(mmif_obj.get_documents_in_view('v4')), 1)

    def test_get_document_by_metadata(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        mmif_obj.add_document(Document(FRACTIONAL_EXAMPLES['doc_only']))
        self.assertEqual(len(mmif_obj.get_documents_by_property("mime", "video/mpeg")), 1)
        self.assertEqual(len(mmif_obj.get_documents_by_property("mime", "text/plain")), 2)  # one from the original 'v4', one from the newly added here

    def test_get_documents_by_app(self):
        tesseract_appid = 'http://mmif.clams.ai/apps/tesseract/0.2.1'
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        self.assertEqual(len(mmif_obj.get_documents_by_app(tesseract_appid)), 25)
        self.assertEqual(len(mmif_obj.get_documents_by_app('xxx')), 0)
        new_document = Document({'@type': f"http://mmif.clams.ai/vocabulary/TextDocument/{DocumentTypes._typevers['TextDocument']}",
                                 'properties': {'id': 'td999', 'text': {"@value": "HI"}}})
        mmif_obj['v6'].add_document(new_document)
        self.assertEqual(len(mmif_obj.get_documents_by_app(tesseract_appid)), 26)
        new_view = mmif_obj.new_view()
        new_view.metadata.app = tesseract_appid
        new_view.new_contain(DocumentTypes.TextDocument)
        new_view.add_document(new_document)
        self.assertEqual(len(mmif_obj.get_documents_by_app(tesseract_appid)), 27)

    def test_get_documents_by_type(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        # probably the worst way of testing...
        self.assertEqual(len(mmif_obj.get_documents_by_type(DocumentTypes.VideoDocument)), 1)
        self.assertEqual(len(mmif_obj.get_documents_by_type(DocumentTypes.TextDocument)), 26)

    def test_document_location_helpers(self):
        new_doc = Document()
        new_doc.id = "d1"
        file_path = "/var/archive/video-003.mp4"
        new_doc.properties.location = file_path
        self.assertEqual(new_doc.properties.location_scheme(), 'file')
        self.assertEqual(new_doc.properties.location_path_literal(), file_path)
        self.assertEqual(new_doc.properties.location_path_resolved(), file_path)
        # synonymous delegate method
        self.assertEqual(new_doc.location_path(), file_path)
        new_doc.location = "/var/archive/video-003.mp4"
        self.assertEqual(new_doc.location_scheme(), 'file')
        self.assertEqual(new_doc.location_path(), file_path)
        new_doc.location = f"ftp://localhost{file_path}"
        self.assertEqual(new_doc.location_scheme(), 'ftp')
        with self.assertRaises(ValueError):
            # because we don't have a handler for `ftp` scheme
            new_doc.location_path()
        self.assertEqual(new_doc.location_address(), f'localhost{file_path}')
        # round_trip = Document(new_doc.serialize())
        self.assertEqual(Document(new_doc.serialize()).serialize(), new_doc.serialize())
    
    def test_document_location_helpers_http(self):
        new_doc = Document()
        new_doc.id = "d1"
        new_doc.location = f"https://example.com/"
        self.assertEqual(new_doc.location_scheme(), 'https')
        try:
            path = new_doc.location_path()
            self.assertTrue(Path(path).exists())
            f = open(path)
            content = f.read()
            self.assertTrue(isinstance(content, str))
            f.close()
        except ValueError:
            pytest.fail("failed to get path from https location")
        # round_trip = Document(new_doc.serialize())
        self.assertEqual(Document(new_doc.serialize()).serialize(), new_doc.serialize())

    def test_get_documents_locations(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        self.assertEqual(1, len(mmif_obj.get_documents_locations(DocumentTypes.VideoDocument)))
        self.assertEqual(mmif_obj.get_document_location(DocumentTypes.VideoDocument), 
                         "file:///var/archive/video-002.mp4")
        self.assertEqual(mmif_obj.get_document_location(DocumentTypes.VideoDocument, path_only=True), 
                         "/var/archive/video-002.mp4")
        # TODO (angus-lherrou @ 9-23-2020): no text documents in documents list of raw.json,
        #  un-comment and fix if we add view searching to these methods
        # text document is there but no location is specified
        # self.assertEqual(0, len(mmif_obj.get_documents_locations(f'http://mmif.clams.ai/{__specver__}/vocabulary/TextDocument')))
        # self.assertEqual(mmif_obj.get_document_location(f'http://mmif.clams.ai/{__specver__}/vocabulary/TextDocument'), None)
        # audio document is not there
        self.assertEqual(0, len(mmif_obj.get_documents_locations(DocumentTypes.AudioDocument)))

    def test_get_view_by_id(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        try:
            _ = mmif_obj.get_view_by_id('v1')
        except KeyError:
            self.fail("didn't get v1")

        try:
            _ = mmif_obj.get_view_by_id('v555')
            self.fail("didn't raise exception on getting v55")
        except KeyError:
            pass

    def test_get_all_views_contain(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        views = mmif_obj.get_all_views_contain(AnnotationTypes.TimeFrame)
        self.assertEqual(4, len(views))
        # there is not such thing as `v0` of this type
        # but when you query views with a string (not by the AnnotationType object)
        # it should not perfomr "fuzzy" match and instead should do full string to string match
        views = mmif_obj.get_all_views_contain('http://mmif.clams.ai/vocabulary/TimeFrame/v0')
        self.assertEqual(0, len(views))
        views = mmif_obj.get_views_contain(DocumentTypes.TextDocument)
        self.assertEqual(2, len(views))
        views = mmif_obj.get_all_views_contain('http://vocab.lappsgrid.org/SemanticTag')
        self.assertEqual(1, len(views))
        views = mmif_obj.get_views_contain(
            AnnotationTypes.TimeFrame,
            DocumentTypes.TextDocument,
            AnnotationTypes.Alignment,
        )
        self.assertEqual(1, len(views))
        views = mmif_obj.get_all_views_contain(not_existing_attype)
        self.assertEqual(0, len(views))

    def test_get_view_contains(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        view = mmif_obj.get_view_contains('http://vocab.lappsgrid.org/SemanticTag')
        self.assertIsNotNone(view)
        self.assertEqual('v8', view.id)
        view = mmif_obj.get_view_contains([
            AnnotationTypes.TimeFrame,
            DocumentTypes.TextDocument,
            AnnotationTypes.Alignment,
        ])
        self.assertIsNotNone(view)
        self.assertEqual('v4', view.id)
        view = mmif_obj.get_view_contains(not_existing_attype)
        self.assertIsNone(view)

    def test_get_views_for_document(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        
        # top-level document
        self.assertEqual(5, len(mmif_obj.get_views_for_document('m1')))
        # generated document
        self.assertEqual(2, len(mmif_obj.get_views_for_document('v4:td1')))
        # non-existing document
        self.assertEqual(0, len(mmif_obj.get_views_for_document('m321321')))

    def test_get_alignments(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        views_and_alignments = mmif_obj.get_alignments(DocumentTypes.TextDocument, AnnotationTypes.TimeFrame)
        self.assertEqual(1, len(views_and_alignments))
        self.assertTrue('v4' in views_and_alignments)
        self.assertEqual(1, len(views_and_alignments['v4']))
        views_and_alignments = mmif_obj.get_alignments("http://vocab.lappsgrid.org/Token", AnnotationTypes.TimeFrame)
        self.assertEqual(1, len(views_and_alignments))
        self.assertTrue('v4' in views_and_alignments)
        self.assertEqual(28, len(views_and_alignments['v4']))
        views_and_alignments = mmif_obj.get_alignments(DocumentTypes.TextDocument, AnnotationTypes.BoundingBox)
        self.assertEqual(1, len(views_and_alignments))
        self.assertTrue('v6' in views_and_alignments)
    
    def test_cache_alignment(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        views_and_alignments = mmif_obj.get_alignments(DocumentTypes.TextDocument, AnnotationTypes.TimeFrame)
        for vid, alignments in views_and_alignments.items():
            v = mmif_obj[vid]
            for alignment in alignments:
                s = mmif_obj[alignment.get('source')]
                t = mmif_obj[alignment.get('target')]
                self.assertTrue(s.aligned_to_by(alignment).id.endswith(t.id))
                self.assertTrue(t.aligned_to_by(alignment).id.endswith(s.id))
            with self.assertWarns(RuntimeWarning):
                # this should not raise a warning, because we are using the cache
                v.new_annotation(AnnotationTypes.Alignment, source=alignment.get('source'), target='non-existing-target-id')

    def test_new_view_id(self):
        p = Mmif.view_prefix
        mmif_obj = Mmif(validate=False)
        a_view = mmif_obj.new_view()
        self.assertEqual(a_view.id, f'{p}0')
        b_view = View()
        b_view.id = f'{p}2'
        mmif_obj.add_view(b_view)
        self.assertEqual({f'{p}0', f'{p}2'}, set(mmif_obj.views._items.keys()))
        c_view = mmif_obj.new_view()
        self.assertEqual(c_view.id, f'{p}3')
        d_view = View()
        d_view.id = 'v4'
        mmif_obj.add_view(d_view)
        e_view = mmif_obj.new_view()
        self.assertEqual(e_view.id, f'{p}4')
        self.assertEqual(len(mmif_obj.views), 5)

    def test_get_annotations_between_time(self):
        token_type = "http://vocab.lappsgrid.org/Token"
        # Below tokens are obtained by 'jq' in CLI using command:
        # jq '[
        # .views[3].annotations |
        # .[] |
        # select(."@type"=="http://vocab.lappsgrid.org/Token")] |
        # sort_by(.properties.id | ltrimstr("t") | tonumber) |
        # map(.properties.word)' <examples>.json
        tokens_in_order = ["Hello",
                           ",",
                           "this",
                           "is",
                           "Jim",
                           "Lehrer",
                           "with",
                           "the",
                           "NewsHour",
                           "on",
                           "PBS",
                           ".",
                           "In",
                           "the",
                           "nineteen",
                           "eighties",
                           ",",
                           "barking",
                           "dogs",
                           "have",
                           "increasingly",
                           "become",
                           "a",
                           "problem",
                           "in",
                           "urban",
                           "areas",
                           "."]
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])

        # Test case 1: All token annotations are selected
        selected_token_anns = [ann for ann in mmif_obj.get_annotations_between_time(0, 22000) if ann.is_type(token_type)]
        self.assertEqual(28, len(selected_token_anns))
        for i, ann in enumerate(selected_token_anns):
            self.assertEqual(tokens_in_order[i], ann.get_property("word"))

        # Test case 2: No token annotation are selected
        selected_token_anns = list(mmif_obj.get_annotations_between_time(0, 5, time_unit="seconds"))
        self.assertEqual(4, len(list(selected_token_anns))) 
        for ann in selected_token_anns:
            self.assertFalse(ann.is_type(token_type))

        # Test case 3(a): Partial tokens are selected (involve partial overlap)
        selected_token_anns = mmif_obj.get_annotations_between_time(7, 10, time_unit="seconds", 
                                                                    at_types=['http://vocab.lappsgrid.org/Token'])
        self.assertEqual(tokens_in_order[3:9], [ann.get_property("word") for ann in selected_token_anns])

        # Test case 3(b): Partial tokens are selected (only full overlap)
        selected_token_anns = mmif_obj.get_annotations_between_time(11500, 14600, 
                                                                    at_types=['http://vocab.lappsgrid.org/Token'])
        self.assertEqual(tokens_in_order[12:17], [ann.get_property("word") for ann in selected_token_anns])

    def test_add_document(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        med_obj = Document(FRACTIONAL_EXAMPLES['doc_only'])
        mmif_obj.add_document(med_obj)
        try:
            mmif_obj.add_document(med_obj)
            self.fail("didn't raise exception on duplicate ID add")
        except KeyError:
            pass
        try:
            mmif_obj.add_document(med_obj, overwrite=True)
        except KeyError:
            self.fail("raised exception on duplicate ID add when overwrite was set to True")

    def test_empty_source_mmif(self):
        mmif_obj = Mmif(validate=False)
        med_obj = Document(FRACTIONAL_EXAMPLES['doc_only'])
        mmif_obj.add_document(med_obj)
        Mmif.validate(str(mmif_obj))

    def test_add_view(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        view_obj = View()
        view_obj.id = 'v400'
        mmif_obj.add_view(view_obj)
        try:
            mmif_obj.add_view(view_obj)
            self.fail("didn't raise exception on duplicate ID add")
        except KeyError:
            pass
        try:
            mmif_obj.add_view(view_obj, overwrite=True)
        except KeyError:
            self.fail("raised exception on duplicate ID add when overwrite was set to True")
    
    @pytest.mark.skip("comparing two `Mmif` objs with an arbitrary file path included won't work until https://github.com/seperman/deepdiff/issues/357 is addressed")
    def test_eq_checking_order(self):
        mmif1 = Mmif(EVERYTHING_JSON)
        mmif2 = Mmif(EVERYTHING_JSON)
        view1 = View()
        view1.id = 'v99'
        view2 = View()
        view2.id = 'v98'
        mmif1.add_view(view1)
        mmif1.add_view(view2)
        mmif2.add_view(view2)
        mmif2.add_view(view1)
        self.assertFalse(mmif1 == mmif2)

        mmif3 = Mmif(EVERYTHING_JSON)
        mmif4 = Mmif(EVERYTHING_JSON)
        mmif3.add_view(view1)
        mmif3.add_view(view2)
        mmif4.add_view(view1)
        mmif4.add_view(view2)
        self.assertTrue(mmif3 == mmif4)

    def test___getitem__(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        self.assertIsInstance(mmif_obj['m1'], Document)
        self.assertIsInstance(mmif_obj['v5'], View)
        self.assertIsInstance(mmif_obj['v5:bb1'], Annotation)
        with self.assertRaises(KeyError):
            _ = mmif_obj['asdf']
        a_view = View()
        a_view.id = 'm1'
        with self.assertRaises(KeyError):
            mmif_obj.add_view(a_view)

    def test___contains__(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        self.assertTrue('views' in mmif_obj)
        self.assertTrue('v5' in mmif_obj)
        self.assertFalse('v432402' in mmif_obj)
    
    def test_get_label(self):
        v = View()
        a = v.new_annotation(AnnotationTypes.TimeFrame, label="speech")
        self.assertEqual(a._get_label(), "speech")
        a = v.new_annotation(AnnotationTypes.TimeFrame, frameType="speech")
        self.assertEqual(a._get_label(), "speech")
        a = v.new_annotation(AnnotationTypes.BoundingBox, label="text")
        self.assertEqual(a._get_label(), "text")
        a = v.new_annotation(AnnotationTypes.BoundingBox, boxType="text")
        self.assertEqual(a._get_label(), "text")
        with self.assertRaises(KeyError):
            a = v.new_annotation(AnnotationTypes.BoundingBox)
            _ = a._get_label()

    def test_get_anchor_point(self):
        mmif = Mmif(validate=False)
        v1 = mmif.new_view()
        v2 = mmif.new_view()
        tps = []
        tf2_targets_with_vid = []
        for timepoint in range(5):
            tp = v1.new_annotation(AnnotationTypes.TimePoint, timePoint=timepoint)
            tps.append(tp)
            tf2_targets_with_vid.append(f"{tp.id}")
        # tf1 used to be here and was used when long_id was less forced
        tf2 = v2.new_annotation(AnnotationTypes.TimeFrame, targets=tf2_targets_with_vid)
        tf3 = v2.new_annotation(AnnotationTypes.TimeFrame, start=100, end=200)
        self.assertEqual(mmif.get_start(tf3), 100)
        self.assertEqual(mmif.get_end(tf3), 200)
        self.assertEqual(mmif._get_linear_anchor_point(tf3, start=True), 100)
        self.assertEqual(mmif._get_linear_anchor_point(tf3, start=False), 200)
        self.assertEqual(mmif._get_linear_anchor_point(tf2, start=True), 0)
        self.assertEqual(mmif._get_linear_anchor_point(tf2, start=False), 4)
        self.assertEqual(mmif._get_linear_anchor_point(mmif[tf2_targets_with_vid[0]], start=True), 0)
        self.assertEqual(mmif._get_linear_anchor_point(mmif[tf2_targets_with_vid[-1]], start=False), 4)
        self.assertEqual(mmif._get_linear_anchor_point(tps[0], start=True), 0)
        self.assertEqual(mmif._get_linear_anchor_point(tps[-1], start=False), 4)
        non_region_ann = v2.new_annotation(AnnotationTypes.Alignment)
        with self.assertRaises(ValueError):
            _ = mmif._get_linear_anchor_point(non_region_ann, start=True)
    
    def test_cannot_get_anchor_point(self):
        # when an annotation has ambiguous anchors (for example, `targets`
        # and `start`/`end` properties exist together) getting an anchor 
        # point is impossbiel 
        mmif = Mmif(validate=False)
        v1 = mmif.new_view()
        spoint = random.randint(0, 10000)
        epoint = random.randint(spoint, 10000 + spoint)
        tps = v1.new_annotation(AnnotationTypes.TimePoint, timePoint=spoint)
        tpe = v1.new_annotation(AnnotationTypes.TimePoint, timePoint=epoint)
        tf = v1.new_annotation(AnnotationTypes.TimeFrame, targets=[tps.id, tpe.id], start=spoint, end=epoint)
        with self.assertRaises(ValueError):
            _ = mmif.get_start(tf)
        with self.assertRaises(ValueError):
            _ = mmif.get_end(tf)
        with self.assertRaises(ValueError):
            _ = mmif._get_linear_anchor_point(tf, start=True)
        with self.assertRaises(ValueError):
            _ = mmif._get_linear_anchor_point(tf, start=False)
        # in fact, MMIF should not allow de-/serialization of such ambiguous annotations
        with self.assertRaises(ValueError):
            _ = Mmif(mmif.serialize(), validate=False)
        
        

class TestMmifObject(unittest.TestCase):

    def setUp(self) -> None:
        ...

    def test_load_json_on_str(self):
        self.assertTrue("_type" in MmifObject._load_json('{ "@type": "some_type", "@value": "some_value"}').keys())
        self.assertTrue("_value" in MmifObject._load_json('{ "@type": "some_type", "@value": "some_value"}').keys())

    def test_load_json_on_dict(self):
        json_dict = json.loads('{ "@type": "some_type", "@value": "some_value"}')
        self.assertTrue("_type" in MmifObject._load_json(json_dict.copy()).keys())
        self.assertTrue("_value" in MmifObject._load_json(json_dict.copy()).keys())

    def test_load_json_on_other(self):
        try:
            MmifObject._load_json(123)
            self.fail()
        except TypeError:
            pass

    def test_under_at_swap(self):
        text = Text()
        text.value = "asdf"
        text.lang = "en"
        self.assertTrue(hasattr(text, '_value'))
        self.assertTrue(hasattr(text, '_language'))
        plain_json = json.loads(text.serialize())
        self.assertIn('@value', plain_json.keys())
        self.assertIn('@language', plain_json.keys())

    @pytest.mark.skip("TODO: does not work with text examples that are a mixture of old (short-id) and new (long-id) annotations")
    def test_print_mmif(self):
        with patch('sys.stdout', new=StringIO()) as fake_out:
            mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
            print(mmif_obj)
            self.assertEqual(json.loads(MMIF_EXAMPLES['everything']), json.loads(fake_out.getvalue()))


class TestGetItem(unittest.TestCase):

    def setUp(self) -> None:
        self.mmif_obj = Mmif(MMIF_EXAMPLES['everything'])

    def test_mmif_getitem_document(self):
        try:
            m1 = self.mmif_obj['m1']
            self.assertIs(m1, self.mmif_obj.documents.get('m1'))
        except TypeError:
            self.fail("__getitem__ not implemented")
        except KeyError:
            self.fail("didn't get document 'm1'")

    @pytest.mark.skip("no longer id conflict after long_id is enforced everywhere (1.1.0)")
    def test_mmif_getitem_idconflict(self):
        # TODO (krim @ 6/13/25): major re-write when addressing #295
        m = Mmif(validate=False)
        v1 = m.new_view()
        v1.id = 'v1'
        v2 = m.new_view()
        v2.id = 'v1'
        with pytest.raises(KeyError):
            _ = m['v1']

        m = Mmif(validate=False)
        v1 = m.new_view()
        v1a = v1.new_annotation(AnnotationTypes.Annotation, id='a1')
        v2 = m.new_view()
        v2a = v2.new_annotation(AnnotationTypes.Annotation, id='a1')
        self.assertIsNotNone(m[v1.id])
        self.assertIsNotNone(m[v2.id])
        # conflict short IDs
        self.assertEqual(v1a._short_id, v2a._short_id)
        with pytest.raises(KeyError):
            _ = m['a1']
        self.assertIsNotNone(m[v1a.id])
        self.assertIsNotNone(m[v2a.id])

    def test_mmif_getitem_view(self):
        try:
            v1 = self.mmif_obj['v1']
            self.assertIs(v1, self.mmif_obj.views.get('v1'))
        except TypeError:
            self.fail("__getitem__ not implemented")
        except KeyError:
            self.fail("didn't get view 'v1'")

    def test_mmif_getitem_annotation(self):
        try:
            v1_bb1 = self.mmif_obj['v5:bb1']
            self.assertIs(v1_bb1, self.mmif_obj.views.get('v5').annotations.get('v5:bb1'))
        except TypeError:
            self.fail("__getitem__ not implemented")
        except KeyError:
            self.fail("didn't get annotation 'v5:bb1'")

    def test_mmif_fail_getitem_toplevel(self):
        try:
            _ = self.mmif_obj['v500']
            self.fail("didn't raise exception on bad getitem")
        except KeyError:
            pass

    def test_mmif_fail_getitem_annotation_no_view(self):
        try:
            _ = self.mmif_obj['v59:s1']
            self.fail("didn't raise exception on annotation getitem on bad view")
        except KeyError:
            pass

    def test_mmif_fail_getitem_no_annotation(self):
        try:
            _ = self.mmif_obj['v1:bb1']
            self.fail("didn't raise exception on bad annotation getitem")
        except KeyError:
            pass

    def test_view_getitem(self):
        try:
            s1 = self.mmif_obj['v1:s1']
            self.assertIs(s1, self.mmif_obj.get_view_by_id('v1').get_annotation_by_id('v1:s1'))
        except TypeError:
            self.fail("__getitem__ not implemented")
        except KeyError:
            self.fail("didn't get annotation 's1'")


class TestView(unittest.TestCase):

    def setUp(self) -> None:
        self.mmif_examples_json = {k: json.loads(v) for k, v in MMIF_EXAMPLES.items()}
        self.view_json = self.mmif_examples_json['everything']['views'][0]
        self.view_obj = View(self.view_json)
        self.maxDiff = None

    def test_init(self):
        view_from_json = View(self.view_json)
        view_from_str = View(json.dumps(self.view_json))
        view_from_bytes = View(json.dumps(self.view_json).encode('utf-8'))
        self.assertEqual(view_from_str, view_from_json)
        self.assertEqual(view_from_str, view_from_bytes)
        self.assertEqual(json.loads(view_from_json.serialize()), json.loads(view_from_str.serialize()))
        self.assertEqual(json.loads(view_from_bytes.serialize()), json.loads(view_from_str.serialize()))

    def test_annotation_order_preserved(self):
        view_serial = self.view_obj.serialize()
        for original, new in zip(self.view_json['annotations'],
                                 json.loads(view_serial)['annotations']):

            o = original['properties']['id']
            n = new['properties']['id']
            # TODO (krim @ 6/29/25): stopgap to handle "old" MMIF (<1.1.x) with short IDs
            short_id_len = min(len(o), len(n))
            o = o[-short_id_len:]
            n = n[-short_id_len:]
            assert o == n, f"{o} is not {n}"

    def test_view_metadata(self):
        vmeta = ViewMetadata()
        vmeta['app'] = 'fdsa'
        vmeta['random_key'] = 'random_value'
        serialized = vmeta.serialize()
        deserialized = ViewMetadata(serialized)
        self.assertEqual(vmeta, deserialized)

    def test_view_parameters(self):
        vmeta = ViewMetadata()
        vmeta.add_parameter('pretty', str(False))
        self.assertEqual(len(vmeta.parameters), 1)
        self.assertEqual(vmeta.get_parameter('pretty'), str(False))
        with pytest.raises(KeyError):
            vmeta.get_parameter('not_exist')
            
    def test_view_configuration(self):
        vmeta = ViewMetadata()
        vmeta.add_app_configuration('pretty', False)
        self.assertEqual(len(vmeta.appConfiguration), 1)
        self.assertEqual(vmeta.get_app_configuration('pretty'), False)
        with pytest.raises(KeyError):
            vmeta.get_app_configuration('not_exist')

    def test_view_parameters_batch_adding(self):
        vmeta = ViewMetadata()
        vmeta.add_parameters(pretty=str(True), validate=str(False))
        self.assertEqual(len(vmeta.parameters), 2)
        vmeta = ViewMetadata()
        vmeta.add_parameters(**{'pretty': str(True), 'validate': str(False)})
        self.assertEqual(len(vmeta.parameters), 2)

    def test_add_warning(self):
        vmeta = ViewMetadata()
        w1 = Warning('first_warning')
        w2 = UserWarning('second warning')
        vmeta.add_warnings(w1, w2)
        self.assertEqual(len(vmeta.warnings), 2)
        for warning in vmeta.warnings:
            self.assertTrue(isinstance(warning, str))
            self.assertTrue('warning' in warning.lower())

    def test_new_contain(self):
        # can add by str at_type
        self.view_obj.new_contain("http://vocab.lappsgrid.org/Token")
        # can add by obj at_type
        self.view_obj.new_contain(AnnotationTypes.TimePoint)
        # can add details
        self.view_obj.new_contain(AnnotationTypes.TimeFrame, **{"frameType": "speech"})
        with pytest.raises(ValueError):
            # empty at_type is not allowed
            self.view_obj.new_contain("")
        
    def test_add_annotation(self):
        anno_obj = Annotation(self.mmif_examples_json['everything']['views'][6]['annotations'][2])
        old_len = len(self.view_obj.annotations)
        self.view_obj.add_annotation(anno_obj)  # raise exception if this fails
        self.assertEqual(old_len+1, len(self.view_obj.annotations))
        self.assertIn('http://vocab.lappsgrid.org/NamedEntity', self.view_obj.metadata.contains)
        _ = self.view_obj.serialize()  # raise exception if this fails
        self.view_obj.new_annotation(AnnotationTypes.TimePoint)
        roundtrip = View(json.loads(self.view_obj.serialize()))
        self.assertEqual(roundtrip, self.view_obj)

    def test_new_annotation(self):
        self.view_obj.new_annotation('Relation', 'relation1')
        self.assertIn('Relation', self.view_obj.metadata.contains)
        a1 = self.view_obj.new_annotation('TimeFrame')
        a2 = self.view_obj.new_annotation('TimeFrame')
        self.assertNotEqual(a1.id, a2.id)
        self.assertEqual(a1.id.rsplit('_', 1)[0], a2.id.rsplit('_', 1)[0])
        a3 = self.view_obj.new_annotation('TimeFrame', frameType='speech', start=100, end=500)
        self.assertEqual(4, len(a3.properties))

    def test_new_textdocument(self):
        english_text = 'new document is added to the view.'
        td1 = self.view_obj.new_textdocument(english_text)
        td2 = self.view_obj.new_textdocument('새로운 문서가 추가되었습니다', 'ko')
        self.assertIn(DocumentTypes.TextDocument, self.view_obj.metadata.contains)
        self.assertFalse('parent' in td1)
        self.assertTrue(td1.properties.text_value == td1.text_value)
        self.assertNotEqual(td1.text_language, td2.text_language)
        self.assertEqual(english_text, td1.text_value)
        self.assertEqual(td1, self.view_obj.annotations.get(td1.id))
        td3 = self.view_obj.new_textdocument(english_text, mime='plain/text')
        self.assertEqual(td1.text_value, td3.text_value)
        self.assertEqual(len(td1.properties), len(td3.properties) - 1)

    def test_parent(self):
        mmif_obj = Mmif(self.mmif_examples_json['everything'])
        self.assertTrue(all(anno.parent == v.id for v in mmif_obj.views for anno in mmif_obj.get_view_by_id(v.id).annotations))
    
    def test_non_existing_parent(self):
        anno_obj = Annotation(FRACTIONAL_EXAMPLES['doc_only'])
        with self.assertRaises(ValueError):
            p = anno_obj.parent
        with self.assertWarns(DeprecationWarning):
            anno_obj.parent = 'v1'

    def test_get_by_id(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        mmif_obj['m1']
        mmif_obj['v4:td1']
        with self.assertRaises(KeyError):
            mmif_obj['m55']
        with self.assertRaises(KeyError):
            mmif_obj['v1:td1']
        view_obj = mmif_obj['v4']
        td1 = view_obj['v4:td1']
        self.assertEqual(td1.properties.mime, 'text/plain')
        a1 = view_obj['v4:a1']
        self.assertEqual(a1.at_type, AnnotationTypes.Alignment)
        with self.assertRaises(KeyError):
            view_obj['completely-unlikely-annotation-id']
            
    def test_get_annotations(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        # simple search by at_type
        annotations = list(mmif_obj['v3'].get_annotations(AnnotationTypes.TimeFrame))
        self.assertEqual(len(annotations), 2)
        # simple search fail by at_type
        annotations = list(mmif_obj['v3'].get_annotations(not_existing_attype))
        self.assertEqual(len(annotations), 0)
        # at_type + property
        annotations = list(mmif_obj['v3'].get_annotations(AnnotationTypes.TimeFrame, frameType='speech'))
        self.assertEqual(len(annotations), 1)
        # just property
        annotations = list(mmif_obj['v3'].get_annotations(frameType='speech'))
        self.assertEqual(len(annotations), 1)
        # at_type + annotation metadata
        annotations = list(mmif_obj['v3'].get_annotations(AnnotationTypes.TimeFrame, timeUnit='milliseconds'))
        self.assertEqual(len(annotations), 2)
        # non-existing annotations
        with pytest.raises(StopIteration):
            annotations = mmif_obj['v3'].get_annotations(AnnotationTypes.TimeFrame, timeUnit='seconds')
            next(annotations)
        
    def test_errordict(self):
        error = ErrorDict({"message": "some message", "stackTrace": "some trace"})
        self.assertIsNotNone(error)
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        aview = mmif_obj.new_view()
        ann = Annotation()
        ann.at_type = AnnotationTypes.VideoObject
        ann.id = 'a1'
        aview.add_annotation(ann)
        
        # before error is set
        self.assertTrue("contains" in aview.metadata)
        self.assertEqual(len(aview.metadata.contains), 1)
        self.assertEqual(len(aview.annotations), 1)
        self.assertFalse("error" in aview.metadata)
        
        # after error is set
        aview.set_error("some message", "some trace")
        self.assertEqual(len(aview.annotations), 0)
        self.assertEqual(len(aview.metadata.contains), 0)
        self.assertFalse("contains" in aview.metadata)
        self.assertTrue("error" in aview.metadata)
        self.assertEqual(aview.metadata.error.message, "some message")
        
        # serialize trip
        aview_json = json.loads(aview.serialize())
        self.assertTrue("error" in aview_json['metadata'])
        self.assertFalse("contains" in aview_json['metadata'])
        roundtrip = View(aview_json)
        self.assertTrue("error" in roundtrip.metadata)
        self.assertFalse("contains" in roundtrip.metadata)

    def test_error_to_text(self):
        err_msg = "some message"
        err_trace = "some trace line1\n\ttrace line 2\n\ttrace line 3"
        error = ErrorDict({"message": err_msg, "stackTrace": err_trace})
        mmif_obj = Mmif(validate=False)
        aview = mmif_obj.new_view()
        aview.set_error(err_msg, err_trace)
        self.assertTrue(aview.has_error())
        aview.metadata.error = error
        self.assertTrue(aview.has_error())
        self.assertFalse(aview.has_warnings())
        # assumes the "text" representation of the error contains the message and the trace
        self.assertGreaterEqual(len(aview.metadata.get_error_as_text()), len(err_msg) + len(err_trace))
        self.assertIn(err_msg, aview.metadata.get_error_as_text())
        self.assertIn(err_trace, aview.metadata.get_error_as_text())
        self.assertEqual(aview.metadata.get_error_as_text(), aview.get_error())
        self.assertEqual(1, len(mmif_obj.get_views_with_error()))
        self.assertEqual(aview.id, mmif_obj.get_view_with_error().id)
        self.assertEqual(aview.metadata.get_error_as_text(), mmif_obj.get_last_error())
        
        # and then test for custom error objects
        aview.metadata.error = {'errorName': 'custom error', 'errorDetails': 'some details', 'errorTimestamp': 'now'}
        self.assertTrue(aview.has_error())
        self.assertTrue(isinstance(mmif_obj.get_last_error(), str))
        err_str = 'custom error as a single long string'
        aview.metadata.error = err_str
        self.assertTrue(aview.has_error())
        self.assertTrue(isinstance(mmif_obj.get_last_error(), str))
        self.assertIn(err_str, mmif_obj.get_last_error())
        aview.metadata.error = {}  # no error
        self.assertFalse(aview.has_error())
        with self.assertRaises(KeyError):
            _ = aview.metadata.get_error_as_text()
        self.assertIsNone(aview.get_error())
        self.assertIsNone(mmif_obj.get_last_error())


class TestAnnotation(unittest.TestCase):
    # TODO (angus-lherrou @ 7/27/2020): testing should include validation for required attrs
    #  once that is implemented (issue #23)
    def setUp(self) -> None:
        self.data = {}
        for i, example in MMIF_EXAMPLES.items():
            self.data[i] = {'string': example,
                            'json': json.loads(example),
                            'mmif': Mmif(example),
                            'annotations': [annotation for view in json.loads(example)['views'] for annotation in view['annotations']]}

    def test_annotation_properties_wrapper(self):
        ann_obj = Annotation(self.data['everything']['annotations'][0])
        props_json = self.data['everything']['annotations'][0]['properties']
        props_obj = AnnotationProperties(props_json)
        self.assertEqual(ann_obj.properties, props_obj)
        ann_obj.add_property('new_prop', 'new_prop_value')
        self.assertEqual(ann_obj.properties['new_prop'], 'new_prop_value')
        for k in ann_obj.properties.keys():
            self.assertTrue(k is not None)
            self.assertTrue(ann_obj.properties[k] is not None)
        for k, v in ann_obj.properties.items():
            self.assertTrue(k is not None)
            self.assertTrue(v is not None)
            
    def test_annotation_properties(self):
        props_json = self.data['everything']['annotations'][0]['properties']
        props_obj = AnnotationProperties(props_json)
        self.assertEqual(props_json, json.loads(props_obj.serialize()))
        self.assertEqual(props_json['id'], props_obj.id)
        self.assertEqual(props_json['start'], props_obj.get('start'))
        self.assertEqual(props_json['start'], props_obj.get('start'))
        self.assertEqual(props_json['end'], props_obj.get('end'))
        # normal deletion
        props_obj['new_prop'] = 'new_prop_value'
        del props_obj['new_prop']
        self.assertNotIn('baz', props_obj)
        
        # deletion of a required property
        with self.assertRaises(AttributeError):
            del props_obj['id']
        
        # deletion of a non-existing property
        with self.assertRaises(KeyError):
            del props_obj['notfound']

    def test_empty_annotation_property(self):
        a = Annotation({
            '@type': ThingType.Thing,
            'properties': {
                'id': 'a1',
                'empty_str_prop': "",
                'nonempty_str_prop': "string",
                'empty_lst_prop': []
            }
        })
        self.assertEqual(a['empty_str_prop'], "")
        self.assertEqual(a['empty_lst_prop'], [])
        self.assertEqual(4, len(a.properties.keys()))
        a_serialized = a.serialize()
        json.loads(a_serialized)
        self.assertEqual(json.loads(a_serialized)['properties']['empty_str_prop'], "")
        self.assertEqual(json.loads(a_serialized)['properties']['empty_lst_prop'], [])
        a_roundtrip = Annotation(a_serialized)
        self.assertEqual(a_roundtrip.get_property('empty_str_prop'), "")
        self.assertEqual(a_roundtrip.get_property('empty_lst_prop'), [])
        self.assertEqual(4, len(a.properties.keys()))

    def test_annotation_ephemeral_properties(self):
        mmif = self.data['everything']['mmif']
        first_view_first_ann = mmif['v1']['v1:s1']
        self.assertFalse('document' in first_view_first_ann.properties.keys())
        self.assertTrue('document' in first_view_first_ann._props_ephemeral.keys())
        self.assertEqual('m1', first_view_first_ann.get_property('document'))

    def test_annotation_ephemeral_start_end_props(self):
        mmif_obj = Mmif(validate=False)
        view = mmif_obj.new_view()
        # Create target annotations (e.g., TimePoint)
        tp1 = view.new_annotation(AnnotationTypes.TimePoint, timePoint=0)
        tp2 = view.new_annotation(AnnotationTypes.TimePoint, timePoint=10)
        # Create an annotation with targets, but no start/end
        tf = view.new_annotation(AnnotationTypes.TimeFrame, targets=[tp1.id, tp2.id])
        # After deserialization, ephemeral start/end should be set
        mmif_roundtrip = Mmif(mmif_obj.serialize(), validate=False)
        tf_roundtrip = mmif_roundtrip[view.id][tf.id]
        assert 'start' in tf_roundtrip._props_ephemeral
        assert 'end' in tf_roundtrip._props_ephemeral
        assert tf_roundtrip._props_ephemeral['start'] == 0
        assert tf_roundtrip._props_ephemeral['end'] == 10
        
    def test_property_types(self):
        ann = Annotation()
        ann.id = 'a1'
        for a_type, a_value in zip([str, int, float, bool, type(None)], ['str', '1', '1.1', False, None]):
            ann.add_property(a_type.__name__, a_value)
            ann.add_property(a_type.__name__ + '_list', [a_value])
        ann.add_property("list_list", [[1], [2]])
        ann.add_property("dict", {"k1": "v1"})
        ann.add_property("dict_list", {"k1": ["v1"]})

    @pytest.mark.skip("TODO: does not work with text examples that are a mixture of old (short-id) and new (long-id) annotations")
    def test_add_property(self):
        for i, datum in self.data.items():
            try:
                mmif = Mmif(datum['json'])
                for j, view in enumerate(mmif.views):
                    view_id = view.id
                    first_ann = list(view.annotations._items.values())[0]
                    props = first_ann.properties
                    first_ann_id = props['id']
                    removed_prop_key, removed_prop_value = list(props.items())[-1]
                    props.pop(removed_prop_key)
                    new_mmif = Mmif(datum['json'])
                    new_mmif.get_view_by_id(view_id).annotations[first_ann_id].add_property(removed_prop_key, removed_prop_value)
                    self.assertEqual(json.loads(datum['string'])['views'][j],
                                     json.loads(new_mmif.serialize())['views'][j],
                                     f'Failed on {i}, {view_id}')
            except ValidationError:
                continue
    
    def test_get_property(self):
        v = View()
        a = v.new_annotation(AnnotationTypes.Annotation)
        a.add_property('prop1', 'value1')
        self.assertEqual(a.properties['prop1'], 'value1')
        self.assertEqual(a['properties']['prop1'], 'value1')
        self.assertEqual(a.get_property('prop1'), 'value1')
        self.assertEqual(a['prop1'], 'value1')
        self.assertEqual(a.id, a['id'])
        self.assertEqual(a.id, a.get_property('id'))
    
    def test_get_property_with_alias(self):
        v = View()
        tf1 = v.new_annotation(AnnotationTypes.TimeFrame, start=0, end=10, label="speech")
        # tf3 = v.new_annotation(AnnotationTypes.TimeFrame, start=20, end=30, frameType="speech")
        self.assertEqual(tf1.get_property('label'), "speech")
        self.assertEqual(tf1.get_property('frameType'), "speech")
        with warnings.catch_warnings(record=True) as caught_warnings:
            # should throw a warning for alias collision
            tf2 = v.new_annotation(AnnotationTypes.BoundingBox, start=10, end=20,
                                   label="nonspeech", boxType="nonspeech")
            # again, should throw a warning for alias collision for frameType and label, 
            # but not for frameLabel
            tf3 = v.new_annotation(AnnotationTypes.TimeFrame, start=10, end=20, 
                                   frameType="nonspeech", label="nonspeech", frameLabel="speech")
            self.assertEqual(2, len(caught_warnings))
            self.assertTrue("nonspeech", tf3.get_property('frameType'))
            self.assertTrue("nonspeech", tf3.get_property('label'))
            self.assertTrue("speech", tf3.get_property('frameLabel'))

    def test_change_id(self):
        anno_obj: Annotation = self.data['everything']['mmif']['v5:bb1']

        anno_obj.id = 'v5:bb200'
        self.assertEqual('v5:bb200', anno_obj.id)
        self.assertEqual('v5:bb200', anno_obj._short_id)

        serialized = json.loads(anno_obj.serialize())
        new_id = serialized['properties']['id']
        self.assertEqual('v5:bb200', new_id)

        serialized_mmif = json.loads(self.data['everything']['mmif'].serialize())
        new_id_from_mmif = serialized_mmif['views'][4]['annotations'][0]['properties']['id']
        self.assertEqual('v5:bb200', new_id_from_mmif)


class TestDocument(unittest.TestCase):

    def setUp(self) -> None:
        self.data = {i: {'string': example,
                         'json': json.loads(example),
                         'mmif': Mmif(example),
                         'documents': json.loads(example)['documents']}
                     for i, example in MMIF_EXAMPLES.items()}
    
    def test_text_document(self):
        t = tempfile.NamedTemporaryFile(delete=False)
        new_text = 'new document is added'
        t.write(bytes(new_text, 'utf8'))
        t.close()
        v = View()
        td1 = v.new_textdocument(new_text)
        self.assertEqual(new_text, td1.text_value)
        td2 = v.new_textdocument('')
        # must return None when no location is set
        self.assertIsNone(td2.location)
        self.assertIsNone(td2.location_scheme())
        self.assertIsNone(td2.location_path())
        self.assertIsNone(td2.location_address())
        td2.location = t.name
        self.assertEqual(new_text, td2.text_value)
        
    def test_get_property(self):
        d = Document()
        d.at_type = DocumentTypes.TextDocument
        d.id = 'd1'
        d.location = 'file:///some/file.txt'
        d.add_property('prop1', 'value1')
        self.assertEqual(d.id, d.get_property('id'))
        self.assertEqual(d.location, d.get_property('location'))
        self.assertEqual('value1', d.get_property('prop1'))
        d.id = 'v1:d1'
        self.assertEqual('v1:d1', d.long_id)
        self.assertEqual('v1:d1', d._short_id)
        self.assertEqual('v1', d.parent)


    def test_nontext_document(self):
        ad = Document()
        ad.at_type = DocumentTypes.AudioDocument
        with self.assertRaises(ValueError):
            assert ad.text_language is None
        with self.assertRaises(ValueError):
            assert ad.text_value is None
        with self.assertRaises(ValueError):
            ad.text_value = 'non-text document must not have ``@text`` field'
        with self.assertRaises(ValueError):
            ad.text_value = 'tlh'

    def test_init(self):
        for i, datum in self.data.items():
            for j, document in enumerate(datum['documents']):
                try:
                    _ = Document(document)
                except Exception as ex:
                    self.fail(f"{type(ex)}: {str(ex)}: {i} {document['id']}")

    def test_document_properties(self):
        props_json = self.data['everything']['documents'][0]['properties']
        props_obj = DocumentProperties(props_json)
        self.assertEqual(props_json, json.loads(props_obj.serialize()))
    
    def test_document_added_properties(self):
        mmif = Mmif(self.data['everything']['string'])
        doc1 = Document()
        doc1.at_type = DocumentTypes.TextDocument
        doc1.id = 'doc1'
        doc1.location = 'aScheme:///data/doc1.txt'
        # `mime` is a special prop and shouldn't be added to "temporary" props
        doc1.add_property('mime', 'text')
        doc1_roundtrip = Document(doc1.serialize())
        self.assertTrue(doc1_roundtrip.get('mime'), 'text')
        # but a generic prop should be added to "temporary" props
        # ("temporary" props dict will be lost after `Document`-level serialization)
        doc1.add_property('author', 'me')
        doc1_roundtrip = Document(doc1.serialize())
        self.assertNotIn('author', doc1_roundtrip.properties)
        # then converted to an `Annotation` annotation during serialization at `Mmif`-level
        mmif.add_document(doc1)
        ## no Annotation before serialization
        self.assertEqual(0, len(list(mmif.views.get_last_contentful_view().get_annotations(AnnotationTypes.Annotation, author='me'))))
        ## after serialization, the `Annotation` annotation should be added to the last view
        ## note that we didn't add any views, so the last view before and after the serialization are the same
        mmif_roundtrip = Mmif(mmif.serialize())
        self.assertTrue(next(mmif_roundtrip.views.get_last_contentful_view().get_annotations(AnnotationTypes.Annotation, author='me')))
        # finally, when deserialized back to a Mmif instance, the `Annotation` props should be added
        # as a property of the document 
        doc1_mmif_roundtrip = mmif_roundtrip['doc1']
        self.assertEqual(0, len(doc1_mmif_roundtrip._props_pending))
        self.assertEqual('me', doc1_mmif_roundtrip.get_property('author'))
        
    def test_document_adding_duplicate_properties(self):
        mmif = Mmif(self.data['everything']['string'])
        doc1 = Document()
        mmif.add_document(doc1)
        did = 'doc1'
        # last view before serialization rounds
        r0_vid = mmif.views.get_last_contentful_view().id
        doc1.at_type = DocumentTypes.TextDocument
        doc1.id = did
        doc1.location = 'aScheme:///data/doc1.txt'
        doc1.add_property('author', 'me')
        doc1.add_property('publisher', 'they')
        
        # sanity checks
        self.assertEqual(2, len(doc1._props_pending))
        self.assertEqual('me', doc1.get_property('author'))
        
        # new value should overwrite the existing before being serialized
        doc1.add_property('author', 'you')
        self.assertEqual(2, len(doc1._props_pending))
        self.assertEqual('you', doc1.get_property('author'))
        
        # first round of serialization
        mmif_roundtrip1 = Mmif(mmif.serialize())  # as we didn't add any views, two `Annotation` annotations should be in the last view of the original MMIF
        doc1 = mmif_roundtrip1[did]
        # adding duplicate value should not be serialized into a new Annotation object
        ## new view to 
        v = mmif_roundtrip1.new_view()
        r1_vid = v.id
        v.metadata.app = tester_appname
        doc1.add_property('author', 'you')  # duplicate value
        doc1.add_property('publisher', 'they')  # duplicate value
        ## stored in temporary props even when the value is the same
        self.assertEqual(2, len(doc1._props_pending))
        mmif_roundtrip2 = Mmif(mmif_roundtrip1.serialize())
        ## but not serialized
        self.assertEqual(0, len(list(mmif_roundtrip2.views.get_last_contentful_view().get_annotations(AnnotationTypes.Annotation))))

        # adding non-duplicate value should be serialized into a new Annotation object
        # even when there is a duplicate key in a previous view
        doc1 = mmif_roundtrip2[did]
        v = mmif_roundtrip2.new_view()
        r2_vid = v.id
        v.metadata.app = tester_appname
        v.new_annotation(AnnotationTypes.Region, document=did)
        doc1.add_property('author', 'me')
        doc1.add_property('publisher', 'they')
        self.assertEqual(2, len(doc1._props_pending))
        mmif_roundtrip3 = Mmif(mmif_roundtrip2.serialize())
        r0_v_anns = list(mmif_roundtrip3.views[r0_vid].get_annotations(AnnotationTypes.Annotation))
        r1_v_anns = list(mmif_roundtrip3.views[r1_vid].get_annotations(AnnotationTypes.Annotation))
        r2_v_anns = list(mmif_roundtrip3.views[r2_vid].get_annotations(AnnotationTypes.Annotation))
        # two props (`author` and `publisher`) are serialized to one `Annotation` objects
        self.assertEqual(1, len(r0_v_anns))  
        self.assertEqual(0, len(r1_v_anns))
        self.assertEqual(1, len(r2_v_anns))
        
        # when the value is different, two same-key props co-exist in two Annotation objects
        self.assertEqual('you', r0_v_anns[0].get_property('author'))
        self.assertEqual('me', r2_v_anns[0].get_property('author'))

        # but the Annotation object should not be created when the value is the same
        self.assertTrue('publisher' in r0_v_anns[0])
        self.assertFalse('publisher' in r2_v_anns[0])

    def test_document_added_properties_with_manual_capital_annotation(self):
        mmif = Mmif(validate=False)
        v = mmif.new_view()
        did = 'doc1'
        v.metadata.app = tester_appname
        v.metadata.new_contain(AnnotationTypes.Annotation, document=did)
        doc1 = Document()
        mmif.add_document(doc1)
        doc1.at_type = DocumentTypes.TextDocument
        doc1.id = did
        doc1.location = 'aScheme:///data/doc1.txt'

        # test auto-generation disabled when an Annotation instance is added manually during current app's run
        v.new_annotation(AnnotationTypes.Annotation, author='me', publisher='they')
        doc1.add_property('author', 'me')
        mmif_roundtrip = Mmif(mmif.serialize())
        ## should be only one Annotation object, from manual call of `new_annotation`
        self.assertEqual(1, len(list(mmif_roundtrip.views.get_last_contentful_view().get_annotations(AnnotationTypes.Annotation))))

        # test with duplicate property added by a downstream app
        mmif_roundtrip = Mmif(mmif.serialize())
        doc1_prime = mmif_roundtrip[did]
        ## simulating a new view added by the downstream app
        v2 = mmif_roundtrip.new_view()
        v2.metadata.app = tester_appname
        v2.new_annotation(AnnotationTypes.Region, document=did)
        # author=me is already in the input MMIF
        doc1_prime.add_property('author', 'me')
        mmif_roundtrip2 = Mmif(mmif_roundtrip.serialize())
        self.assertEqual(1, len(list(mmif.views.get_last_contentful_view().get_annotations(AnnotationTypes.Annotation))))
        # none should be added
        self.assertEqual(0, len(list(mmif_roundtrip2.views.get_last_contentful_view().get_annotations(AnnotationTypes.Annotation))))

        # test with same key, different value
        mmif_roundtrip = Mmif(mmif.serialize())
        doc1_prime = mmif_roundtrip[did]
        ## simulating a new view added by the downstream app
        v2 = mmif_roundtrip.new_view()
        v2.metadata.app = tester_appname
        v2.metadata.new_contain(AnnotationTypes.Region, document=did)
        # author=me is in the input MMIF
        doc1_prime.add_property('author', 'you')
        mmif_roundtrip2 = Mmif(mmif_roundtrip.serialize())
        # the Annotation in the previous view should be preserved
        self.assertEqual(1, len(list(mmif.views.get_last_contentful_view().get_annotations(AnnotationTypes.Annotation))))
        # but a new one should be added
        self.assertEqual(1, len(list(mmif_roundtrip2.views.get_last_contentful_view().get_annotations(AnnotationTypes.Annotation))))

        self.assertEqual('me', list(mmif.views.get_last_contentful_view().get_annotations(AnnotationTypes.Annotation))[0].get_property(
            'author'))
        self.assertEqual('you', list(mmif_roundtrip2.views.get_last_contentful_view().get_annotations(AnnotationTypes.Annotation))[
            0].get_property('author'))
        
    def test_capital_annotation_generation_viewfinder(self):
        mmif = Mmif(validate=False)
        for i in range(1, 3):
            doc = Document()
            doc.at_type = DocumentTypes.TextDocument
            doc.id = f'doc{i}'
            doc.location = f'aScheme:///data/doc{i}.txt'
            mmif.add_document(doc)

            v = mmif.new_view()
            v.id = f'v{i}'
            v.metadata.app = tester_appname
            v.new_annotation(AnnotationTypes.Region, document=doc.id)
            mmif.add_view(v)
        authors = ['me', 'you']
        for i in range(2):
            mmif[f'doc{i+1}'].add_property('author', authors[i])
        mmif_roundtrip = Mmif(mmif.serialize())
        for i in range(1, 3):
            cap_anns = list(mmif_roundtrip.views[f'v{i}'].get_annotations(AnnotationTypes.Annotation))
            self.assertEqual(1, len(cap_anns))
            self.assertEqual(authors[i-1], cap_anns[0].get_property('author'))
            
    def test_capital_annotation_nongeneration_for_writable_documents(self):
        mmif = Mmif(validate=False)
        doc = Document()
        doc.at_type = DocumentTypes.TextDocument
        doc.id = f'doc0'
        doc.location = f'aScheme:///data/doc0.txt'
        mmif.add_document(doc)

        v = mmif.new_view()
        v.metadata.app = tester_appname
        vid = v.id
        new_td_id = mmif[vid].new_textdocument(text='new text', document=doc.id, origin='transformation').id
        doc.add_property('author', 'me')
        
        mmif_roundtrip = Mmif(mmif.serialize())
        
        self.assertTrue(AnnotationTypes.Annotation in mmif_roundtrip[vid].metadata.contains)
        self.assertTrue(mmif_roundtrip['doc0'].get_property('author'), 'me')
        self.assertTrue(next(mmif_roundtrip[vid].get_annotations(AnnotationTypes.Annotation)).get_property('author'), 'me')
        self.assertTrue(next(mmif_roundtrip[vid].get_annotations(AnnotationTypes.Annotation)).get_property('document'), doc.id)
        self.assertTrue(mmif_roundtrip[new_td_id].get_property('origin'), 'transformation')

    def test_deserialize_with_whole_mmif(self):
        for i, datum in self.data.items():
            for j, document in enumerate(datum['documents']):
                try:
                    document_obj = datum['mmif'][document['properties']['id']]
                except KeyError:
                    self.fail(f"Document {document['properties']['id']} not found in MMIF")
                self.assertIsInstance(document_obj, Document)
                self.assertIsInstance(document_obj.properties, DocumentProperties)

    def test_deserialize_with_medium_str(self):
        for i, datum in self.data.items():
            for j, document in enumerate(datum['documents']):
                document_obj = Document(document)
                self.assertIsInstance(document_obj, Document)
                self.assertIsInstance(document_obj.properties, DocumentProperties)

    def test_serialize_to_medium_str(self):
        for i, datum in self.data.items():
            for j, document in enumerate(datum['documents']):
                document_obj = Document(document)
                serialized = json.loads(document_obj.serialize())
                self.assertEqual(document, serialized, f'Failed on {i}, {document["properties"]["id"]}')

    def test_serialize_with_whole_mmif(self):
        for i, datum in self.data.items():
            for j, document in enumerate(datum['documents']):
                document_serialized = json.loads(datum['mmif'].serialize())['documents'][j]
                self.assertEqual(document, document_serialized, f'Failed on {i}, {document["properties"]["id"]}')

    @pytest.mark.skip("TODO: does not work with text examples that are a mixture of old (short-id) and new (long-id) annotations")
    def test_add_property(self):
        for i, datum in self.data.items():
            for j in range(len(datum['json']['documents'])):
                document_id = datum['json']['documents'][j]['properties']['id']
                properties = datum['json']['documents'][j].get('properties')
                if properties:
                    removed_prop_key, removed_prop_value = list(properties.items())[-1]
                    properties.pop(removed_prop_key)
                    try:
                        new_mmif = Mmif(datum['json'])
                        new_mmif.get_document_by_id(document_id).add_property(removed_prop_key, removed_prop_value)
                        self.assertEqual(json.loads(datum['string']), json.loads(new_mmif.serialize()), f'Failed on {i}, {document_id}')
                    except ValidationError:
                        continue


class TestDataStructure(unittest.TestCase):
    def setUp(self) -> None:
        self.mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        self.datalist = self.mmif_obj.views

    def test_setitem(self):
        self.datalist['v1'] = View({'id': 'v1'})
        self.datalist['v2'] = View({'id': 'v2'})

    def test_getitem(self):
        self.assertIs(self.mmif_obj['v1'], self.datalist['v1'])

    def test_getitem_raises(self):
        with self.assertRaises(KeyError):
            _ = self.datalist['reserved_names']

    def test_append(self):
        self.assertTrue('v256' not in self.datalist._items)
        self.datalist.append(View({'id': 'v256'}))
        self.assertTrue('v256' in self.datalist._items)

    def test_append_overwrite(self):
        try:
            self.datalist.append(View({'id': 'v1'}))
            self.fail('appended without overwrite')
        except KeyError as ke:
            self.assertEqual('Key v1 already exists', ke.args[0])

        try:
            self.datalist.append(View({'id': 'v1'}), overwrite=True)
        except AssertionError:
            raise
        except Exception as ex:
            self.fail(ex.args[0])

    def test_membership(self):
        self.assertIn('v1', self.datalist)

        self.assertNotIn('v200', self.datalist)
        self.datalist['v200'] = View({'id': 'v200'})
        self.assertIn('v200', self.datalist)

    def test_len(self):
        self.assertEqual(8, len(self.datalist))
        for i in range(9, 19):
            self.datalist[f'v{i}'] = View({'id': f'v{i}'})
            self.assertEqual(i, len(self.datalist))

    def test_iter(self):
        for i in range(9, 19):
            self.datalist[f'v{i}'] = View({'id': f'v{i}'})

        for expected_index, (actual_index, item) in zip(range(18), enumerate(self.datalist)):
            self.assertEqual(expected_index, actual_index, "here")
            self.assertEqual(expected_index+1, int(item['id'][1:]))

    def test_setitem_fail_on_reserved_name(self):
        for i, name in enumerate(self.datalist.reserved_names):
            try:
                self.datalist[name] = View({'id': f'v{i+1}'})
                self.fail("was able to setitem on reserved name")
            except KeyError as ke:
                self.assertEqual("can't set item on a reserved name", ke.args[0])

    def test_get(self):
        self.assertEqual(self.datalist['v1'], self.datalist.get('v1'))

    def test_update(self):
        other_contains = """{
          "Segment": { "unit": "seconds" },
          "TimePoint": { "unit": "seconds" }
        }"""
        other_datadict = ContainsDict(other_contains)

        other_contains = """{
                  "Segment": { "unit": "seconds" },
                  "TimePoint": { "unit": "milliseconds" , "foo": "bar" }
                }"""
        other_datadict = ContainsDict(other_contains)


@unittest.skipIf(*SKIP_SCHEMA)
class TestSchema(unittest.TestCase):

    schema = json.loads(mmifpkg.get_mmif_json_schema())

    def setUp(self) -> None:
        if DEBUG:
            self.hypos = []

    def tearDown(self) -> None:
        if DEBUG:
            with open('hypotheses.json', 'w') as dump:
                json.dump(self.hypos, dump, indent=2)

    @given(hypothesis_jsonschema.from_schema(schema))
    @settings(suppress_health_check=list(HealthCheck))
    def test_accepts_valid_schema(self, data):
        if DEBUG:
            self.hypos.append(data)
        try:
            _ = Mmif(json.dumps(data))
        except ValidationError as ve:
            self.fail("didn't accept valid data")


if __name__ == '__main__':
    unittest.main()
