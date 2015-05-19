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
from urllib import urlopen, urlretrieve
import hashlib
import shutil

class InstallError(Exception):
    pass

class HTTPError(Exception):
    pass

#def wipe_installs():
#    print('Wipe all local anitpackage installs? (y/n)')
#    if raw_input() is 'y':
#        shutil.rmtree(os.path.expanduser('~/.antipackage'))
#        print('antipackage wiped')
#    else:
#        print('cancled')

def assume_brancher():
    """Replace all GitHubImporters in sys.meta_path with one GitHubBrancher"""
    sys.meta_path = [imp for imp in sys.meta_path if not isinstance(imp, GitHubImporter)]
    sys.meta_path.insert(0, GitHubBrancher())

def assume_importer():
    """Replace all GitHubImporters in sys.meta_path with one GitHubImporter"""
    sys.meta_path = [imp for imp in sys.meta_path if not isinstance(imp, GitHubImporter)]
    sys.meta_path.insert(0, GitHubImporter())

def insert_brancher():
    """Add a GitHubBrancher to sys.meta_path"""
    sys.meta_path.append(GitHubBrancher())

def insert_importer():
    """Add a GitHubImporter to sys.meta_path"""
    sys.meta_path.append(GitHubImporter())

class GitHubImporter(object):
    
    def __init__(self):
        self.base_dir = os.path.expanduser('~/.antipackage')
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
        sys.path.append(self.base_dir)

    def _parse_fullname(self, fullname):
        comps = fullname.split('.')
        top, username, repo, modname = None, None, None, None
        if len(comps)>=1:
            top = 'github'
            if len(comps)>=2:
                username = comps[1]
                if len(comps)>=3:
                    repo = comps[2]
                    if len(comps)==4:
                        modname = comps[3]
                    elif len(comps)>4:
                        raise InstallError('Import path must be github.username.repo.module:'
                                            ' got {0} instead.'.format(fullname))
        return top, username, repo, modname
        
    def _install_init(self, path):
            ipath = os.path.join(path, '__init__.py')
            # print('Installing: ', ipath)
            self._touch(ipath)

    def _setup_package(self, path):
        if not os.path.exists(path):
            os.makedirs(path)
        self._install_init(path)

    def _update_if_changed(self, old, new):
        new_hash = ''
        with open(new, 'r') as f:
            new_hash = hashlib.md5(f.read()).hexdigest()
        old_hash = ''
        if os.path.isfile(old):
            with open(old, 'r') as f:
                old_hash = hashlib.md5(f.read()).hexdigest()
        if new_hash!=old_hash:
            shutil.copy(new, old)
            if old_hash:
                return 'updated'
            else:
                return 'installed'
        return 'noaction'

    def _touch(self, path):
        with open(path, 'a'):
            os.utime(path, None)

    def _install_module(self, fullname):
        top, username, repo, modname = self._parse_fullname(fullname)
        url = 'https://raw.githubusercontent.com/%s/%s/master/%s' % (username, repo, modname+'.py')
        print('Downloading: ', url)
        try:
            tmp_file, resp = urlretrieve(url)
            with open(tmp_file, 'r') as f:
                new_content = f.read()
            if new_content=='Not Found':
                raise InstallError('remote file does not exist')
        except IOError:
            raise InstallError('error downloading file')
        
        new = tmp_file
        old = self._install_path(fullname)
        updated = self._update_if_changed(old, new)
        if updated=='updated':
            print('Updating module: ', fullname)
        elif updated=='installed':
            print('Installing module: ', fullname)
        elif updated=='noaction':
            print('Using existing version: ', fullname)

    def _install_path(self, fullname):
        top, username, repo, modname = self._parse_fullname(fullname)
        return os.path.join(self.base_dir, top, username, repo, modname+'.py')

    def _make_package(self, fullname):
        top, username, repo, modname = self._parse_fullname(fullname)
        if repo is not None:
            repo_path = os.path.join(self.base_dir, top, username, repo)
            self._setup_package(repo_path)
        if username is not None:
            user_path = os.path.join(self.base_dir, top, username)
            self._setup_package(user_path)
        if top is not None:
            top_path = os.path.join(self.base_dir, top)
            self._setup_package(top_path)
        if modname is not None:
            try:
                self._install_module(fullname)
            except InstallError:
                if os.path.isfile(self._install_path(fullname)):
                    print('Using existing version: ', fullname)
                else:
                    print('Error installing/updating module: ', fullname)

    def find_module(self, fullname, path=None):
        # print('find_module', fullname, path)
        if fullname.startswith('github'):
            self._make_package(fullname)
        return None

