import os
import json
from git import pin as gitpin, pinform as gitform

class RetrieveError(Exception): pass
_base_dir = os.path.expanduser('~/.antipackage')

def pin(path, **kwargs):
    """Mark a repo with a branch, tag, or sha pin
    Paramters
    ---------
    path : str
        A string indicating the repository location example:
        'github/username/repo'
    **kwargs : dict
        There should only be one keyword argument. That being
        for either 'branch', 'tag', or 'sha' corrisponding to
        the kinds of pins associated with a repository.
        Marking a repo with a branch pin will cause antipackage
        to pull from the most recent version found on that
        branch when importing. However marking a repo with a
        sha or tag pin will force antipackage to draw on
        version of the repository which orrisponds to that
        particular commit during all future imports.
    """
    if len(kwargs) == 0:
        raise ValueError('No pin provided')
    if len(kwargs) > 1:
        raise ValueError('Only one pin allowed per path')
    if path.startswith('github'):
        pathlist = _parse_path(path)
        name, value = kwargs.items()[0]
        if data(path+'/'+gitform[name])!=value:
            p = gitpin(pathlist, name, value)
            __push__(pathlist, p)

def data(path=None):
    """Get pinning data at the given path
    Parameters
    ----------
    path : str
        Similar to the path given in pin(), this function
        with return a dictionary containing pinning data.
        For example 'github/username/repo/commit/sha' will
        return the sha associated with that particular
        repository.
    """
    err = "No data at '%s'" % path
    pathlist = _parse_path(path)
    with open(_base_dir+'/pinnings.json','r') as f:
        if path is None:
            return json.load(f)
        else:
            data = json.load(f)
            for k in pathlist:
                data = data.get(k,None)
                if not data:
                    return None
            return data

def _parse_path(path):
    if path:
        if path[0]=='/':
            path = path[1:]
        if path[-1]=='/':
            path = path[:-1]
        return path.split('/')

def __push__(pathlist, pin):
    """Push a pin to the location given by pathlist
    Notes
    -----
    pins can be pushed to any path
    """
    fname = _base_dir+'/pinnings.json'
    
    if os.path.exists(fname):
        with open(fname,'r') as f:
            data = json.load(f)
    else:
        raise RetrieveError('%s does not exist: call setup()' % fname)

    def push_pin(data, index=0):
        key = pathlist[index]
        if index+1 == len(pathlist):
            data[key] = pin
        else:
            new = pathlist[index+1]
            if not data.get(key,None):
                data[key] = {new: None}
            push_pin(data[key],index+1)
        return data

    with open(fname,'w') as f:
        json.dump(push_pin(data),f)

def __pull__(pathlist):
    """Remove a pin from the location given by pathlist
    Notes
    -----
    Only data structures containing an attribute 'id' with
    the value 'pin' can be deleted.
    """
    err = "No data at '%s'" % '/'.join(pathlist)
    with open(_base_dir+'/pinnings.json','r+') as f:
        raw = f.read()
        if raw == str():
            raise RetrieveError("'pinnings.json' is empty")
        else:
            data = json.loads(raw)

        def pull_pin(data, index=0):
            key = pathlist[index]
            if index+1 == len(pathlist):
                if data[key].get('id',None) == 'pin':
                    del data[key]
                else:
                    raise RetrieveError('Not a pin')
            else:
                new = pathlist[index+1]
                if not data.get(key,None):
                    raise RetrieveError(err)
                pull_pin(data[key],index+1)
            return data

        json.dump(pull_pin(data),f)