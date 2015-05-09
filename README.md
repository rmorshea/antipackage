AntiPackage
===========

Automagically import lightweight Python packages from GitHub.

## Installation

`antipackage` can be installed from GitHub using `pip`:

```
pip install git+https://github.com/rmorshea/antipackage.git#egg=antipackage
```

## Basic Usage

Enable `antipackage` by simply importing it:

```python
import antipackage as apkg
```

Once `antipackage` has been imported you can simply import modules from GitHub using the syntax:

```python
from github.username.repo import module
```

When you do this, the import hook will automatically download and install the whole GitHub repository
into the location `~/.antipackage/github/username/repo`. Thus antipackage can support modules with
relatively lightweight dependancies. If the repository ever changes on GitHub it will be updated the
next time you import it.

## Pinning

The alternate way to import with antipackage is with pins. Pinning allows for a repo to be retrieved
from a particular branch, tag, or commit during all future imports. By default antipackage will tag a
repo with a branch pin to 'master'. Marking a repo with a branch pin will cause antipackage to pull
from the most recent version found on that branch. However marking a repo with a sha or tag pin will
force antipackage to draw on the version of the repository which corrisponds to that particular commit.

To enable this functionality, use `pin` in `pinning` by giving a path along with a pin type and value:

```python
apkg.pin('github/username/repo', sha='0158d2c0824e7162c1721174cb967d9efbfbbdb0')
```

Similarly, you access pinning data using `data` in `pinning` by giving a path to the information you need.
Thus paths can also retrieve specific data attributes by extending the it into the pin itself:

```python
# returns all pinning data
apkg.data()
```

or 

```python
# the path to 'sha' holds the sha string
# the repo is currently associated with
apkg.data('github/username/repo/commit/sha')

# the path to 'url' holds the url which
# the sha string was sourced from
apkg.data('github/username/repo/commit/url')

# the 'branch' and 'tag' paths hold the
# branch or tag name respectively if
# that's what the repo is associate with
apkg.data('github/username/repo/tag')
apkg.data('github/username/repo/branch')
```

##Import Replacements
The method `import_replacement` allows for substitutions in import statements. This resolves an issue
where one might want to download a repository whose name includes a reserved character. For example,
the following import statement is invalid due to the inclusion of the "-" character:

```python
import github.jdfreder.ipython-d3networkx
```

To get around this problem we make an import replacement along with a revised import statement:

```python
apkg.import_replacement('ipython_d3networkx','ipython-d3networkx')
import github.jdfreder.ipython_d3networkx
```

The method `import_replacement` substitutes the value, `'ipython-d3networkx'`, in for **all** instance
of the key, `'ipython_d3networkx'`, in subsiquent import statements until the rule is removed by calling:

```python
apkg.import_replacement('ipython_d3networkx', remove=True)
```

Thus import statements which would normally require reserved characters can be made valid while
still pointing to the intended repository. It should be noted that the sweeping application of the
method means specific replacements should be made a habbit.

##Absolute Imports
`antipackage` is written looking forward to the days when Python 2 is no longer
supported. Because of this, the import hooks used in `antipackage` assume that relative imports are not
used in the single file modules that are being imported. To enable this behavior for Python 2, add the
following line at the top of your modules:

```python
from __future__ import absolute_import
```

Like this: https://github.com/ellisonbg/misc/blob/master/vizarray.py#L26
