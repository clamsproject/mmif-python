# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import datetime

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
from pathlib import Path
import sys
doc_src_dir = Path(os.getenv("SPHINX_MULTIVERSION_SOURCEDIR", default=__file__))
proj_root_dir = doc_src_dir.parent.parent if doc_src_dir.is_file() else doc_src_dir.parent
sys.path.insert(0, proj_root_dir.as_posix())


# -- Project information -----------------------------------------------------

project = 'mmif-python'
copyright = f'{datetime.date.today().year}, Brandeis LLC'
author = 'Brandeis LLC'
version = open(proj_root_dir / 'VERSION').read().strip()


# The full version, including alpha/beta/rc tags
#  release = '0.1.0'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
        'sphinx.ext.autodoc',
        'sphinx_rtd_theme',
        'sphinx.ext.linkcode',
        'm2r2',
]
try: 
    import sphinx_multiversion
    extensions.append('sphinx_multiversion')
except ImportError:
    pass
source_suffix = ['.rst', '.md']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
# html_theme = 'alabaster'
html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
#  html_static_path = ['_static']

# hide document source view link at the top
html_show_sourcelink = False


# function used by `linkcode` extension
def linkcode_resolve(domain, info):
    if domain != 'py':
        return None
    if not info['module']:
        return None
    filename = info['module'].replace('.', '/')
    # TODO (krim): it's not trivial to recover the file path from a module name
    try:
        return f"https://github.com/clamsproject/mmif-python/tree/{version}/{filename}.py"
    except:
        return f"https://github.com/clamsproject/mmif-python/tree/main/{filename}.py"



# configuration for multiversion extension
# Whitelist pattern for tags (set to None to ignore all tags)
smv_tag_whitelist = r'^[0-9]+\.[0-9]+\.[0-9]+.*$' 
# Whitelist pattern for branches (set to None to ignore all branches)
smv_branch_whitelist = None
# Whitelist pattern for remotes (set to None to use local branches only)
smv_remote_whitelist = 'origin'
# Pattern for released versions
smv_released_pattern = r'^tags/[0-9]+\.[0-9]+\.[0-9]+.*$'
# Format for versioned output directories inside the build directory
smv_outputdir_format = '{ref.name}'
# Determines whether remote or local git branches/tags are preferred if their output dirs conflict
smv_prefer_remote_refs = True

# TODO (krim @ 6/13/21): maybe there's a way to re-write what I wrote in the 
# fork of sphinx-multiversion here in conf.py. Issues I can think of as of now; 
# 1. sphinx-mv/main.py know current version of the library by git tag, 
#    but conf.py has no way to know that... 
# 2. target-versions.csv file can be read once and used in the for loop 
#    in sphinx-mv/main.py, but here it should be read in for each `docs` bulid. 
