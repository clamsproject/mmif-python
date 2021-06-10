from urllib import request

from mmif import __specver__
from string import Template

__all__ = [
    'EVERYTHING_JSON',
    'MMIF_EXAMPLES',
    'FRACTIONAL_EXAMPLES',
]

everything_file_url = f"https://raw.githubusercontent.com/clamsproject/mmif/{__specver__}/specifications/samples/everything/raw.json"
res = request.urlopen(everything_file_url)
EVERYTHING_JSON = res.read().decode('utf-8')

MMIF_EXAMPLES = {
    'everything': Template(EVERYTHING_JSON),
}
FRACTIONAL_EXAMPLES = {
    'doc_only': Template("""{
"@type": "http://mmif.clams.ai/${VERSION}/vocabulary/TextDocument",
"properties": {
"id": "td999",
"mime": "text/plain",
"location": "file:///var/archive/transcript-1000.txt" 
}
}"""),
}

MMIF_EXAMPLES = dict((k, v.substitute(VERSION=__specver__)) for k, v in MMIF_EXAMPLES.items())
FRACTIONAL_EXAMPLES = dict((k, v.substitute(VERSION=__specver__)) for k, v in FRACTIONAL_EXAMPLES.items())
