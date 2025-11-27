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

from mmif.serialize import Mmif
from mmif.vocabulary import DocumentTypes, AnnotationTypes


class TestCli(unittest.TestCase):
    def setUp(self) -> None:
        self.parser, _ = mmif.prep_argparser_and_subcmds()

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
        args.output = open(os.devnull, 'w')

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
        # mmif we add views to
        self.mmif_one = Mmif(
            {
                "metadata": {"mmif": "http://mmif.clams.ai/1.0.0"},
                "documents": [],
                "views": [],
            }
        )

        # baseline empty mmif for comparison
        self.empty_mmif = Mmif(
            {
                "metadata": {"mmif": "http://mmif.clams.ai/1.0.0"},
                "documents": [],
                "views": [],
            }
        )
    
    @staticmethod
    def add_dummy_view(mmif: Mmif, appname: str):
        v = mmif.new_view()
        v.metadata.app = appname
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
        # Regular Case
        app_one_views = 3 
        app_two_views = 2
        for i in range(app_one_views):
            self.add_dummy_view(self.mmif_one, 'dummy_app_one')
        for j in range(app_two_views):
            self.add_dummy_view(self.mmif_one, 'dummy_app_two')
        self.assertEqual(len(self.mmif_one.views), app_one_views + app_two_views)
        rewound = rewind.rewind_mmif(self.mmif_one, 1, choice_is_viewnum=False)
        self.assertEqual(len(rewound.views), app_one_views)


