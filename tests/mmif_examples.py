import itertools
from pathlib import Path
from string import Template

from mmif import __specver__
from mmif.vocabulary import AnnotationTypes, DocumentTypes

__all__ = [
    'ATTYPE_PREFIX',
    'EVERYTHING_JSON',
    'MMIF_EXAMPLES',
    'FRACTIONAL_EXAMPLES',
]

# Canonical URI prefix for vocabulary types (e.g.,
# ``http://clams.ai/vocabulary/type/TimeFrame/v6``). Derived from the
# installed ``clams-vocabulary`` so it stays in sync if the prefix
# ever changes again. Tests should build expected URIs as
# ``f"{ATTYPE_PREFIX}/{TypeName}/{version}"`` rather than hardcoding.
ATTYPE_PREFIX = AnnotationTypes.Annotation.base_uri


_EXAMPLES_DIR = (
    Path(__file__).resolve().parent / 'mmif-examples'
)

EVERYTHING_JSON = (_EXAMPLES_DIR / 'everything' / 'raw.json').read_text()
OLD_SHORTID_JSON = (_EXAMPLES_DIR / '1.0.5-old-shortid.json').read_text()
SWT_1_0_JSON = (_EXAMPLES_DIR / 'swt-1.0.mmif').read_text()

# Build ``{TypeName_VER: vN, VERSION: X.Y.Z}`` from the installed
# ``clams-vocabulary`` package so templated fixtures always exercise the
# currently installed type versions. Fixtures that need to pin a historical
# version (e.g., ``1.0.5-old-shortid.json``) hardcode URIs inline rather
# than using these templates.
attypevers = {f'{k}_VER': v for k, v in itertools.chain.from_iterable(
    map(lambda x: x._typevers.items(), [AnnotationTypes, DocumentTypes]))}
attypevers['VERSION'] = __specver__

MMIF_EXAMPLES = {
    'everything': Template(EVERYTHING_JSON).safe_substitute(**attypevers),
    # Historical fixture: 1.0.5-era types, already hardcoded inline.
    # Do NOT run template substitution on this file.
    'mmif_old_shortid': OLD_SHORTID_JSON,
    'mmif_swt_1_0': SWT_1_0_JSON,
}

FRACTIONAL_EXAMPLES = {
    'doc_only': Template(
        '{'
        f'"@type": "{ATTYPE_PREFIX}/TextDocument/$TextDocument_VER",'
        '"properties": {'
        '"id": "td999",'
        '"mime": "text/plain",'
        '"location": "file:///var/archive/transcript-1000.txt"'
        '}'
        '}'
    ).safe_substitute(**attypevers),
}
