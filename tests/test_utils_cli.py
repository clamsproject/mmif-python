import contextlib
import io
import json
import os
import tempfile
import unittest.mock

import mmif
from mmif.utils.cli import rewind
from mmif.utils.cli import source
from mmif.utils.cli import describe
from mmif.utils.cli import summarize

from mmif.serialize import Mmif
from mmif.vocabulary import DocumentTypes, AnnotationTypes


BASIC_MMIF_STRING = '{"metadata": {"mmif": "http://mmif.clams.ai/1.0.0"}, "documents": [{"@type": "http://mmif.clams.ai/vocabulary/VideoDocument/v1", "properties": {"id": "d1", "mime": "video/mp4", "location": "file:///test/video.mp4"}}], "views": []}'


class TestCli(unittest.TestCase):
    def setUp(self) -> None:
        self.parser, _, _ = mmif.prep_argparser_and_subcmds()

    def test_primary_cli(self):
        stdout = io.StringIO()
        with self.assertRaises(SystemExit) as e, contextlib.redirect_stdout(stdout):
            self.parser.parse_args("-v".split())
        self.assertEqual(e.exception.code, 0)
        self.assertEqual(stdout.getvalue().strip(),
                         mmif.version_template.format(mmif.__version__, mmif.__specver__))


class TestSource(unittest.TestCase):

    def setUp(self) -> None:
        self.parser = mmif.source.prep_argparser()
        self.prefix = None
        self.scheme = None
        self.mmif_jsonschema = mmif.get_mmif_json_schema()  # for when testing for mock windows (importlib.resources will try to read from unix file system and fails)
        self.docs = []

    def get_params(self):
        
        params = []
        if self.prefix:
            params.extend(f'--prefix {self.prefix}'.split())
        if self.scheme:
            params.extend(f'--scheme {self.scheme}'.split())
        params.extend(self.docs)
        return params

    def generate_source_mmif(self):

        # to suppress output (otherwise, set to stdout by default)
        args = self.parser.parse_args(self.get_params())
        with open(os.devnull, 'w') as devnull:
            args.output = devnull
            return source.main(args)

    def test_accept_file_paths(self):
        self.docs.append("video:/a/b/c.mp4")
        self.docs.append('text:/a/b/c.txt')
        source_mmif = Mmif(self.generate_source_mmif())
        self.assertEqual(len(source_mmif.documents), 2)
        self.assertTrue(all(map(lambda x: x.location_scheme() == 'file', source_mmif.documents)))

        # relative path
        self.docs.append('audio:a/b/c.mp3')
        with self.assertRaises(ValueError):
            self.generate_source_mmif()

    @unittest.mock.patch('os.name', 'nt')
    def test_on_windows(self):
        mmif.get_mmif_json_schema = lambda: self.mmif_jsonschema  # mock the schema to avoid importlib.resources issues on windows
        self.test_accept_file_paths()

    def test_accept_prefixed_file_paths(self):
        self.prefix = '/a/b'
        self.docs.append("video:c.mp4")
        self.docs.append("text:c.txt")
        source_mmif = Mmif(self.generate_source_mmif())
        self.assertEqual(len(source_mmif.documents), 2)
        
        # absolute path + prefix flag
        self.docs.append("audio:/c.mp3")
        with self.assertRaises(ValueError):
            self.generate_source_mmif()

    def test_reject_relative_prefix(self):
        self.prefix = '/'
        self.docs.append("video:c.mp4")
        source_mmif = Mmif(self.generate_source_mmif())
        self.assertEqual(len(source_mmif.documents), 1)
        
        self.prefix = '.'
        with self.assertRaises(ValueError):
            self.generate_source_mmif()

    def test_reject_unknown_mime(self):
        self.docs.append("unknown_mime/more_unknown:/c.mp4")
        with self.assertRaises(ValueError):
            self.generate_source_mmif()

    def test_accept_scheme_files(self):
        self.scheme = 'baapb'
        self.docs.append("video:cpb-aacip-123-4567890.video")
        self.docs.append("audio:cpb-aacip-111-1111111.audio")
        source_mmif = Mmif(self.generate_source_mmif())
        self.assertEqual(len(source_mmif.documents), 2)
        self.assertTrue(all(map(lambda x: x.location_scheme() == self.scheme, source_mmif.documents)))

    def test_generate_mixed_scheme(self):
        self.scheme = 'baapb'
        self.docs.append("video:file:///data/cpb-aacip-123-4567890.mp4")
        self.docs.append("audio:cpb-aacip-111-1111111.audio")
        source_mmif = Mmif(self.generate_source_mmif())
        self.assertEqual(len(source_mmif.documents), 2)
        schemes = set(doc.location_scheme() for doc in source_mmif.documents)
        self.assertEqual(len(schemes), 2)
        self.assertTrue('baapb' in schemes)
        self.assertTrue('file' in schemes)


