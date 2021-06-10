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
import sys
rootdir = os.getenv("SPHINX_MULTIVERSION_SOURCEDIR", default=os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(rootdir))


# -- Project information -----------------------------------------------------

project = 'mmif-python'
copyright = f'{datetime.date.today().year}, Brandeis LLC'
author = 'Brandeis LLC'

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
        "sphinx_multiversion"
]
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
    return f"https://github.com/clamsproject/mmif-python/tree/{version}/{filename}.py"


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