class TestDescribe(unittest.TestCase):
    """Test suite for the describe CLI module."""

    def setUp(self):
        """Create test MMIF structures."""
        self.parser = describe.prep_argparser()

        # Create a basic MMIF with some documents
        self.basic_mmif = Mmif(
            {
                "metadata": {"mmif": "http://mmif.clams.ai/1.0.0"},
                "documents": [
                    {
                        "@type": "http://mmif.clams.ai/vocabulary/VideoDocument/v1",
                        "properties": {
                            "id": "d1",
                            "mime": "video/mp4",
                            "location": "file:///test/video.mp4"
                        }
                    },
                    {
                        "@type": "http://mmif.clams.ai/vocabulary/TextDocument/v1",
                        "properties": {
                            "id": "d2",
                            "mime": "text/plain",
                            "location": "file:///test/text.txt"
                        }
                    }
                ],
                "views": [],
            }
        )

    def create_temp_mmif_file(self, mmif_obj):
        """Helper to create a temporary MMIF file."""
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.mmif', delete=False)
        tmp.write(mmif_obj.serialize(pretty=False))
        tmp.close()
        return tmp.name

    def test_split_appname_appversion(self):
        """Test splitting app name and version from URI."""
        # Normal case
        app_name, app_version = describe.split_appname_appversion(
            "http://apps.clams.ai/test-app/v1.0.0"
        )
        self.assertEqual(app_name, "test-app")
        self.assertEqual(app_version, "v1.0.0")

        # With app name ending with version
        app_name, app_version = describe.split_appname_appversion(
            "http://apps.clams.ai/test-app-v1.0.0/v1.0.0"
        )
        self.assertEqual(app_name, "test-app")
        self.assertEqual(app_version, "v1.0.0")

        # Unresolvable version
        app_name, app_version = describe.split_appname_appversion(
            "http://apps.clams.ai/test-app/unresolvable"
        )
        self.assertEqual(app_name, "test-app")
        self.assertIsNone(app_version)

        # Short URI
        app_name, app_version = describe.split_appname_appversion(
            "http://apps.clams.ai"
        )
        self.assertIsNone(app_name)
        self.assertIsNone(app_version)

    def test_generate_param_hash(self):
        """Test parameter hash generation."""
        # Empty params
        hash1 = describe.generate_param_hash({})
        self.assertEqual(len(hash1), 32)  # MD5 hash length

        # Same params should give same hash
        params = {"param1": "value1", "param2": 42}
        hash2 = describe.generate_param_hash(params)
        hash3 = describe.generate_param_hash(params)
        self.assertEqual(hash2, hash3)

        # Order shouldn't matter (sorted internally)
        params_reversed = {"param2": 42, "param1": "value1"}
        hash4 = describe.generate_param_hash(params_reversed)
        self.assertEqual(hash2, hash4)

        # Different params should give different hash
        params_diff = {"param1": "value1", "param2": 43}
        hash5 = describe.generate_param_hash(params_diff)
        self.assertNotEqual(hash2, hash5)

    def test_get_workflow_specs_empty(self):
        """Test get_workflow_specs with MMIF containing no views."""
        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            spec, error_views, warning_views, empty_views = describe.get_workflow_specs(tmp_file)
            self.assertEqual(len(spec), 0)
            self.assertEqual(len(error_views), 0)
            self.assertEqual(len(warning_views), 0)
            self.assertEqual(len(empty_views), 0)
        finally:
            os.unlink(tmp_file)

    def test_get_workflow_specs_with_views(self):
        """Test get_workflow_specs with MMIF containing views with annotations."""
        # Add a view with annotations
        view = self.basic_mmif.new_view()
        view.metadata.app = "http://apps.clams.ai/test-app/v1.0.0"
        view.metadata.appConfiguration = {"threshold": 0.5}
        view.metadata.parameters = {"threshold": "0.5"}
        view.new_annotation(AnnotationTypes.TimeFrame, start=0, end=1000)
        view.new_annotation(AnnotationTypes.TimeFrame, start=1000, end=2000)

        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            spec, error_views, warning_views, empty_views = describe.get_workflow_specs(tmp_file)
            self.assertEqual(len(spec), 1)
            self.assertEqual(len(error_views), 0)
            self.assertEqual(len(warning_views), 0)
            self.assertEqual(len(empty_views), 0)

            # Check the spec content
            view_id, app, configs, running_time, running_hardware, annotation_count, annotations_by_type = spec[0]
            self.assertEqual(app, "http://apps.clams.ai/test-app/v1.0.0")
            self.assertEqual(configs, {"threshold": 0.5})
            self.assertIsNone(running_time)
            self.assertIsNone(running_hardware)
            self.assertEqual(annotation_count, 2)
            self.assertIn(str(AnnotationTypes.TimeFrame), annotations_by_type)
            self.assertEqual(annotations_by_type[str(AnnotationTypes.TimeFrame)], 2)
        finally:
            os.unlink(tmp_file)

    def test_get_workflow_specs_with_profiling(self):
        """Test get_workflow_specs with appProfiling metadata."""
        view = self.basic_mmif.new_view()
        view.metadata.app = "http://apps.clams.ai/test-app/v1.0.0"
        view.metadata.appProfiling = {
            "runningTime": "0:00:05.123456",
            "hardware": {"cpu": "Intel", "gpu": "NVIDIA"}
        }
        view.new_annotation(AnnotationTypes.TimeFrame, start=0, end=1000)

        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            spec, _, _, _ = describe.get_workflow_specs(tmp_file)
            self.assertEqual(len(spec), 1)

            view_id, app, configs, running_time, running_hardware, annotation_count, annotations_by_type = spec[0]
            self.assertEqual(running_time, "0:00:05.123456")
            self.assertEqual(running_hardware, {"cpu": "Intel", "gpu": "NVIDIA"})
        finally:
            os.unlink(tmp_file)

    def test_get_workflow_specs_with_old_profiling(self):
        """Test get_workflow_specs with deprecated appRunningTime metadata."""
        view = self.basic_mmif.new_view()
        view.metadata.app = "http://apps.clams.ai/test-app/v1.0.0"
        # Use old metadata keys
        view.metadata["appRunningTime"] = "0:00:03.456789"
        view.metadata["appRunningHardware"] = {"cpu": "AMD"}
        view.new_annotation(AnnotationTypes.TimeFrame, start=0, end=1000)

        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            spec, _, _, _ = describe.get_workflow_specs(tmp_file)
            self.assertEqual(len(spec), 1)

            view_id, app, configs, running_time, running_hardware, annotation_count, annotations_by_type = spec[0]
            self.assertEqual(running_time, "0:00:03.456789")
            self.assertEqual(running_hardware, {"cpu": "AMD"})
        finally:
            os.unlink(tmp_file)

    def test_get_workflow_specs_empty_view(self):
        """Test get_workflow_specs with view containing no annotations."""
        view = self.basic_mmif.new_view()
        view.metadata.app = "http://apps.clams.ai/test-app/v1.0.0"

        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            spec, error_views, warning_views, empty_views = describe.get_workflow_specs(tmp_file)
            self.assertEqual(len(spec), 0)
            self.assertEqual(len(empty_views), 1)
            self.assertIn(view.id, empty_views)
        finally:
            os.unlink(tmp_file)

    def test_get_workflow_specs_error_view(self):
        """Test get_workflow_specs with view containing errors."""
        view = self.basic_mmif.new_view()
        view.metadata.app = "http://apps.clams.ai/test-app/v1.0.0"
        view.metadata.error = {"message": "Something went wrong"}

        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            spec, error_views, warning_views, empty_views = describe.get_workflow_specs(tmp_file)
            self.assertEqual(len(spec), 0)
            self.assertEqual(len(error_views), 1)
            self.assertIn(view.id, error_views)
        finally:
            os.unlink(tmp_file)

    def test_get_workflow_specs_warning_view(self):
        """Test get_workflow_specs with view containing warnings."""
        view = self.basic_mmif.new_view()
        view.metadata.app = "http://apps.clams.ai/test-app/v1.0.0"
        view.metadata.warnings = ["Warning 1", "Warning 2"]

        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            spec, error_views, warning_views, empty_views = describe.get_workflow_specs(tmp_file)
            self.assertEqual(len(spec), 0)
            self.assertEqual(len(warning_views), 1)
            self.assertIn(view.id, warning_views)
        finally:
            os.unlink(tmp_file)

    def test_generate_workflow_identifier_basic(self):
        """Test workflow identifier generation with basic workflow."""
        # Add views
        view1 = self.basic_mmif.new_view()
        view1.metadata.app = "http://apps.clams.ai/app1/v1.0.0"
        view1.metadata.parameters = {"param1": "value1"}
        view1.new_annotation(AnnotationTypes.TimeFrame, start=0, end=1000)

        view2 = self.basic_mmif.new_view()
        view2.metadata.app = "http://apps.clams.ai/app2/v2.0.0"
        view2.metadata.parameters = {}
        view2.new_annotation(AnnotationTypes.BoundingBox, coordinates=[[0, 0], [10, 10]])

        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            workflow_id = describe.generate_workflow_identifier(tmp_file)

            # Check structure: should contain source info and two app segments
            segments = workflow_id.split('/')
            # First segment is sources (TextDocument-1-VideoDocument-1)
            self.assertIn('TextDocument-1', segments[0])
            self.assertIn('VideoDocument-1', segments[0])

            # Check app segments exist
            self.assertIn('app1', workflow_id)
            self.assertIn('app2', workflow_id)
            self.assertIn('v1.0.0', workflow_id)
            self.assertIn('v2.0.0', workflow_id)
        finally:
            os.unlink(tmp_file)

    def test_generate_workflow_identifier_excludes_errors(self):
        """Test that workflow identifier excludes views with errors."""
        view1 = self.basic_mmif.new_view()
        view1.metadata.app = "http://apps.clams.ai/app1/v1.0.0"
        view1.metadata.parameters = {}
        view1.new_annotation(AnnotationTypes.TimeFrame, start=0, end=1000)

        view2 = self.basic_mmif.new_view()
        view2.metadata.app = "http://apps.clams.ai/app2/v2.0.0"
        view2.metadata.error = {"message": "Error occurred"}

        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            workflow_id = describe.generate_workflow_identifier(tmp_file)

            # Should contain app1 but not app2
            self.assertIn('app1', workflow_id)
            self.assertNotIn('app2', workflow_id)
        finally:
            os.unlink(tmp_file)

    def test_generate_workflow_identifier_excludes_warnings(self):
        """Test that workflow identifier excludes views with warnings."""
        view1 = self.basic_mmif.new_view()
        view1.metadata.app = "http://apps.clams.ai/app1/v1.0.0"
        view1.metadata.parameters = {}
        view1.new_annotation(AnnotationTypes.TimeFrame, start=0, end=1000)

        view2 = self.basic_mmif.new_view()
        view2.metadata.app = "http://apps.clams.ai/app2/v2.0.0"
        view2.metadata.warnings = ["Warning message"]

        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            workflow_id = describe.generate_workflow_identifier(tmp_file)

            # Should contain app1 but not app2
            self.assertIn('app1', workflow_id)
            self.assertNotIn('app2', workflow_id)
        finally:
            os.unlink(tmp_file)

    def test_generate_workflow_identifier_includes_empty_views(self):
        """Test that workflow identifier includes empty views (no annotations)."""
        view1 = self.basic_mmif.new_view()
        view1.metadata.app = "http://apps.clams.ai/app1/v1.0.0"
        view1.metadata.parameters = {}
        view1.new_annotation(AnnotationTypes.TimeFrame, start=0, end=1000)

        view2 = self.basic_mmif.new_view()
        view2.metadata.app = "http://apps.clams.ai/app2/v2.0.0"
        view2.metadata.parameters = {}
        # No annotations added

        tmp_file = self.create_temp_mmif_file(self.basic_mmif)
        try:
            workflow_id = describe.generate_workflow_identifier(tmp_file)

            # Should contain both apps (empty views are included)
            self.assertIn('app1', workflow_id)
            self.assertIn('app2', workflow_id)
        finally:
            os.unlink(tmp_file)


if __name__ == '__main__':
    unittest.main()
