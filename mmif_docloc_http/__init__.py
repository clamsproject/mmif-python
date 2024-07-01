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
