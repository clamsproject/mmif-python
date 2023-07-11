import importlib
import pkgutil
import re
from collections import defaultdict
from typing import Dict, Type, Callable, Set

import pkg_resources

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
    res = pkg_resources.resource_stream(f'{__name__}.{_res_pkg}', _schema_res_name)
    res_str = res.read().decode('utf-8')
    res.close()
    return res_str


patches: Dict[Type, Set[Callable]] = defaultdict(set)
for _, name, ispkg in pkgutil.iter_modules():
    if ispkg and re.match(r'mmif[-_]utils[-_]', name):
        mod = importlib.import_module(name)
        for c, ms in mod.patches.items():
            for m in ms:
                if m in patches[c]:
                    raise ValueError(f'Patch for {c}::{m.__name__} already exists.')
                patches[c].add(m)
