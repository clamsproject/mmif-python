from urllib import request

from mmif import __specver__
from string import Template

__all__ = ['JSON_STR',
           'MMIF_EXAMPLES',
           'SUB_EXAMPLES']


def substitute(example_dict: dict) -> dict:
    return dict((k, Template(v).substitute(specver=__specver__)) for k, v in example_dict.items())


everything_file_url = f"https://raw.githubusercontent.com/clamsproject/mmif/{__specver__}/specifications/samples/everything/raw.json"
res = request.urlopen(everything_file_url)
# TODO (krim @ 11/23/20): instead of hard-code version string in the example file in the `mmif` repository,
# we can use a symbol for substitution that can be replaced with actual spec version
# by a "builder" there
JSON_STR = res.read().decode('utf-8').replace('0.2.0', '${specver}')

example_templates = dict(
    mmif_example1=JSON_STR
)

sub_example_templates = {'doc_example': """{
  "@type": "http://mmif.clams.ai/${specver}/vocabulary/TextDocument",
    "properties": {
      "id": "td999",
      "mime": "text/plain",
      "location": "/var/archive/transcript-1000.txt" 
    }
}"""}

MMIF_EXAMPLES = substitute(example_templates)
SUB_EXAMPLES = substitute(sub_example_templates)
