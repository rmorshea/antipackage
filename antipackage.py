# encoding: utf-8
"""Automagically import single file Python modules from GitHub.

To use, just import `antipackage`:

    import antipackage

Then you can import single file Python modules from GitHub using:
    from github.username.repo import module
Modules are downloaded and cached locally. They are automatically updated to the latest version
anytime they change on GitHub.
"""

from __future__ import print_function

import os
import sys

import hashlib
import shutil
# Imports for urllib are different in py2 vs. py3
try: 
    from urllib import urlretrieve
except ImportError:
    from urllib.request import urlretrieve


try:
    # python 2 import
    from urllib import urlretrieve
except ImportError:
    # python 3 import
    from urllib.requests import urlretrieve

from IPython.utils.tempdir import TemporaryDirectory

class RetrieveError(Exception): pass
class GitHubError(Exception): pass

# - - - - - - - - -
# Utility Functions
# - - - - - - - - -

_conv = {}
_reserved = ['.', os.path.sep, 'github']

def import_replacement(key, value=None, remove=False):
    """Replaces all instances of `key` with `value` in import calls

    Notes
    -----
    setting `remove` to True deletes a previously
    created replacement rule assigned to `key`"""
    if not remove:
        if key not in _reserved:
            _conv[key] = value
        else:
            raise ValueError("'%s' is a reserved key" % key)
    else:
        del _conv[key]

def _repr_conv(chars):
    """Applies replacements specified by `import_replacement`"""
    for key in _conv:
        chars = chars.replace(key, _conv[key])
    return chars

def _undo_conv(chars):
    """Undoes replacements specified by `import_replacement`"""
    for key in _conv:
        chars = chars.replace(_conv[key], key)
    return chars

def display_download(count, block, size):
    """Displays download progress for sizable files

    Notes
    -----
    Supply as the 'reporthook' for urlretrieve"""
    fraction = size/block
    if fraction>3:
        percent = int(count*100/fraction)
        sys.stdout.write("\rDownload in progress... %d%%" % percent)
        sys.stdout.flush()

# - - - - - - - - - - - - - - - -
# Setup Base Dir and Pinning File
# - - - - - - - - - - - - - - - -

def _setup(directory, fname):
    base_path = os.path.expanduser('~/'+directory)
    if not os.path.exists(base_path):
        os.makedirs(base_path)
    data_path = base_path+'/'+fname
    if not os.path.isfile(data_path):
        with open(data_path, 'w') as f:
            json.dump({},f)
    return base_path, data_path

_BASE_DIR, _DATA_PATH = _setup('.antipackage','pinnings.json')

# - - - - - - - - - - - - - - - - - - - - -
# Main Data Management Object and Functions
# - - - - - - - - - - - - - - - - - - - - -

def pin(path, branch=None, sha=None, tag=None):
    """Associate a repo with a particular version

    GitHub Paramters
    ----------------
    path : str
        A string indicating a data location via keys delimited
        by a series of '/' characters. This is an example of a
        GitHub path - 'github/username/repo'.
    **kwargs : dict
        There should only be one keyword argument. That being
        for either 'branch', 'tag', or 'sha' corrisponding to
        the kinds of pins associated with a repository.
        Marking a repo with a branch pin will cause antipackage
        to pull from the most recent version found on that
        branch when importing. However marking a repo with a
        sha or tag pin will force antipackage to draw on the
        version of the repository which corrisponds to that
        particular commit during all future imports. Default
        points to 'master' branch of the repository indicated
        by path.
    """
    raw = {'branch':branch, 'sha':sha, 'tag':tag}
    kwargs = {k:v for k,v in raw.items() if v is not None}
    PackageState(path).write(**kwargs)

def data(path=None):
    """Get a dictionary of pinning data at the given path

    GitHub Parameters
    -----------------
    path : str
        A string indicating a data location via keys delimited
        by a series of '/' characters.
    """
    with open(_DATA_PATH,'r') as f:
        if not path:
            return json.load(f)
        else:
            pathlist = path.strip('/').split('/')
            data = json.load(f)
            for k in pathlist:
                data = data.get(k,dict())
                if not data:
                    return dict()
            return data

