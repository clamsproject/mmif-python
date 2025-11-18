import itertools
import os
import subprocess
from string import Template
from urllib import request

from mmif import __specver__
from mmif.vocabulary import DocumentTypes, AnnotationTypes

__all__ = [
    'EVERYTHING_JSON',
    'MMIF_EXAMPLES',
    'FRACTIONAL_EXAMPLES',
]


def _load_from_url_or_git(url):
    """
    Load content from URL or local git repository.
    If LOCALMMIF env var is set, use git show to load from local repo.
    LOCALMMIF should be the path to the local mmif repository.
    """
    localmmif = os.environ.get('LOCALMMIF')
    if localmmif:
        # Extract the version/branch and file path from the URL
        # URL format: https://raw.githubusercontent.com/clamsproject/mmif/{version}/{filepath}
        url_prefix = "https://raw.githubusercontent.com/clamsproject/mmif/"
        if url.startswith(url_prefix):
            remainder = url[len(url_prefix):]
            parts = remainder.split('/', 1)
            if len(parts) == 2:
                version, filepath = parts
                # Use git show to get the file from the specific version
                git_ref = f"{version}:{filepath}"
                try:
                    result = subprocess.run(
                        ['git', 'show', git_ref],
                        cwd=localmmif,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    return result.stdout
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f"Failed to load {git_ref} from local git repo at {localmmif}: {e.stderr}")

    # Fallback to URL loading
    return request.urlopen(url).read().decode('utf-8')

everything_file_url = f"https://raw.githubusercontent.com/clamsproject/mmif/{__specver__}/specifications/samples/everything/raw.json"
old_mmif_w_short_id_url = f"https://raw.githubusercontent.com/clamsproject/mmif/1.0.5/specifications/samples/everything/raw.json"
EVERYTHING_JSON = _load_from_url_or_git(everything_file_url)
OLD_SHORTID_JSON = _load_from_url_or_git(old_mmif_w_short_id_url)
SWT_1_0_JSON = open('tests/samples/1.0/swt.mmif').read()

# for keys and values in chain all typevers in mmif.vocabulary.*_types modules
# merge into a single dict 
attypevers = {f'{k}_VER': v for k, v in itertools.chain.from_iterable(
    map(lambda x: x._typevers.items(), [AnnotationTypes, DocumentTypes]))}
attypevers['VERSION'] = __specver__

MMIF_EXAMPLES = {
    'everything': Template(EVERYTHING_JSON),
    'mmif_old_shortid': Template(OLD_SHORTID_JSON),
    'mmif_swt_1_0': Template(SWT_1_0_JSON),
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
