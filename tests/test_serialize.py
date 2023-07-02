import json
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

import hypothesis_jsonschema
import pytest
from hypothesis import given, settings, HealthCheck
from jsonschema import ValidationError

import mmif as mmifpkg
from mmif.serialize import *
from mmif.serialize.model import *
from mmif.serialize.view import ContainsDict, ErrorDict
from mmif.vocabulary import AnnotationTypes, DocumentTypes
from tests.mmif_examples import *

# Flags for skipping tests
DEBUG = False
SKIP_SCHEMA = False, "Not skipping TestSchema by default"
not_existing_attype = 'http://not.existing/type'


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
        v.metadata.app = 'http://dummy.app'
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
        document.at_type = f"http://mmif.clams.ai/vocabulary/TextDocument/{DocumentTypes.typevers['TextDocument']}"
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
                         mmif_obj.get_document_by_id('v6:td1'))
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
        new_document = Document({'@type': f"http://mmif.clams.ai/vocabulary/TextDocument/{DocumentTypes.typevers['TextDocument']}",
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
        views = mmif_obj.get_views_contain(DocumentTypes.TextDocument)
        self.assertEqual(2, len(views))
        views = mmif_obj.get_all_views_contain('http://vocab.lappsgrid.org/SemanticTag')
        self.assertEqual(1, len(views))
        views = mmif_obj.get_views_contain([
            AnnotationTypes.TimeFrame,
            DocumentTypes.TextDocument,
            AnnotationTypes.Alignment,
        ])
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
        mmif_obj.add_view(a_view)
        with self.assertRaises(KeyError):
            _ = mmif_obj['m1']

    def test___contains__(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        self.assertTrue('views' in mmif_obj)
        self.assertTrue('v5' in mmif_obj)
        self.assertFalse('v432402' in mmif_obj)


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
            self.assertIs(v1_bb1, self.mmif_obj.views.get('v5').annotations.get('bb1'))
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
            self.assertIs(s1, self.mmif_obj.get_view_by_id('v1').annotations.get('s1'))
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
        vmeta.add_parameter('pretty', False)
        self.assertEqual(len(vmeta.parameters), 1)
        self.assertEqual(vmeta.get_parameter('pretty'), False)
        with pytest.raises(KeyError):
            vmeta.get_parameter('not_exist')

    def test_view_parameters_batch_adding(self):
        vmeta = ViewMetadata()
        vmeta.add_parameters(pretty=True, validate=False)
        self.assertEqual(len(vmeta.parameters), 2)
        vmeta = ViewMetadata()
        vmeta.add_parameters(**{'pretty': True, 'validate': False})
        
    def test_add_warning(self):
        vmeta = ViewMetadata()
        w1 = Warning('first_warning')
        w2 = UserWarning('second warning')
        vmeta.add_warnings(w1, w2)
        self.assertEqual(len(vmeta.warnings), 2)
        for warning in vmeta.warnings:
            self.assertTrue(isinstance(warning, str))
            self.assertTrue('warning' in warning.lower())

    def test_props_preserved(self):
        view_serial = self.view_obj.serialize()

        def id_func(a):
            return a['properties']['id']

        for original, new in zip(sorted(self.view_json['annotations'], key=id_func),
                                 sorted(json.loads(view_serial)['annotations'], key=id_func)):
            self.assertEqual(original, new)
            
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

    def test_get_by_id(self):
        mmif_obj = Mmif(MMIF_EXAMPLES['everything'])
        mmif_obj.get_document_by_id('m1')
        mmif_obj.get_document_by_id('v4:td1')
        with self.assertRaises(KeyError):
            mmif_obj.get_document_by_id('m55')
        with self.assertRaises(KeyError):
            mmif_obj.get_document_by_id('v1:td1')
        view_obj = mmif_obj['v4']
        td1 = view_obj.get_document_by_id('td1')
        self.assertEqual(td1.properties.mime, 'text/plain')
        a1 = view_obj.get_annotation_by_id('a1')
        self.assertEqual(a1.at_type, AnnotationTypes.Alignment)
        with self.assertRaises(KeyError):
            view_obj.get_annotation_by_id('completely-unlikely-annotation-id')
            
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


class TestAnnotation(unittest.TestCase):
    # TODO (angus-lherrou @ 7/27/2020): testing should include validation for required attrs
    #  once that is implemented (issue #23)
    def setUp(self) -> None:
        self.data = {i: {'string': example,
                         'json': json.loads(example),
                         'mmif': Mmif(example),
                         'annotations': [annotation
                                         for view in json.loads(example)['views']
                                         for annotation in view['annotations']]}
                     for i, example in MMIF_EXAMPLES.items()}

    def test_annotation_properties(self):
        ann_json = self.data['everything']['annotations'][0]
        props_json = ann_json['properties']
        ann_obj = Annotation(ann_json)
        props_obj = AnnotationProperties(props_json)
        self.assertEqual(props_json, json.loads(props_obj.serialize()))
        self.assertEqual(ann_obj.properties, props_obj)
        self.assertEqual(props_json['id'], props_obj.id)
        self.assertEqual(props_json['start'], props_obj.get('start'))
        self.assertEqual(props_json['start'], props_obj.get('start'))
        self.assertEqual(props_json['end'], props_obj.get('end'))
        ann_obj.add_property('new_prop', 'new_prop_value')
        self.assertEqual(ann_obj.properties['new_prop'], 'new_prop_value')
        for k in ann_obj.properties.keys():
            self.assertTrue(k is not None)
            self.assertTrue(ann_obj.properties[k] is not None)
        for k, v in ann_obj.properties.items():
            self.assertTrue(k is not None)
            self.assertTrue(v is not None)
    
    def test_property_types(self):
        ann = Annotation()
        ann.id = 'a1'
        for a_type, a_value in zip([str, int, float, bool, type(None)],
                                         ['str', '1', '1.1', False, None]):
            ann.add_property(a_type.__name__, a_value)
        with self.assertRaises(ValueError):
            ann.add_property("dict", {"k1": "v1"})

    def test_add_property(self):
        for i, datum in self.data.items():
            for j in range(len(datum['json']['views'])):
                view_id = datum['json']['views'][j]['id']
                anno_id = datum['json']['views'][j]['annotations'][0]['properties']['id']
                props = datum['json']['views'][j]['annotations'][0]['properties']
                removed_prop_key, removed_prop_value = list(props.items())[-1]
                props.pop(removed_prop_key)
                try:
                    new_mmif = Mmif(datum['json'])
                    new_mmif.get_view_by_id(view_id).annotations[anno_id].add_property(removed_prop_key, removed_prop_value)
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

    def test_id(self):
        anno_obj: Annotation = self.data['everything']['mmif']['v5:bb1']

        old_id = anno_obj.id
        self.assertEqual('bb1', old_id)

    def test_change_id(self):
        anno_obj: Annotation = self.data['everything']['mmif']['v5:bb1']

        anno_obj.id = 'bb200'
        self.assertEqual('bb200', anno_obj.id)

        serialized = json.loads(anno_obj.serialize())
        new_id = serialized['properties']['id']
        self.assertEqual('bb200', new_id)

        serialized_mmif = json.loads(self.data['everything']['mmif'].serialize())
        new_id_from_mmif = serialized_mmif['views'][4]['annotations'][0]['properties']['id']
        self.assertEqual('bb200', new_id_from_mmif)


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
        doc1.add_property('author', 'me')
        doc1_roundtrip = Document(doc1.serialize())
        self.assertNotIn('author', doc1_roundtrip.properties)
        # and converted to an `Annotation` annotation during serialization
        mmif.add_document(doc1)
        ## no Annotation before serialization
        with pytest.raises(StopIteration):
            self.assertTrue(next(mmif.views.get_last().get_annotations(AnnotationTypes.Annotation, author='me')))
        ## after serialization, the `Annotation` annotation should be added to the last view
        mmif_roundtrip = Mmif(mmif.serialize())
        self.assertTrue(next(mmif_roundtrip.views.get_last().get_annotations(AnnotationTypes.Annotation, author='me')))
    def test_deserialize_with_whole_mmif(self):
        for i, datum in self.data.items():
            for j, document in enumerate(datum['documents']):
                try:
                    document_obj = datum['mmif'].get_document_by_id(document['properties']['id'])
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
        # TODO (krim @ 6/21/23): remove this ignore filter once hypothesis-jsonschema is updated with jsonschema 4.18
        import warnings
        warnings.simplefilter("ignore")

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
