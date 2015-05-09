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
    from urllib import urlopen, urlretrieve
except ImportError:
    # python 3 import
    from urllib.requests import urlopen, urlretrieve

from IPython.utils.tempdir import TemporaryDirectory

class RetrieveError(Exception): pass

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

# - - - - - - - - - - - - - - - - - - - -
# Main Data Management Objects, Functions
# - - - - - - - - - - - - - - - - - - - -

def pin(path, **kwargs):
    """Associate a repo a particular version

    GitHub Paramters
    ----------------
    path : str
        A string indicating a data location via keys delimited
        by a series of '/' characters.
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
    path = path.strip('/')
    data = _Data(path)
    key = path.split('/')[0]
    pointer = Operand(key).use(path,**kwargs)
    if data.items()!=pointer.items():
        data.new = pointer
        data.push()

def data(path=None):
    """Get pinning data at the given path

    GitHub Parameters
    -----------------
    path : str
        A string indicating a data location via keys delimited
        by a series of '/' characters. This is an example of a
        GitHub path - 'github/username/repo/commit/sha'. Given
        this path, the function returns the sha associated with
        that particular repository.
    """
    return dict(_Data(path))

class Operand(object):

    def __init__(self, key):
        """Private function store

        Parameters
        ----------
        key : str
            Idicates the name of a private function in Operand.
            That function is assigned to self.use for public use.
        """
        self.use = getattr(self, '_'+key)

    def _github(self, path, **kwargs):
        """Return a GitPointer object"""
        if len(kwargs) == 0:
            raise ValueError('No pin provided')
        if len(kwargs) > 1:
            raise ValueError('Only one pin allowed per path')
        repo = GitRepo(path.split('/'), *kwargs.items()[0])
        return GitPointer(*repo.info)

class _Data(dict):

    def __init__(self, path=None, new=None):
        """Object makes, gets and deletes pinning data

        Paramters
        ---------
        path : str
            A string indicating a data location via keys
            delimited by a series of '/' characters. Default
            returns all data.
        new : dict
            Optional argument which stores pinning data to
            the given path after running `self.push()`
        """
        self.path = path
        if not new:
            data = self.pull()
            if not data:
                data = dict()
        elif isinstance(new,dict):
            self.new = new
        super(_Data,self).__init__(data)

    @property
    def pathlist(self):
        if self.path:
            return self.path.strip('/').split('/')
        else:
            return list()

    def pull(self):
        """Get pinning data from self.path"""
        pathlist = self.pathlist
        with open(_DATA_PATH,'r') as f:
            if self.path is None:
                return json.load(f)
            else:
                data = json.load(f)
                for k in pathlist:
                    data = data.get(k,None)
                    if not data:
                        return None
                return data

    def push(self):
        """Add self.new to pinning data"""
        fname = _DATA_PATH
        pathlist = self.pathlist

        if os.path.exists(fname):
            with open(fname,'r') as f:
                data = json.load(f)
        else:
            raise RetrieveError('%s does not exist: call setup()' % fname)

        def push_new(data, index=0):
            key = pathlist[index]
            if index+1 == len(pathlist):
                try:
                    data[key] = self.new
                except AttributeError:
                    raise AttributeError('No data to push')
            else:
                new = pathlist[index+1]
                if not data.get(key,None):
                    data[key] = {new: None}
                push_new(data[key],index+1)
            return data

        with open(fname,'w') as f:
            json.dump(push_new(data),f)

    def _del(self):
        """Delete self.path from the pinning data"""
        pathlist = self.pathlist
        err = "No data at '%s'" % '/'.join(pathlist)
        with open(_DATA_PATH,'r+') as f:
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

# - - - - - - - - - - - - - - - - - - - -
# Github Setup, Download, Import Objects
# - - - - - - - - - - - - - - - - - - - -

class GitHandle(object):

    base_dir = _BASE_DIR

    def __init__(self, fullname):
        """Handles imports from GitHub"""
        sys.path.append(self.base_dir)
        comps = fullname.split('.')
        fill = lambda c: c+[None for i in range(3-len(c))]
        self.top, self.username, self.repo = fill(comps[:3])
        self.path = os.path.join(*self.index)
        self._setup_package()

    def _setup_package(self):
        """Create package directories and __init__ files"""
        if not self.repo:
            if not os.path.exists(self.path):
                os.makedirs(self.path)
            self._install_init()

    def _install_init(self):
        if self.path != self.base_dir:
            self._touch()

    def _touch(self):
        i = '__init__.py'
        path = os.path.join(self.path, i)
        with open(path, 'a'):
            os.utime(path, None)

    @property
    def index(self):
        raw = [self.base_dir, self.top, self.username, self.repo]
        return [prop for prop in raw if prop]

    def waiting(self):
        """Ready for import?"""
        if not self.repo:
            return True
        return False

    def exists(self):
        """Data and self.path exist?"""
        self.data = _Data('/'.join(self.index[1:]))
        return os.path.exists(self.path) and self.data

    def update(self):
        """Use existing files?"""
        pathlist = self.index[1:]
        reponame = '.'.join(pathlist)
        for key in self.data:
            if key in ('branch','tag'):
                repo = GitRepo(pathlist, key, self.data[key])
                if repo.sha != self.data['commit']['sha']:
                    print('Updating repo: %s' % reponame)
                    self.data['commit']['sha'] = repo.sha
                    return True
        print('Using existing version: %s' % reponame)
        return False

    def install(self):
        """Download and install new repository at self.path"""
        url = self.zip()
        print('Downloading zip: %s' % url)
        sys.stdout.flush()
        temp_file, response = urlretrieve(url)
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
            repo = GitRepo(self.index[1:])
            pin = GitPointer(*repo.info)
            self.data.new = pin
            self.data.push()
            src = repo.value
        path.append(src)
        return 'https://api.github.com/'+'/'.join(path)

class GitRepo(object):

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
        self.url = self._new_url(pathlist)
        self.sha = self._new_sha()

    @property
    def info(self):
        return self.url, self.sha, self.name, self.value

    def _new_url(self, pathlist):
        """Format the url"""
        url = self.host['top'].format(*pathlist)
        url += self.host[self.name].format(self.value)
        return url

    def _new_sha(self):
        """Return the sha"""
        temp_file = self.fetch()
        if self.name!='sha':
            with open(temp_file, 'r') as f:
                data = json.load(f)
                if self.name == 'tag':
                    data = self._handle_tag(data)
                return data['commit']['sha']
        else:
            return self.value

    def fetch(self):
        """Retrieve github data"""
        temp_file, response = urlretrieve(self.url)
        if not response['Status'] == '200 OK':
            e = "Invalid url %s" % self.url
            try:
                with open(temp_file, 'r') as f:
                    data = json.load(f)
                e += " github message = '"+data['message']+"'"
            except:
                pass
            raise RetrieveError(e)
        return temp_file

    def _handle_tag(self, data):
        """Handle tag data"""
        for tag in data:
            if tag['name']==self.value:
                return tag
        raise RetrieveError("No tag with name: '%s'" % value)

class GitPointer(dict):

    def __init__(self, url, sha, name, value=None):
        """Returns formated GitHub pinning data"""
        p = {'id':'pin', 'commit':{'sha':sha,'url':url}}
        if name=='branch':
            p['branch'] = value
        elif name=='tag':
            p['tag'] = value
        super(GitPointer,self).__init__(p)

# - - - - - - - - - - - -
# Administrative Importer
# - - - - - - - - - - - -

class Importer(object):

    github = GitHandle
    required = True

    def require(self, source):
        """Evaluates whether installation should occur"""
        if not source.waiting():
            self.required = False
            return not source.exists() or source.update()
        return False

    def find_module(self, fullname, path=None):
        prefix = fullname.split('.')[0]
        if self.required and hasattr(self, prefix):
            source = getattr(self, prefix)(fullname)
            if self.require(source):
                source.install()

sys.meta_path.insert(0, Importer())