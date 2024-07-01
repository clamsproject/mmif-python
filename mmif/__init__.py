import importlib.resources

# DO NOT CHANGE THIS ORDER, important to prevent circular imports
from mmif.ver import __version__
from mmif.ver import __specver__
from mmif.vocabulary import *
from mmif.serialize import *

_res_pkg = 'res'
_ver_pkg = 'ver'
_vocabulary_pkg = 'vocabulary'
_schema_res_name = 'mmif.json'


def get_mmif_json_schema():
    # TODO (krim @ 7/14/23): use `as_file` after dropping support for Python 3.8
    return importlib.resources.read_text(f'{__package__}.{_res_pkg}', _schema_res_name)
