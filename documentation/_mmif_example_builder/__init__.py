"""
Sphinx extension: render example MMIF documents from test fixtures.

At ``builder-inited`` time this extension reads the metadata file at
``tests/mmif-examples/examples.json``, renders each listed example
by substituting ``$TypeName_VER`` / ``$VERSION`` template variables in
the corresponding ``raw.json`` against the installed
``clams-vocabulary`` type versions, and writes:

- ``documentation/examples.rst`` — landing page with a toctree
  linking to the individual example pages (gitignored).
- ``documentation/examples/<dir>.rst`` — one page per example
  with title, description, and rendered JSON (gitignored).

All generated files are referenced from ``index.rst`` via the
``examples`` toctree entry.

Falls back to writing an empty ``examples.rst`` if ``clams-vocabulary``
cannot be imported (e.g., when building docs for a historical
mmif-python version that predates the vocabulary migration).
"""
import itertools
import json
import textwrap
from pathlib import Path
from string import Template

from sphinx.util import logging

logger = logging.getLogger(__name__)

_DOCS_DIR = Path(__file__).resolve().parent.parent
_PROJ_ROOT = _DOCS_DIR.parent
_EXAMPLES_DIR = _PROJ_ROOT / 'tests' / 'mmif-examples'
_META_FILE = _EXAMPLES_DIR / 'examples.json'
_OUTPUT_DIR = _DOCS_DIR / 'examples'
_INDEX_PATH = _DOCS_DIR / 'examples.rst'


def _build_attypevers():
    """
    Build the ``{TypeName_VER: vN, VERSION: X.Y.Z}`` substitution dict
    from the installed ``clams-vocabulary`` and the current MMIF spec
    version.

    :raises ImportError: if ``mmif`` or ``clams-vocabulary`` is
        unavailable.
    :returns: substitution dict suitable for ``Template.safe_substitute``
    :rtype: dict
    """
    import mmif
    from mmif.vocabulary import AnnotationTypes, DocumentTypes
    out = {
        f'{k}_VER': v
        for k, v in itertools.chain.from_iterable(
            m._typevers.items()
            for m in [AnnotationTypes, DocumentTypes]
        )
    }
    out['VERSION'] = mmif.__specver__
    return out


def _render_example_page(entry, attypevers):
    """
    Render a single example as a standalone RST page.

    :param entry: one element of ``examples.json``
    :type entry: dict
    :param attypevers: substitution dict from :func:`_build_attypevers`
    :type attypevers: dict
    :returns: RST source for the page, or ``None`` if the fixture is
        missing
    :rtype: str or None
    """
    raw_path = _EXAMPLES_DIR / entry['dir'] / 'raw.json'
    if not raw_path.is_file():
        logger.warning(
            f"Example fixture not found: {raw_path}. Skipping."
        )
        return None
    raw = Template(raw_path.read_text()).safe_substitute(**attypevers)
    title = entry['title']
    underline = '=' * len(title)
    indent = textwrap.indent(raw, '   ')
    return (
        f"{title}\n{underline}\n\n"
        f"{entry['description']}\n\n"
        f".. code-block:: json\n\n{indent}\n"
    )


def _generate_examples(app):
    """
    Sphinx ``builder-inited`` handler. Writes an index page at
    ``documentation/examples.rst`` and one subpage per example under
    ``documentation/examples/``.
    """
    try:
        attypevers = _build_attypevers()
    except ImportError as e:
        logger.warning(
            f"clams-vocabulary or mmif not importable ({e}). "
            f"Writing empty examples.rst."
        )
        _INDEX_PATH.write_text("")
        return

    if not _META_FILE.is_file():
        logger.warning(
            f"Examples metadata not found at {_META_FILE}. "
            f"Writing empty examples.rst."
        )
        _INDEX_PATH.write_text("")
        return

    entries = json.loads(_META_FILE.read_text())
    _OUTPUT_DIR.mkdir(exist_ok=True)

    # Render individual example pages
    toctree_entries = []
    rendered = 0
    for entry in entries:
        page_rst = _render_example_page(entry, attypevers)
        if page_rst is None:
            continue
        page_path = _OUTPUT_DIR / f"{entry['dir']}.rst"
        page_path.write_text(page_rst)
        toctree_entries.append(f"   examples/{entry['dir']}")
        rendered += 1

    # Render index page with toctree
    page_title = "Example MMIF documents"
    index_rst = (
        f"{page_title}\n{'=' * len(page_title)}\n\n"
        ".. toctree::\n"
        "   :maxdepth: 1\n\n"
        + '\n'.join(toctree_entries)
        + '\n'
    )
    _INDEX_PATH.write_text(index_rst)
    logger.info(
        f"Generated examples ({rendered}/{len(entries)} pages)"
    )


def setup(app):
    """
    Sphinx extension entry point.

    :param app: Sphinx application object
    :returns: extension metadata
    :rtype: dict
    """
    app.connect('builder-inited', _generate_examples)
    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
