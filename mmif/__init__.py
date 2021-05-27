import contextlib

import pkg_resources

from mmif.ver import __version__
from mmif.ver import __specver__
from mmif.vocabulary import *
from mmif.serialize import *

_res_pkg = 'res'
_ver_pkg = 'ver'
_vocabulary_pkg = 'vocabulary'
_schema_res_name = 'mmif.json'


def get_mmif_json_schema():
    res = pkg_resources.resource_stream(f'{__name__}.{_res_pkg}', _schema_res_name)
    res_str = res.read().decode('utf-8')
    res.close()
    return res_str