class TestRewind(unittest.TestCase):
    def setUp(self):
        empty_mmif_str = ('{"metadata": {"mmif": '
                          '"http://mmif.clams.ai/1.0.0"}, "documents": [], '
                          '"views": []}')
        # mmif we add views to
        self.mmif_one = Mmif(empty_mmif_str)

        # baseline empty mmif for comparison
        self.empty_mmif = Mmif(empty_mmif_str)

    @staticmethod
    def add_dummy_view(mmif: Mmif, appname: str, timestamp: str = None):
        v = mmif.new_view()
        v.metadata.app = appname
        if timestamp:
            v.metadata.timestamp = timestamp
        v.new_annotation(AnnotationTypes.Annotation)

    def test_view_rewind(self):
        """
        Tests the use of "view-rewiding" to remove multiple views from a single app.
        """
        # Regular Case
        for i in range(10):
            self.add_dummy_view(self.mmif_one, 'dummy_app_one')
        self.assertEqual(len(self.mmif_one.views), 10)
        rewound = rewind.rewind_mmif(self.mmif_one, 5)
        self.assertEqual(len(rewound.views), 5)
        # rewinding is done "in-place"
        self.assertEqual(len(rewound.views), len(self.mmif_one.views))

    def test_app_rewind(self):
        # Create 3 app executions
        # App 1 (T1): 2 views
        self.add_dummy_view(self.mmif_one, 'dummy_app_one', '2024-01-01T12:00:00Z')
        self.add_dummy_view(self.mmif_one, 'dummy_app_one', '2024-01-01T12:00:00Z')
        # App 2 (T2): 1 view
        self.add_dummy_view(self.mmif_one, 'dummy_app_two', '2024-01-01T12:01:00Z')
        # App 3 (T3): 2 views
        self.add_dummy_view(self.mmif_one, 'dummy_app_three', '2024-01-01T12:02:00Z')
        self.add_dummy_view(self.mmif_one, 'dummy_app_three', '2024-01-01T12:02:00Z')
        
        self.assertEqual(len(self.mmif_one.views), 5)

        # Rewind 1 app execution (the 'dummy_app_three' execution)
        rewound = rewind.rewind_mmif(self.mmif_one, 1, choice_is_viewnum=False)
        
        # 5 - 2 = 3 views should remain
        self.assertEqual(len(rewound.views), 3)
        
        # Check that the correct views were removed
        remaining_apps = {v.metadata.app for v in rewound.views}
        self.assertNotIn('dummy_app_three', remaining_apps)
        self.assertIn('dummy_app_one', remaining_apps)
        self.assertIn('dummy_app_two', remaining_apps)


