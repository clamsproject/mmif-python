import importlib.resources
import sys

# DO NOT CHANGE THIS ORDER, important to prevent circular imports
from mmif.ver import __version__
from mmif.ver import __specver__
from mmif.vocabulary import *
from mmif.serialize import *


from clams import develop
from clams.mmif_utils import source
from clams.mmif_utils import rewind
from clams.app import *
from clams.app import __all__ as app_all
from clams.appmetadata import AppMetadata
from clams.restify import Restifier
from clams.ver import __version__

__all__ = [AppMetadata, Restifier] + app_all
version_template = "{} (based on MMIF spec: {})"

_res_pkg = 'res'
_ver_pkg = 'ver'
_vocabulary_pkg = 'vocabulary'
_schema_res_name = 'mmif.json'


def get_mmif_json_schema():
    # TODO (krim @ 7/14/23): use `as_file` after dropping support for Python 3.8
    return importlib.resources.read_text(f'{__package__}.{_res_pkg}', _schema_res_name)


def prep_argparser():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=version_template.format(__version__, __specver__)
    )
    subparsers = parser.add_subparsers(title='sub-command', dest='subcmd')
    for subcmd_module in [source, rewind, develop]:
        subcmd_name = subcmd_module.__name__.rsplit('.')[-1]
        subcmd_parser = subcmd_module.prep_argparser(add_help=False)
        subparsers.add_parser(subcmd_name, parents=[subcmd_parser], 
                              help=subcmd_module.describe_argparser()[0],
                              description=subcmd_module.describe_argparser()[1],
                              formatter_class=argparse.RawDescriptionHelpFormatter,
                              )
    return parser


def cli():
    parser = prep_argparser()
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()
    if args.subcmd == 'source':
        source.main(args)
    if args.subcmd == 'rewind':
        rewind.main(args)
    if args.subcmd == 'develop':
        develop.main(args)