class GitHubBrancher(GitHubImporter):

    def _parse_fullname(self, fullname):
        comps = fullname.split('.')
        top, username, repo, branch, pkg_list = None, None, None, None, None
        if len(comps)>=1:
            top = 'github'
            if len(comps)>=2:
                username = comps[1]
                if len(comps)>=3:
                    repo = comps[2]
                    if len(comps)>=4:
                        branch = comps[3]
                        if len(comps)>=5:
                            pkg_list = comps[4:]
        pathlist = [top, username, repo, branch]
        try:
            pathlist.extend(pkg_list)
            return [d for d in pathlist if d!=None]
        except TypeError:
            return [d for d in pathlist if d!=None]

    def _build_path(self, fullname, url):
        # check if web page exists
        pathlist = self._parse_fullname(fullname)
        if len(pathlist)<4:
            test_url = 'https://github.com/' + '/'.join(pathlist[1:])
        else:
            test_url = 'https://github.com/' + '/'.join(pathlist[1:3]) + '/tree/' + '/'.join(pathlist[3:])
        if urlopen(test_url).code == 404:
            raise HTTPError('error 404: page not found\n' + url)
        else:
            new, resp = urlretrieve(url)
            old = self._install_dirpath(fullname)
            updated = self._update_if_changed(old, new)

    def _build_file(self, fullname, url):
        # check if web page exists
        if urlopen(url).code == 404:
            raise HTTPError()
        else:
            try:
                print('Downloading: ', url)
                tmp_file, resp = urlretrieve(url)
                with open(tmp_file, 'r') as f:
                    new_content = f.read()
                if new_content=='Not Found':
                    raise InstallError('remote file does not exist')
            except IOError:
                raise IOError('remote file does not exist')
            new = tmp_file
            old = self._install_filepath(fullname)
            updated = self._update_if_changed(old, new)
            shutil.rmtree(self._install_dirpath(fullname))
            if updated=='updated':
                print('Updating module: ', fullname)
            elif updated=='installed':
                print('Installing module: ', fullname)
            elif updated=='noaction':
                print('Using existing version: ', fullname)

    def _install_module(self, fullname):
        pathlist = self._parse_fullname(fullname)
        url = 'https://raw.githubusercontent.com/' + '/'.join(pathlist[1:])
        # attempt order implies subpackages and modules cannot
        # have equivalent names if they exist in the same parent
        # directory. if this is so, the subpackage will be
        # ignored and the file loaded.
        try:
            self._build_file(fullname,url+'.py')
        except HTTPError:
            try:
                self._build_path(fullname,url)
            except HTTPError, e:
                raise HTTPError(e)
        except IOError, e:
            raise InstallError('error downloading file')

    def _install_dirpath(self, fullname):
        pathlist = self._parse_fullname(fullname)
        pathlist.insert(0,self.base_dir)
        return os.path.join(*pathlist)

    def _install_filepath(self, fullname):
        pathlist = self._parse_fullname(fullname)
        pathlist.insert(0,self.base_dir)
        pathlist[-1] += '.py'
        return os.path.join(*pathlist)

    def _make_package(self, fullname):
        pathlist = self._parse_fullname(fullname)
        pathlist.insert(0,self.base_dir)
        top_path = os.path.join(*pathlist)
        self._setup_package(top_path)
        if len(pathlist)>=6:
            # if subpackage or module is present attempt install
            try:
                self._install_module(fullname)
            except InstallError:
                if os.path.isfile(self._install_dirpath(fullname)):
                    print('Using existing version: ', fullname)
                else:
                    print('Error installing/updating module: ', fullname)

sys.meta_path.insert(0, GitHubImporter())