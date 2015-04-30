import os
import json
try:
    # python 2 import
    from urllib import urlopen, urlretrieve
except ImportError:
    # python 3 import
    from urllib.requests import urlopen, urlretrieve

_urlhost = {'top': 'https://api.github.com/repos/{1}/{2}/',
            'branch': 'branches/{0}',
            'sha': 'commits/{0}',
            'tag': 'tags'}

def pin(pathlist, name, value):
    """Returns a pin containing data for imports

    Parameters
    ----------
    pathlist : list
        list containing the repository path
    name : str
        name corrisponding to the pin type
    value : str
        kind of data the pin should store, i.e.
        a branch name, tag name, or sha string
    """
    url = _url(pathlist, name, value)
    sha = _sha(url, name, value)
    return make_pin(url, sha, name, value)

def make_pin(url, sha, name, value=None):
    """Returns a pin containing data for imports

    Parameters
    ----------
    url : str
        url that the information was sourced from
    sha : str
        the sha string corrisponding to a commit
    name : str
        name corrisponding to the pin type
    value : str
        kind of data the pin should store, i.e.
        a branch name, tag name (sha is already
        included in the pin)
    """
    p = {'id':'pin'}
    p['commit'] = {'sha':sha,'url':url}
    if name=='branch':
        p['branch'] = value
    elif name=='tag':
        p['tag'] = value
    return p

def _url(pathlist, name, value):
    url = _urlhost['top'].format(*pathlist)
    url += _urlhost[name].format(value)
    return url

def _sha(url, name, value=None):
    issha = (name=='sha')
    temp_file = _data(url, issha)
    if not issha:
        with open(temp_file, 'r') as f:
            data = json.load(f)
            if name == 'tag':
                data = _tag(data,value)
            return data['commit']['sha']
    else:
        return value

def _data(url, verify=False):
    temp_file, response = urlretrieve(url)
    if not response['Status'] == '200 OK':
        e = "Invalid url %s" % url
        try:
            with open(temp_file, 'r') as f:
                data = json.load(f)
            e += " github message = '"+data['message']+"'"
        except:
            pass
        raise RetrieveError(e)
    if not verify:
        return temp_file

def _tag(data, value):
    for tag in data:
        if tag['name']==value:
            return tag
    raise RetrieveError("No tag with name: '%s'" % value)