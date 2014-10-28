from __future__ import print_function
import os
import sys
from urllib import urlretrieve

class GitHubImporter(object):
    def __init__(self):
        self.base_dir = os.path.expanduser('~/.antipackage')
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
        sys.path.append(self.base_dir)

    def _parse_fullname(self, fullname):
        comps = fullname.split('.')
        top, username, repo, filename = None, None, None, None
        if len(comps)>=1:
            top = 'github'
        if len(comps)>=2:
            username = comps[1]
        if len(comps)>=3:
            repo = comps[2]
        if len(comps)>=4:
            filename = comps[3]
        return top, username, repo, filename
        
    def _install_init(self, path):
            ipath = os.path.join(path, '__init__.py')
            # print('Installing: ', ipath)
            self._touch(ipath)

    def _install_filename(self, username, repo, filename, path):
        url = 'https://raw.githubusercontent.com/%s/%s/master/%s' % (username, repo, filename)
        # print('Downloading: ', url)
        urlretrieve(url, os.path.join(path, filename))
    
    def _setup_package(self, path):
        if not os.path.exists(path):
            os.makedirs(path)
        self._install_init(path)
    
    def _make_package(self, fullname):
        pkgs = fullname.split('.')
        top, username, repo, filename = self._parse_fullname(fullname)
        if repo is not None:
            repo_path = os.path.join(self.base_dir, top, username, repo)
            self._setup_package(repo_path)
        if username is not None:
            user_path = os.path.join(self.base_dir, top, username)
            self._setup_package(user_path)
        if top is not None:
            top_path = os.path.join(self.base_dir, top)
            self._setup_package(top_path)
        if filename is not None:
            self._install_filename(username, repo, filename+'.py', repo_path)
            
    def _touch(self, path):
        with open(path, 'a'):
            os.utime(path, None)
                
    def find_module(self, fullname, path=None):
        # print('find_module', fullname, path)
        if fullname.startswith('github'):
            self._make_package(fullname)
        return None

sys.meta_path = [GitHubImporter()]