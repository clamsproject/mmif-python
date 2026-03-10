# Configuration file for the Sphinx documentation builder.
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import datetime
import inspect
import textwrap
import os
import re
import sys
from pathlib import Path
from sphinx.util import logging

logger = logging.getLogger(__name__)

# -- Path setup --------------------------------------------------------------
# Add project root to sys.path so that autodoc can find the mmif package.
proj_root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(proj_root_dir.absolute()))

# At this point, `pip install -e .` should have been run, so mmif is importable
import mmif

# apidoc settings
apidoc_package_names = ['mmif', 'mmif_docloc_http']
apidoc_exclude_paths = [
    proj_root_dir / 'mmif' / 'res',
    proj_root_dir / 'mmif' / 'ver',
]
# this is used by sphinx.ext.autodoc
autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'show-inheritance': True,
}
autodoc_member_order = 'bysource'


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'mmif-python'
blob_base_url = f'https://github.com/clamsproject/{project}/blob'
author = 'Brandeis LLC'
copyright = f'{datetime.date.today().year}, {author}'
try:
    version = open(proj_root_dir / 'VERSION').read().strip()
except FileNotFoundError:
    logger.warning("VERSION file not found, using 'dev' as version.")
    version = 'dev'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.linkcode',
    'm2r2',
    'sphinxcontrib.autodoc_pydantic',
]

autodoc_pydantic_model_show_json = True
autodoc_pydantic_model_show_field_summary = True
autodoc_pydantic_model_show_config_summary = False
autodoc_pydantic_model_show_validator_members = False
autodoc_pydantic_model_show_validator_summary = False
autodoc_pydantic_field_list_validators = False

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
# dynamically generated files
exclude_patterns.extend(['cli_help.rst', 'whatsnew.md'])
# WIP files
exclude_patterns.extend(['consumer-tutorial.rst'])
source_suffix = ['.rst', '.md']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = []  # No static path for now, can be created if needed
html_show_sourcelink = True  # Furo handles this well, no need to hide

# Theme options for visual consistency with CLAMS branding
html_theme_options = {
    # "light_logo": "logo.png", # TODO: Add logo files if available
    # "dark_logo": "logo.png",
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    "source_repository": "https://github.com/clamsproject/mmif-python",
    "source_branch": "main",  # Default branch for "Edit on GitHub" links
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
            git_ref = 'main'  # Fallback for local builds or dev versions

        # Get file path relative to repository root
        repo_root = Path(__file__).parent.parent
        rel_path = Path(filename).relative_to(repo_root)

        return f"{blob_base_url}/{git_ref}/{rel_path}#L{start_lineno}-L{end_lineno}"

    except Exception:
        # Don't fail the entire build if one link fails, just return None
        return None


def update_target_versions(app):
    """
    Update documentation/target-versions.csv with the current version and spec version.
    This replaces the old logic in setup.py.
    """
    # Check if we have __specver__ (it might not be there if not installed via setup.py develop)
    if not hasattr(mmif, '__specver__'):
        return

    current_ver = mmif.__version__
    spec_ver = mmif.__specver__

    csv_path = proj_root_dir / 'documentation' / 'target-versions.csv'
    if not csv_path.exists():
        return

    # Read existing content
    with open(csv_path, 'r') as f:
        lines = f.readlines()

    # Check if current version is already in the file (first data line)
    # lines[0] is header, lines[1] is latest version
    if len(lines) > 1 and lines[1].startswith(f'{current_ver},'):
        return

    # Insert new version
    logger.info(f"Updating target-versions.csv: {current_ver} -> {spec_ver}")
    lines.insert(1, f'{current_ver},"{spec_ver}"\n')

    with open(csv_path, 'w') as f:
        f.writelines(lines)


def generate_cli_rst(app):
    from mmif import prep_argparser_and_subcmds

    # Generate main help
    os.environ['COLUMNS'] = '100'
    parser, _, _ = prep_argparser_and_subcmds()
    help_text = parser.format_help()

    content = []

    content.append('.. code-block:: text\n\n')
    content.append('    $ mmif --help\n')
    content.append(textwrap.indent(help_text, '    '))
    content.append('\n\n')

    # No longer generate subcommand help

    with open(proj_root_dir / 'documentation' / 'cli_help.rst', 'w') as f:
        f.write(''.join(content))


def generate_whatsnew_rst(app):
    """
    Create the documentation/whatsnew.md file by pulling out the changes for the
    current version from the changelog file.
    """

    changelog_path = proj_root_dir / 'CHANGELOG.md'
    output_path = proj_root_dir / 'documentation' / 'whatsnew.md'
    if not changelog_path.exists():
        logger.warning(f"CHANGELOG.md not found at {changelog_path}")
        with open(output_path, 'w') as f:
            f.write("")
        return

    content = []
    found_version = False
    version_header_re = re.compile(r'^## releasing\s+([^\s]+)\s*(\(.*\))?')

    logger.debug(f"Looking for version '{version}' in CHANGELOG.md")

    with open(changelog_path, 'r') as f:
        lines = f.readlines()

    for line in lines:
        match = version_header_re.match(line)
        if match:
            header_version = match.group(1)
            if header_version == version:
                found_version = True
                # We don't include the header line itself in the content we want to wrap
                continue
            elif found_version:
                break

        if found_version:
            content.append(line)

    if not found_version:
        logger.info(f"No changelog entry found for version {version}")
        with open(output_path, 'w') as f:
            f.write(f"### nothing new in {version}\nDid you locally build for testing?")
    else:
        # Dump matched markdown content directly to whatsnew.md
        with open(output_path, 'w') as f:
            f.write(f"## What's New in {version}\n\n(Full changelog available in the [CHANGELOG.md]({blob_base_url}/main/CHANGELOG.md))\n")
            f.writelines(content)


def run_apidoc(app):
    """
    Run sphinx-apidoc to auto-generate RST files for all modules.
    This ensures new modules are automatically documented without manual updates.
    """
    from sphinx.ext.apidoc import main as apidoc_main

    docs_dir = Path(__file__).parent
    output_dir = docs_dir / 'autodoc'

    exclude_paths = map(str, apidoc_exclude_paths)

    # Run sphinx-apidoc for each package specified in package_names
    # apidoc_main() accepts argv-style arguments (without the program name)
    for package_name in apidoc_package_names:
        package_dir = proj_root_dir / package_name
        if not package_dir.exists():
            logger.warning(f"Package directory {package_dir} does not exist. "
                           f"Skipping apidoc for {package_name}.")
            continue

        args = [
            '-o', str(output_dir),
            str(package_dir),
            *exclude_paths,
            '--force',          # Overwrite existing files
            '--module-first',   # Put module docs before submodule docs
            '--no-toc',         # Don't create modules.rst, will be overwriting each other's
        ]
        logger.info(f"Running sphinx-apidoc with args: {args}")
        apidoc_main(args)


def setup(app):
    try:
        app.connect('builder-inited', run_apidoc)
        app.connect('builder-inited', update_target_versions)
        app.connect('builder-inited', generate_cli_rst)
        app.connect('builder-inited', generate_whatsnew_rst)
    except ImportError:
        logger.warning("'mmif' package not found. Skipping dynamic generation of parts of documentation.")