class PackageState(object):

    def __init__(self, path, source=None, save=True):
        """Container for private pinning formatters that write to file

        Parameters
        ----------
        path : str
            A string indicating a data location via keys delimited
            by a series of '/' characters. The first key of the path`
            idicates the name of a private function in `self`. That
            function is assigned to `self.write` for public use. For
            example, the key 'github' sets up a formatter to write
            GitHub pinning data.
        save : bool
            Default action causes pins writen with 'self.write' to be
            pushed to the path and does not return them. If given as
            'False' the formatter in 'self.write' returns the pin and
            does not push them to the path.
        """
        self.source = source
        self.path = path.strip('/')
        self.pathlist = self.path.split('/')
        try:
            self.write = getattr(self, '_'+self.pathlist[0])
        except AttributeError:
            raise AttributeError("No pinning formatter for: '%s'" % self.pathlist[0])
        self.save = save
        self._new = None

    def _github(self, **kwargs):
        """Return or write GitHub pinning data"""
        force = kwargs.pop('force',False)
        if len(kwargs) == 0:
            kwargs = {'branch':'master'}
        if len(kwargs) > 1:
            raise ValueError('Only one pin allowed per path')
        name, value = kwargs.items()[0]
        pathing = {'tag':'/tag', 'branch':'/branch', 'sha':'/commit/sha'}
        for key, ext in pathing.items():
            if name==key:
                if force or value!=data(self.path+ext):
                    if not self.source:
                        username = self.pathlist[1]
                        reponame = self.pathlist[2]
                        self.source = GitHubRepo(username, reponame, name, value)
                    self.source.pull_data()
                    self._new = {'commit':{'sha':self.source.sha,'url':self.source.url}}
                    if name=='branch':
                        self._new['branch'] = value
                    elif name=='tag':
                        self._new['tag'] = value
                    self._new['id'] = 'pin'
                if self._new and self.save:
                    self.push()
                else:
                    return self._new or data(self.path)
        else:
            if name not in ('branch','tag','sha'):
                raise ValueError("Keywords must be 'branch',"
                                " 'tag' or 'sha' not: '%s'" % name)

    def push(self):
        """Write pinning data to file"""
        try:
            with open(_DATA_PATH,'r') as f:
                data = json.load(f)
        except IOError:
            raise IOError("%s does not exist: call '_setup()'" % fname)

        def push_new(data, index=0):
            key = self.pathlist[index]
            if index+1 == len(self.pathlist):
                if self._new:
                    data[key] = self._new
                else:
                    raise AttributeError('No data to push')
            else:
                new = self.pathlist[index+1]
                if not data.get(key,None):
                    data[key] = {new: None}
                push_new(data[key],index+1)
            return data

        with open(_DATA_PATH,'w') as f:
            json.dump(push_new(data),f)

# - - - - - - - - - - - - - - - - - -
# Github Import Hook and Setup Object
# - - - - - - - - - - - - - - - - - -

class GitHubHook(object):

    def __init__(self, fullname):
        """Handles imports from GitHub"""
        self.repo = None
        self.comps = fullname.split('.')
        fill = lambda c: c+[None for i in range(3-len(c))]
        index = [_BASE_DIR] + fill(self.comps[:3])
        self.top, self.username, self.reponame = index[1:]
        self.index = [key for key in index if key]
        self.path = _undo_conv(os.path.join(*self.index))
        self._setup_package()

    def update_or_install(self):
        """Evaluates whether installation should occur"""
        if len(self.comps)==3 and (not self._exists() or self._update()):
            self._install()

    def _setup_package(self):
        """Create package directories and __init__ files"""
        if not self.reponame:
            if not os.path.exists(self.path):
                os.makedirs(self.path)
            self._install_init()

    def _install_init(self):
        if self.path != _BASE_DIR:
            self._touch()

    def _touch(self):
        i = '__init__.py'
        path = os.path.join(self.path, i)
        with open(path, 'a'):
            os.utime(path, None)

    def _exists(self):
        """Data and self.path exist?"""
        self.data = data('/'.join(self.index[1:]))
        return os.path.exists(self.path) and self.data

    def _update(self):
        """Use existing files?"""
        pathlist = self.index[1:]
        reponame = '.'.join(pathlist)
        for key in self.data:
            if key in ('branch','tag'):
                try:
                    self.repo = GitHubRepo(self.username,self.reponame, key, self.data[key])
                    self.repo.pull_data()
                    if self.repo and self.repo.sha != self.data['commit']['sha']:
                        print('Updating repo: %s' % reponame)
                        return True
                except GitHubError, e:
                    print(str(e))
        print('Using existing version of: %s' % reponame)
        return False

    def _install(self):
        """Install new repository at self.path"""
        if not self.repo:
            self.repo = GitHubRepo(self.username,self.reponame)
        ps = PackageState('/'.join(self.index[1:]),self.repo)
        ps.write(**{self.repo.name:self.repo.value,'force':True})
        self.repo.download(self.path)
        self._install_init()

