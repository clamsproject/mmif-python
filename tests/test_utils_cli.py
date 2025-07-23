import contextlib
import io
import os
import unittest.mock

import mmif
from mmif.utils.cli import rewind
from mmif.utils.cli import source

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
        
        # to suppress output (otherwise, set to stdout by default
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

if __name__ == '__main__':
    unittest.main()