class TestDescribe(unittest.TestCase):
    """Test suite for the describe CLI module."""

    def setUp(self):
        """Create test MMIF structures."""
        self.parser = describe.prep_argparser()
        self.maxDiff = None
        self.basic_mmif = Mmif(BASIC_MMIF_STRING)

    def create_temp_mmif_file(self, mmif_obj):
        """Helper to create a temporary MMIF file."""
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.mmif', delete=False)
        if isinstance(mmif_obj, Mmif):
            content_to_write = mmif_obj.serialize(pretty=False)
        else:
            content_to_write = json.dumps(mmif_obj)
        tmp.write(content_to_write)
        tmp.close()
        return tmp.name

    def test_describe_single_mmif_empty(self):
        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            result = mmif.utils.workflow_helper.describe_single_mmif(tmp_file)
            self.assertEqual(result["stats"]["appCount"], 0)
            self.assertEqual(len(result["apps"]), 0)
            self.assertEqual(result["stats"]["annotationCountByType"], {})
        finally:
            os.unlink(tmp_file)

    def test_describe_single_mmif_one_app(self):
        view = self.basic_mmif.new_view()
        view.metadata.app = "http://apps.clams.ai/test-app/v1.0.0"
        view.metadata.timestamp = "2024-01-01T12:00:00Z"
        view.metadata.appProfiling = {"runningTime": "0:00:01.234"}
        view.new_annotation(AnnotationTypes.TimeFrame)
        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            result = mmif.utils.workflow_helper.describe_single_mmif(tmp_file)
            self.assertEqual(result["stats"]["appCount"], 1)
            self.assertEqual(len(result["apps"]), 1)
            app_exec = result["apps"][0]
            self.assertEqual(app_exec["app"], view.metadata.app)
            self.assertEqual(app_exec["viewIds"], [view.id])
            self.assertEqual(app_exec["appProfiling"]["runningTimeMS"], 1234)
        finally:
            os.unlink(tmp_file)

    def test_describe_single_mmif_one_app_two_views(self):
        view1 = self.basic_mmif.new_view()
        view1.metadata.app = "http://apps.clams.ai/test-app/v1.0.0"
        view1.metadata.timestamp = "2024-01-01T12:00:00Z"
        view1.new_annotation(AnnotationTypes.TimeFrame)
        view2 = self.basic_mmif.new_view()
        view2.metadata.app = "http://apps.clams.ai/test-app/v1.0.0"
        view2.metadata.timestamp = "2024-01-01T12:00:00Z"
        view2.new_annotation(AnnotationTypes.TimeFrame)
        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            result = mmif.utils.workflow_helper.describe_single_mmif(tmp_file)
            self.assertEqual(result["stats"]["appCount"], 1)
            self.assertEqual(len(result["apps"]), 1)
            app_exec = result["apps"][0]
            self.assertEqual(app_exec["viewIds"], [view1.id, view2.id])
        finally:
            os.unlink(tmp_file)

    def test_describe_single_mmif_error_view(self):
        view = self.basic_mmif.new_view()
        view.metadata.app = "http://apps.clams.ai/test-app/v1.0.0"
        view.metadata.timestamp = "2024-01-01T12:00:00Z"
        view.metadata.error = {"message": "Something went wrong"}
        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            result = mmif.utils.workflow_helper.describe_single_mmif(tmp_file)
            self.assertEqual(result["stats"]["appCount"], 0)
            self.assertEqual(len(result["apps"]), 0)
            self.assertEqual(len(result["stats"]["errorViews"]), 1)
        finally:
            os.unlink(tmp_file)

    @unittest.mock.patch('jsonschema.validators.validate')
    def test_describe_single_mmif_with_unassigned_views(self, mock_validate):
        raw_mmif = json.loads(self.basic_mmif.serialize())
        raw_mmif['views'].append({'id': 'v1', 'metadata': {'app': 'http://apps.clams.ai/app1/v1.0.0', 'timestamp': '2024-01-01T12:00:00Z'}, 'annotations': []})
        raw_mmif['views'].append({'id': 'v2', 'metadata': {'app': 'http://apps.clams.ai/app2/v2.0.0'}, 'annotations': []})
        raw_mmif['views'].append({'id': 'v3', 'metadata': {'timestamp': '2024-01-01T12:01:00Z', 'app': ''}, 'annotations': []})
        tmp_file = self.create_temp_mmif_file(raw_mmif)
        try:
            result = mmif.utils.workflow_helper.describe_single_mmif(tmp_file)
            self.assertEqual(result['stats']['appCount'], 1)
            self.assertEqual(len(result['apps']), 2)
            special_entry = result['apps'][-1]
            self.assertEqual(special_entry['app'], 'http://apps.clams.ai/non-existing-app/v1')
            self.assertEqual(len(special_entry['viewIds']), 2)
            self.assertIn('v2', special_entry['viewIds'])
            self.assertIn('v3', special_entry['viewIds'])
        finally:
            os.unlink(tmp_file)

    def test_describe_collection_empty(self):
        dummy_dir = 'dummy_mmif_collection'
        os.makedirs(dummy_dir, exist_ok=True)
        try:
            output = mmif.utils.workflow_helper.describe_mmif_collection(dummy_dir)
            expected = {
                'mmifCountByStatus': {'total': 0, 'successful': 0, 'withErrors': 0, 'withWarnings': 0, 'invalid': 0},
                'workflows': [],
                'annotationCountByType': {}
            }
            self.assertEqual(output, expected)
        finally:
            os.rmdir(dummy_dir)


