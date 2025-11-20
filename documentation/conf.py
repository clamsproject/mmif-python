# Configuration file for the Sphinx documentation builder.
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import datetime
import inspect
import os
import sys
from pathlib import Path

# -- Path setup --------------------------------------------------------------
# Add project root to sys.path so that autodoc can find the mmif package.
proj_root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(proj_root_dir.absolute()))

# At this point, `pip install -e .` should have been run, so mmif is importable
import mmif

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'mmif-python'
copyright = f'{datetime.date.today().year}, Brandeis LLC'
author = 'Brandeis LLC'
try:
    version = open(proj_root_dir / 'VERSION').read().strip()
except FileNotFoundError:
    print("WARNING: VERSION file not found, using 'dev' as version.")
    version = 'dev'
release = version


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.linkcode',
    'furo',
    'm2r2',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
source_suffix = ['.rst', '.md']


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = [] # No static path for now, can be created if needed
html_show_sourcelink = True # Furo handles this well, no need to hide

# Theme options for visual consistency with CLAMS branding
html_theme_options = {
    # "light_logo": "logo.png", # TODO: Add logo files if available
    # "dark_logo": "logo.png",
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    "source_repository": "https://github.com/clamsproject/mmif-python",
    "source_branch": "main", # Default branch for "Edit on GitHub" links
    "source_directory": "documentation/",

    # CLAMS brand colors
    "light_css_variables": {
        "color-brand-primary": "#008AFF",
        "color-brand-content": "#0085A1",
        "color-link": "#008AFF",
        "color-link-hover": "#0085A1",
    },
    # Dark mode variables can be added here if needed
}


# -- Options for linkcode extension ---------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/linkcode.html

def linkcode_resolve(domain, info):
    if domain != 'py' or not info.get('module'):
        return None

    try:
        # Find the Python object
        obj = sys.modules.get(info['module'])
        if obj is None: return None
        for part in info['fullname'].split('.'):
            obj = getattr(obj, part)
        
        # Get the source file and line numbers
        # Use inspect.unwrap to handle decorated objects
        unwrapped_obj = inspect.unwrap(obj)
        filename = inspect.getsourcefile(unwrapped_obj)
        if not filename: return None
        
        lines, start_lineno = inspect.getsourcelines(unwrapped_obj)
        end_lineno = start_lineno + len(lines) - 1
        
        # Get git ref (tag or branch)
        # GITHUB_REF_NAME is set by GitHub Actions (e.g., 'main', 'v1.2.0')
        git_ref = os.environ.get("GITHUB_REF_NAME") or version
        if not git_ref or 'dev' in git_ref:
            git_ref = 'main' # Fallback for local builds or dev versions

        # Get file path relative to repository root
        repo_root = Path(__file__).parent.parent
        rel_path = Path(filename).relative_to(repo_root)

        return f"https://github.com/clamsproject/mmif-python/blob/{git_ref}/{rel_path}#L{start_lineno}-L{end_lineno}"
    
    except Exception:
        # Don't fail the entire build if one link fails, just return None
        return None