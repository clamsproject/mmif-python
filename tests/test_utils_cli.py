import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest.mock

import mmif
from mmif.serialize import Mmif
from mmif.utils.cli import describe, rewind, source, summarize
from mmif.vocabulary import AnnotationTypes

BASIC_MMIF_STRING = '{"metadata": {"mmif": "http://mmif.clams.ai/1.0.0"}, "documents": [{"@type": "http://mmif.clams.ai/vocabulary/VideoDocument/v1", "properties": {"id": "d1", "mime": "video/mp4", "location": "file:///test/video.mp4"}}], "views": []}'


class BaseCliTestCase(unittest.TestCase):
    """Base class for CLI module tests with common utilities."""
    
    cli_module = None  # Override in subclass
    
    def setUp(self):
        """Set up common test fixtures."""
        if self.cli_module:
            self.parser = self.cli_module.prep_argparser()
        self.basic_mmif = Mmif(BASIC_MMIF_STRING)
        self.maxDiff = None
    
    @staticmethod
    def create_temp_mmif_file(mmif_obj):
        """Create a temporary MMIF file for testing.
        
        Args:
            mmif_obj: Either a Mmif object or a dict/string to serialize
            
        Returns:
            str: Path to the temporary file (caller must unlink)
        """
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.mmif', delete=False)
        if isinstance(mmif_obj, Mmif):
            content = mmif_obj.serialize(pretty=False)
        else:
            content = json.dumps(mmif_obj) if isinstance(mmif_obj, dict) else mmif_obj
        tmp.write(content)
        tmp.close()
        return tmp.name
    
    def run_cli_capture_stdout(self, args_namespace):
        """Run CLI module and capture stdout as parsed JSON.
        
        Args:
            args_namespace: Namespace object with CLI arguments
            
        Returns:
            dict: Parsed JSON output from stdout
        """
        with unittest.mock.patch('sys.stdout', new=io.StringIO()) as stdout:
            self.cli_module.main(args_namespace)
            return json.loads(stdout.getvalue())


class IOTestMixin:
    """Mixin providing common I/O tests for CLI modules.
    
    Requires the test class to have:
    - cli_module attribute
    - basic_mmif attribute
    - create_temp_mmif_file method
    - run_cli_capture_stdout method
    - expected_output_keys attribute (list of keys to check in output)
    """
    
    def test_file_input_stdout_output(self):
        """Test reading from file and outputting to stdout."""
        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            args = argparse.Namespace(
                MMIF_FILE=tmp_file,
                output=None,
                pretty=False,
                help_schemas=None  # For describe module
            )
            output = self.run_cli_capture_stdout(args)
            self.assertIsInstance(output, dict)
            for key in self.expected_output_keys:
                self.assertIn(key, output)
        finally:
            os.unlink(tmp_file)
    
    def test_file_input_file_output(self):
        """Test reading from file and outputting to file."""
        tmp_input = self.create_temp_mmif_file(self.basic_mmif)
        tmp_output = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        tmp_output.close()
        try:
            args = self.parser.parse_args([tmp_input, '-o', tmp_output.name])
            self.cli_module.main(args)
            with open(tmp_output.name, 'r') as f:
                output = json.load(f)
            self.assertIsInstance(output, dict)
            for key in self.expected_output_keys:
                self.assertIn(key, output)
        finally:
            os.unlink(tmp_input)
            os.unlink(tmp_output.name)
    
    def test_stdin_input_stdout_output(self):
        """Test reading from stdin and outputting to stdout."""
        mmif_str = self.basic_mmif.serialize()
        with unittest.mock.patch('sys.stdin', io.StringIO(mmif_str)), \
             unittest.mock.patch('sys.stdout', new=io.StringIO()) as stdout:
            args = argparse.Namespace(
                MMIF_FILE=None,
                output=None,
                pretty=False,
                help_schemas=None  # For describe module
            )
            self.cli_module.main(args)
            output = json.loads(stdout.getvalue())
            self.assertIsInstance(output, dict)
            for key in self.expected_output_keys:
                self.assertIn(key, output)


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
        args.output = os.devnull
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


class TestDescribe(BaseCliTestCase, IOTestMixin):
    """Test suite for the describe CLI module."""
    
    cli_module = describe
    expected_output_keys = ['workflowId', 'stats', 'apps']

    def test_help_schemas_all(self):
        """Test --help-schemas all"""
        from mmif.utils.cli.describe import models_to_help
        with unittest.mock.patch('sys.stdout', new=io.StringIO()) as stdout:
            args = argparse.Namespace(help_schemas=['all'], MMIF_FILE=None, output=None, pretty=False)
            with self.assertRaises(SystemExit) as cm:
                describe.main(args)
            self.assertEqual(cm.exception.code, 0)
            output = stdout.getvalue()
            for m in models_to_help:
                self.assertIn(m.__name__, output)
            self.assertIn("$defs", output)

    def test_describe_main_directory(self):
        """Test describe.main with a directory input"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create two mmif files
            with open(os.path.join(tmp_dir, '1.mmif'), 'w') as f:
                f.write(self.basic_mmif.serialize())
            with open(os.path.join(tmp_dir, '2.mmif'), 'w') as f:
                f.write(self.basic_mmif.serialize())
            
            with unittest.mock.patch('sys.stdout', new=io.StringIO()) as stdout:
                # MMIF_FILE argument expects a string path
                args = argparse.Namespace(MMIF_FILE=tmp_dir, output=None, pretty=False, help_schemas=None)
                describe.main(args)
                output_json = json.loads(stdout.getvalue())
                # Just verify valid JSON output was produced
                self.assertIsInstance(output_json, dict)
                self.assertTrue(len(output_json) > 0)

    def test_deprecated_functions(self):
        """Test backward compatibility wrapper functions"""
        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            with self.assertWarns(DeprecationWarning):
                describe.get_pipeline_specs(tmp_file)
            with self.assertWarns(DeprecationWarning):
                describe.generate_pipeline_identifier(tmp_file)
        finally:
            os.unlink(tmp_file)


class TestSummarize(BaseCliTestCase, IOTestMixin):
    """Test suite for the summarize CLI module."""
    
    cli_module = summarize
    expected_output_keys = ['mmif_version', 'documents', 'views']

    def test_summarize_validates_content(self):
        """Test that summarize produces expected content."""
        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            output = self.run_cli_capture_stdout(
                argparse.Namespace(MMIF_FILE=tmp_file, output=None, pretty=False)
            )
            self.assertEqual(output['mmif_version'], "http://mmif.clams.ai/1.0.0")
        finally:
            os.unlink(tmp_file)


if __name__ == '__main__':
    unittest.main()
