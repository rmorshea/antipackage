AntiPackage
===========

Automagically import single file Python modules from GitHub.

## Installation

The `antipackage` package can be installed from GitHub using `pip`:

```
pip install git+https://github.com/ellisonbg/antipackage.git#egg=antipackage
```

## Usage

Enable `antipackage` by simply importing it:

```python
import antipackage as apkg
```

Once `antipackage` has been imported you can simply import modules from GitHub using the syntax:

```python
from github.username.repo import module
```

Additionally if you need to access a branch other than master, or want to install a module
located in subpackes inside the GitHub repository, use the following command and import syntx:

```python
apkg.assume_brancher()
from github.username.repo.branch.subpackages import module
```

When you do this, the import hook will automatically download and install single file
Python modules into the location `~/.antipackage/github/username/repo/testing/subpackages/module.py`.
If the module ever changes on GitHub it will be updated next time you import it.

## Absolute imports

The `antipackage` package is written looking forward to the days when Python 2 is no longer
supported. Because of this, the import hooks used in `antipackage` assume that relative imports
are not used in the single file modules that are being imported. To enable this behavior for Python 2,
add the following line at the top of your modules:

```python
from __future__ import absolute_import
```

Like this: https://github.com/ellisonbg/misc/blob/master/vizarray.py#L26
