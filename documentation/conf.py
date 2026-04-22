# Configuration file for the Sphinx documentation builder.
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import datetime
import inspect
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from sphinx.util import logging

logger = logging.getLogger(__name__)

# -- Path setup --------------------------------------------------------------
# Add project root to sys.path so that autodoc can find the mmif package.
proj_root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(proj_root_dir.absolute()))
# Add the local Sphinx extensions directory so '_mmif_example_builder'
# can be imported by name from the ``extensions`` list below.
sys.path.insert(0, str(Path(__file__).parent.absolute()))

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
    from importlib.metadata import version as _get_version
    version = _get_version('mmif-python')
except Exception:
    logger.warning("Could not read package version, using 'dev'.")
    version = 'dev'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.linkcode',
    'm2r2',
    'sphinxcontrib.autodoc_pydantic',
    '_mmif_example_builder',
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
    # Skip dev/dummy versions to avoid dirtying the git-tracked CSV
    if 'dev' in current_ver or not re.match(r'^\d+\.\d+\.\d+$', current_ver):
        return
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
    Generate whatsnew.md by fetching the latest release PR body
    from GitHub via ``gh pr list``.

    Falls back gracefully if ``gh`` is unavailable (local builds).
    """
    output_path = proj_root_dir / 'documentation' / 'whatsnew.md'
    repo = f'clamsproject/{project}'

    try:
        result = subprocess.run(
            ['gh', 'pr', 'list',
             '-s', 'merged', '-B', 'main',
             '-L', '100',
             '--json', 'title,body',
             '--repo', repo],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        prs = json.loads(result.stdout)
        pr = next(
            (p for p in prs
             if p['title'].startswith('releasing ')),
            None,
        )
        if pr is None:
            raise RuntimeError("No release PR found")
        title = pr['title']
        body = pr.get('body', '')

        with open(output_path, 'w') as f:
            f.write(f"## {title}\n\n")
            f.write(f"(Full changelog: "
                    f"[CHANGELOG.md]"
                    f"({blob_base_url}/main/CHANGELOG.md))\n\n")
            if body:
                f.write(body)
        logger.info(f"Generated whatsnew.md from PR: {title}")

    except Exception as e:
        logger.warning(
            f"Could not fetch release notes via gh: {e}. "
            f"Writing empty whatsnew.md"
        )
        with open(output_path, 'w') as f:
            f.write("")


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
