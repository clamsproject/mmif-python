import itertools
from string import Template
from urllib import request

from mmif import __specver__
from mmif.vocabulary import DocumentTypes, AnnotationTypes

__all__ = [
    'EVERYTHING_JSON',
    'MMIF_EXAMPLES',
    'FRACTIONAL_EXAMPLES',
]

everything_file_url = f"https://raw.githubusercontent.com/clamsproject/mmif/{__specver__}/specifications/samples/everything/raw.json"
old_mmif_w_short_id = f"https://raw.githubusercontent.com/clamsproject/mmif/1.0.5/specifications/samples/everything/raw.json"
EVERYTHING_JSON = request.urlopen(everything_file_url).read().decode('utf-8')
OLD_SHORTID_JSON = request.urlopen(old_mmif_w_short_id).read().decode('utf-8')

# for keys and values in chain all typevers in mmif.vocabulary.*_types modules
# merge into a single dict 
attypevers = {f'{k}_VER': v for k, v in itertools.chain.from_iterable(
    map(lambda x: x._typevers.items(), [AnnotationTypes, DocumentTypes]))}
attypevers['VERSION'] = __specver__

MMIF_EXAMPLES = {
    'everything': Template(EVERYTHING_JSON),
    'old_shortid': Template(OLD_SHORTID_JSON),
}
FRACTIONAL_EXAMPLES = {
    'doc_only': Template("""{
"@type": "http://mmif.clams.ai/vocabulary/TextDocument/$TextDocument_VER",
"properties": {
"id": "td999",
"mime": "text/plain",
"location": "file:///var/archive/transcript-1000.txt" 
}
}"""),
}

MMIF_EXAMPLES = dict((k, v.safe_substitute(**attypevers)) for k, v in MMIF_EXAMPLES.items())
FRACTIONAL_EXAMPLES = dict((k, v.safe_substitute(**attypevers)) for k, v in FRACTIONAL_EXAMPLES.items())