class GitHubRepo(object):

    host = {'top': 'https://api.github.com/repos/{0}/{1}/',
            'branch': 'branches/{0}',
            'sha': 'commits/{0}',
            'tag': 'tags'}

    def __init__(self, username, reponame, name='branch', value='master'):
        """Stores downloads and formats key GitHub repository information

        Parameters
        ----------
        username : str
            A GitHub username
        reponame:
            The name of a repository owned by the given user
        name : str
            Should be either 'sha', 'tag' or 'branch' and
            indicates the version access method for the repo
        value : str
            specific to `name` and indicated the specific
            repository version being referenced"""
        self.username = username
        self.reponame = reponame
        self.name = name
        self.value = value
        names = (self.username,self.reponame)
        url = self.host['top'].format(*names)
        url += self.host[self.name].format(self.value)
        self.url = url
        self._pulled = False

    def pull_data(self, force=False):
        """Initialize data from GitHub"""
        if force or not self._pulled:
            filepath = self._fetch()
            with open(filepath, 'r') as f:
                data = json.load(f)
                self.sha = self._sha(data)
                self.zip = self._zip()
            self._pulled = True

    def download(self, path):
        """Download and save new repository to path"""
        self.pull_data()
        print("Downloading from: %s" % self.zip)
        sys.stdout.flush()
        filepath, response = urlretrieve(self.zip,reporthook=display_download)
        zf = zipfile.ZipFile(filepath)
        fname = zf.filename
        with TemporaryDirectory() as td:
            zf.extractall(td)
            contents = os.listdir(td)
            for name in contents:
                if name.startswith(self.username):
                    tmp_repo = name
            if os.path.exists(path):
                shutil.rmtree(path)
            os.rename(td+'/'+tmp_repo, path)
        zf.close()

    def _fetch(self):
        """Retrieve data from GitHub"""
        filepath, response = urlretrieve(self.url)
        if response['Status'] != '200 OK':
            e = 'at '+self.url
            try:
                with open(filepath, 'r') as f:
                    out = json.load(f)
                e = "message "+e+" = '"+out['message']+"'"
            except:
                pass
            raise GitHubError(e)
        return filepath

    def _sha(self, data):
        """Return the sha"""
        if self.name!='sha':
            if self.name == 'tag':
                data = self._handle_tag(data)
            return data['commit']['sha']
        else:
            return self.value

    def _handle_tag(self, data):
        """Retrieve data from a """
        for tag in data:
            if tag['name']==self.value:
                return tag
        raise RetrieveError("No tag with name: '%s'" % value)

    def _zip(self):
        """Returns url to the reopsitory's .zip file"""
        if self.sha:
            path = ['repos',self.username, self.reponame,'zipball',self.sha]
        else:
            raise RetrieveError('no sha found: call `self.download_data()`')
        return 'https://api.github.com/'+'/'.join(path)

# - - - - - - - - - - - -
# Administrative Importer
# - - - - - - - - - - - -

class Importer(object):

    hooks = {'github':GitHubHook}

    def __init__(self):
        sys.path.append(_BASE_DIR)

    def find_module(self, fullname, path=None):
        fullname = _repr_conv(fullname)
        prefix = fullname.split('.')[0]
        if prefix in self.hooks:
            hook = self.hooks[prefix](fullname)
            hook.update_or_install()


sys.meta_path.insert(0, Importer())