class TestSummarize(unittest.TestCase):
    """Test suite for the summarize CLI module."""

    def setUp(self):
        """Create test MMIF structures."""
        self.parser = summarize.prep_argparser()
        self.basic_mmif = Mmif(BASIC_MMIF_STRING)

    def create_temp_mmif_file(self, mmif_obj):
        """Helper to create a temporary MMIF file."""
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.mmif', delete=False)
        tmp.write(mmif_obj.serialize(pretty=False))
        tmp.close()
        return tmp.name

    def test_summarize_positional_input(self):
        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        stdout = io.StringIO()
        try:
            args = self.parser.parse_args([tmp_file])
            args.output = stdout
            summarize.main(args)
            output = json.loads(stdout.getvalue())
            self.assertIn('mmif_version', output)
            self.assertEqual(output['mmif_version'], "http://mmif.clams.ai/1.0.0")
        finally:
            os.unlink(tmp_file)

    def test_summarize_output_file(self):
        tmp_input = self.create_temp_mmif_file(self.basic_mmif)
        tmp_output = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        tmp_output.close()
        try:
            args = self.parser.parse_args([tmp_input, "-o", tmp_output.name])
            summarize.main(args)
            # args.output is a path string now; no file handle to close.
            with open(tmp_output.name, 'r') as f:
                output = json.load(f)
            self.assertIn('mmif_version', output)
        finally:
            os.unlink(tmp_input)
            os.unlink(tmp_output.name)

    def test_summarize_pretty_print(self):
        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        stdout_pretty = io.StringIO()
        stdout_compact = io.StringIO()
        try:
            # Pretty
            args_pretty = self.parser.parse_args([tmp_file, "--pretty"])
            args_pretty.output = stdout_pretty
            summarize.main(args_pretty)

            # Compact
            args_compact = self.parser.parse_args([tmp_file])
            args_compact.output = stdout_compact
            summarize.main(args_compact)

            self.assertNotEqual(stdout_pretty.getvalue(), stdout_compact.getvalue())
            self.assertIn('\n  ', stdout_pretty.getvalue()) # Check for indentation
        finally:
            os.unlink(tmp_file)

    def test_summarize_stdin(self):
        mmif_str = self.basic_mmif.serialize()
        import argparse
        stdout = io.StringIO()
        stdin = io.StringIO(mmif_str)

        args = argparse.Namespace(MMIF_FILE=stdin, output=stdout, pretty=False)
        summarize.main(args)

        output = json.loads(stdout.getvalue())
        self.assertEqual(output['mmif_version'], "http://mmif.clams.ai/1.0.0")


if __name__ == '__main__':
    unittest.main()
