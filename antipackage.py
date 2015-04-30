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
import hashlib
import shutil
import json
import zipfile
import shutil
import pinning

try:
    # python 2 import
    from urllib import urlopen, urlretrieve
except ImportError:
    # python 3 import
    from urllib.requests import urlopen, urlretrieve

from IPython.utils.tempdir import TemporaryDirectory

class RetrieveError(Exception): pass

# - - - - - - - -

_base_dir = os.path.expanduser('~/.antipackage')

def _setup(base_dir, fname):
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    path = base_dir+'/'+fname
    if not os.path.isfile(path):
        with open(path, 'w') as f:
            json.dump({},f)

_setup(_base_dir,'pinnings.json')

# - - - - - -

class GitHubImporter(object):

    base_dir = _base_dir
    git = 'https://api.github.com'

    def __init__(self):
        
        sys.path.append(self.base_dir)
        self.branch = None

    @property
    def pathlist(self):
        raw = [self.base_dir, self.top, self.username, self.repo]
        return [p for p in raw if p]

    def _parse_fullname(self,fullname):
        comps = fullname.split('.')
        fill = lambda c: c+[None for i in range(3-len(c))]
        self.top, self.username, self.repo = fill(comps[:3])
        if len(comps)==3:
            self._data = pinning.data('/'.join(comps))
        else:
            self._data = None

    def _setup_package(self, path):
        if len(self.pathlist)<4:
            if not os.path.exists(path):
                os.makedirs(path)
            self._install_init(path)

    def _install_init(self, path):
        if path != self.base_dir:
            ipath = os.path.join(path, '__init__.py')
            self._touch(ipath)

    def _touch(self, path):
        with open(path, 'a'):
            os.utime(path, None)

    def url(self):
        path = ['repos',self.username, self.repo,'zipball']
        if self._data:
            sha = self._data['commit']['sha']
            path.append(sha)
        else:
            value = 'master'
            pinning.pin('/'.join(self.pathlist[1:]),
                branch=value)
            path.append(value)
        return self.git+'/'+'/'.join(path)

    def _install_package(self, path):
        url = self.url()
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
            if os.path.exists(path):
                shutil.rmtree(path)
            os.rename(td+'/'+tmp_repo, path)
        self._install_init(path)

    def _update(self):
        repo = '.'.join(self.pathlist[1:])
        for k in ['branch', 'tag']:
            if k in self._data:
                plist = self.pathlist[1:]
                url = pinning.git._url(plist, k, self._data[k])
                sha = pinning.git._sha(url, k, self._data[k])
                if sha != self._data['commit']['sha']:
                    print('Updating repo: %s' % repo)
                    return True
        print('Using existing version: %s' % repo)
        return False

    def _make_package(self, fullname):
        self._parse_fullname(fullname)
        path = os.path.join(*self.pathlist)
        self._setup_package(path)
        if len(fullname.split('.'))==3:
            no_data = not self._data
            no_path = not os.path.exists(path)
            if no_data or no_path or self._update():
                self._install_package(path)

    def find_module(self, fullname, path=None):
        print('find_module', fullname, path)
        if fullname.startswith('github'):
            self._make_package(fullname)
        return None
        
sys.meta_path.insert(0, GitHubImporter())