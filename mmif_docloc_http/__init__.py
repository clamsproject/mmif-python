import urllib.request
import urllib.error

_cache = {}


def resolve(docloc):
    if docloc in _cache:
        return _cache[docloc]
    try:
        if docloc.startswith('http://') or docloc.startswith('https://'):
            path = urllib.request.urlretrieve(docloc)[0]
            _cache[docloc] = path
            return path
        else:
            raise ValueError(f'cannot handle document location scheme: {docloc}')
    except urllib.error.URLError as e:
        raise e


def help():
    return "location must be a URL string."
