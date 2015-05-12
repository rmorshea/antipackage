# encoding: utf-8
"""Automagically import single file Python modules from GitHub.
To use, just import `antigravity`:
    import antigravity
Then you can import single file Python modules from GitHub using:
    from github.username.repo.branch.subpackages import module
Modules are downloaded and cached locally. They are automatically updated to the latest version
anytime they change on GitHub.
"""

from __future__ import print_function

import os
import sys
import shutil
import json
import zipfile
import shutil

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

def replace_char(key, value=None, remove=False):
    """Replace `key` with `value` in all import calls

    Notes
    -----
    setting `remove` to True deletes a previously
    created replacement rule assigned to `key`"""
    if not remove:
        if key != '.':
            _conv[key] = value
        else:
            raise ValueError("'.' is a reserved character")
    else:
        del _conv[key]

def repr_conv(chars):
    """Applies replacements specified by `replace_char`"""
    for key in _conv:
        chars = chars.replace(key, _conv[key])
    return chars

def display_download(count, block, size):
    """Displays download progress for sizable files

    Notes
    -----
    Supply as the 'reporthook' for urlretrieve"""
    fraction = size/block
    if fraction>10:
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

def pin(path, **kwargs):
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
        sha or tag pin will force antipackage to draw on
        version of the repository which orrisponds to that
        particular commit during all future imports. Default
        points to 'master' branch of the repository indicated
        by path.
    """
    Author(path,True).write(**kwargs)

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

class Author(object):

    def __init__(self, path, save=True):
        """Container holding private pinning formatters

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
        if len(kwargs) == 0:
            kwargs = {'branch':'master'}
        if len(kwargs) > 1:
            raise ValueError('Only one pin allowed per path')
        name, value = kwargs.items()[0]
        pathing = {'tag':'/tag', 'branch':'/branch', 'sha':'/commit/sha'}
        for key, ext in pathing.items():
            if name==key:
                if value!=data(self.path+ext):
                    repo = GitHubRepo(self.pathlist, name, value)
                    self._new = {'commit':{'sha':repo.sha,'url':repo.url}}
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
        self.comps = fullname.split('.')
        fill = lambda c: c+[None for i in range(3-len(c))]
        index = [_BASE_DIR] + fill(self.comps[:3])
        self.top, self.username, self.repo = index[1:]
        self.index = [key for key in index if key]
        self.path = os.path.join(*self.index)
        self._setup_package()

    def _setup_package(self):
        """Create package directories and __init__ files"""
        if not self.repo:
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

    def waiting(self):
        """Ready for import?"""
        if not self.repo or len(self.comps)>3:
            return True
        return False

    def exists(self):
        """Data and self.path exist?"""
        self.data = data('/'.join(self.index[1:]))
        return os.path.exists(self.path) and self.data

    def update(self):
        """Use existing files?"""
        pathlist = self.index[1:]
        reponame = '.'.join(pathlist)
        for key in self.data:
            if key in ('branch','tag'):
                repo = GitHubRepo(pathlist, key, self.data[key])
                if repo.sha != self.data['commit']['sha']:
                    print('Updating repo: %s' % reponame)
                    self.data['commit']['sha'] = repo.sha
                    return True
        print('Using existing version of: %s' % reponame)
        return False

    def install(self):
        """Download and install new repository at self.path"""
        url = self.zip()
        print("Downloading from: %s" % url)
        sys.stdout.flush()
        temp_file, response = urlretrieve(url, reporthook=display_download)
        zf = zipfile.ZipFile(temp_file)
        fname = zf.filename
        with TemporaryDirectory() as td:
            zf.extractall(td)
            contents = os.listdir(td)
            for name in contents:
                if name.startswith(self.username):
                    tmp_repo = name
            if os.path.exists(self.path):
                shutil.rmtree(self.path)
            os.rename(td+'/'+tmp_repo, self.path)
        self._install_init()

    def zip(self):
        """Returns url to the reopsitory's .zip file"""
        path = ['repos',self.username, self.repo,'zipball']
        if self.data:
            src = self.data['commit']['sha']
        else:
            pin('/'.join(self.index[1:]))
            src = 'master'
        path.append(src)
        return 'https://api.github.com/'+'/'.join(path)

class GitHubRepo(object):

    host = {'top': 'https://api.github.com/repos/{1}/{2}/',
            'branch': 'branches/{0}',
            'sha': 'commits/{0}',
            'tag': 'tags'}

    def __init__(self, pathlist, name='branch', value='master'):
        """Stores key GitHub repository information

        Parameters
        ----------
        pathlist : list
            Of the form `[github, username, repository]`
            and indicates the repository that should be
            accessed
        name : str
            Should be either 'sha', 'tag' or 'branch' and
            indicates the version access method for the repo
        value : str
            specific to `name` and indicated the specific
            repository version being referenced"""
        self.name = name
        self.value = value
        self.url = self._url(pathlist)
        self._git_init()

    def _url(self, pathlist):
        """Format the GitHub url"""
        url = self.host['top'].format(*pathlist)
        url += self.host[self.name].format(self.value)
        return url

    def _git_init(self):
        """Initialize data from GitHub"""
        temp_file = self.fetch()
        with open(temp_file, 'r') as f:
            data = json.load(f)
            self.sha = self._sha(data)

    def fetch(self):
        """Retrieve data from GitHub"""
        temp_file, response = urlretrieve(self.url)
        if not response['Status'] == '200 OK':
            e = 'at '+self.url
            try:
                with open(temp_file, 'r') as f:
                    out = json.load(f)
                e = "message "+e+" = '"+out['message']+"'"
            except:
                pass
            raise GitHubError(e)
        return temp_file

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

# - - - - - - - - - - - -
# Administrative Importer
# - - - - - - - - - - - -

class Importer(object):

    github = GitHubHook

    def __init__(self):
        sys.path.append(_BASE_DIR)

    def find_module(self, fullname, path=None):
        fullname = repr_conv(fullname)
        prefix = fullname.split('.')[0]
        if hasattr(self, prefix):
            source = getattr(self, prefix)(fullname)
            if self.require(source):
                source.install()
                source.required = True

    def require(self, source):
        """Evaluates whether installation should occur"""
        if not source.waiting():
            return not source.exists() or source.update()
        return False

sys.meta_path.insert(0, Importer())