from importlib.resources import files

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
    return files(f'{__package__}.{_res_pkg}').joinpath(_schema_res_name).read_text()
