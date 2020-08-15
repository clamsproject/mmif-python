_res_pkg = 'res'
_ver_pkg = 'ver'
_vocabulary_pkg = 'vocab'
__version__ = 'UNK'
__specver__ = 'UNK'
_schema_res_oriname = 'schema/mmif.json'
_schema_res_name = 'mmif.json'
_vocab_res_oriname = 'vocabulary/clams.vocabulary.yaml'
_vocab_res_name = 'clams.vocabulary.yaml'
vocab = None        # placeholder for importing vocab package

# now try to import autogenerated packages
# these packages are generated at build time (setup.py build/develop/Xdist)
import importlib
try:
    i = importlib.import_module(f'{__name__}.{_ver_pkg}')
    __version__ = i.__version__  # pytype: disable=attribute-error
    __specver__ = i.__specver__  # pytype: disable=attribute-error
except ImportError:
    # don't set version
    pass
try:
    vocab = importlib.__import__(f'{__name__}.{_vocabulary_pkg}', globals(), locals(), ['*'])
except ImportError:
    # vocab is left as a None type, and cannot be imported
    pass

if vocab is not None: # means the whole package is not in pre-build stage and ready to go
    from mmif.serialize import *
