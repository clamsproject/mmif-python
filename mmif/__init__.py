from importlib.resources import files

import argparse
import importlib
import pkgutil
import sys

# DO NOT CHANGE THIS ORDER, important to prevent circular imports
from mmif.ver import __version__
from mmif.ver import __specver__
from mmif.vocabulary import *
from mmif.serialize import *
from mmif.utils.cli import rewind
from mmif.utils.cli import source

_res_pkg = 'res'
_ver_pkg = 'ver'
_vocabulary_pkg = 'vocabulary'
_schema_res_name = 'mmif.json'
version_template = "{} (based on MMIF spec: {})"


def get_mmif_json_schema():
    return files(f'{__package__}.{_res_pkg}').joinpath(_schema_res_name).read_text()


def find_all_modules(pkgname):
    parent = importlib.import_module(pkgname)
    if not hasattr(parent, '__path__'):
        raise ImportError(f"Error: '{pkgname}' is not a package.")
    for importer, module, ispkg in pkgutil.walk_packages(parent.__path__, parent.__name__ + '.'):
        if not ispkg:  # Only process modules, not subpackages themselves
            yield importlib.import_module(module)


def prep_argparser_and_subcmds():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=version_template.format(__version__, __specver__)
    )
    subparsers = parser.add_subparsers(title='sub-command', dest='subcmd')
    return parser, subparsers


def cli():
    parser, subparsers = prep_argparser_and_subcmds()
    cli_modules = {}
    for cli_module in find_all_modules('mmif.utils.cli'):
        cli_module_name = cli_module.__name__.rsplit('.')[-1]
        cli_modules[cli_module_name] = cli_module
        subcmd_parser = cli_module.prep_argparser(add_help=False)
        subparsers.add_parser(cli_module_name, parents=[subcmd_parser],
                              help=cli_module.describe_argparser()[0],
                              description=cli_module.describe_argparser()[1],
                              formatter_class=argparse.RawDescriptionHelpFormatter,
                              )
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()
    if args.subcmd not in cli_modules:
        parser.print_help(sys.stderr)
    else:
        cli_modules[args.subcmd].main(args)
