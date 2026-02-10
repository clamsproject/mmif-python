"""
MMIF document location helper module for ``http`` and ``https`` schemes.

If you want to write your own docloc scheme handler, please use the source
code of this module as a reference. See the :ref:`plug-in section <docloc_plugin>`
for more information.
"""

import urllib.request
import urllib.error


def resolve(docloc):
    try:
        if docloc.startswith('http://') or docloc.startswith('https://'):
            return urllib.request.urlretrieve(docloc)[0]
        else:
            raise ValueError(f'cannot handle document location scheme: {docloc}')
    except urllib.error.URLError as e:
        raise e
    
    
def help():
    return "location must be a URL string."
