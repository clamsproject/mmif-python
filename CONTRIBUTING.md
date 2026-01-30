# Contributing to mmif-python

## CLI Scripts

The `mmif` command-line interface supports subcommands (e.g., `mmif source`, `mmif describe`). These are implemented as Python modules in `mmif/utils/cli/`.

### Adding a New CLI Script

To add a new CLI subcommand, create a Python module in `mmif/utils/cli/` with these three required functions:

1. **`prep_argparser(**kwargs)`** - Define and return an `argparse.ArgumentParser` instance for your subcommand.

2. **`describe_argparser()`** - Return a tuple of two strings:
   - A one-line description (shown in `mmif --help`)
   - A more verbose description (shown in `mmif <subcommand> --help`)

3. **`main(args)`** - Execute the subcommand logic with the parsed arguments.

See existing modules like `summarize.py` or `describe.py` for examples.

### How CLI Discovery Works

The CLI system automatically discovers subcommands at runtime. The entry point is configured in `setup.py`:

```python
entry_points={
    'console_scripts': [
        'mmif = mmif.__init__:cli',
    ],
},
```

The `cli()` function in `mmif/__init__.py` delegates to `prep_argparser_and_subcmds()`, which uses `find_all_modules('mmif.utils.cli')` to locate all modules in the CLI package. For each module found, it:

1. Calls `prep_argparser()` to get the argument parser
2. Calls `describe_argparser()` for help text
3. Registers the module name as a subcommand

This means adding a properly structured module is all that's needed - no modifications to `setup.py` or other configuration files are required.

## Documentation

The documentation for `mmif-python` is built using Sphinx and published to the [CLAMS documentation hub](https://github.com/clamsproject/website-test).

### Building Documentation Locally

To build the documentation for the current checkout:

```bash
make doc
# OR
python3 build-tools/docs.py
```

The output will be in `docs-test` For more options, run `python build-tools/docs.py --help`.

### Building Documentation for Old Versions

To build documentation for a specific historical version (e.g., `v1.0.0`):

```bash
make doc-version
# OR
python3 build-tools/docs.py --build-ver v1.0.0
```

This runs the build in a sandboxed temporary directory. The output will be in `docs-test/<version>`.

### Troubleshooting Old Version Builds

**Important:** The build script (`build-tools/docs.py`) uses a "Modern Environment, Legacy Source" strategy. It checks out the old source code but installs **modern** build dependencies (Sphinx 7.x, Furo) to ensure the build works on current systems (including Python 3.13).

If an old version fails to build because a dependency is missing (e.g., it was removed from `requirements.txt` in later versions but the old `setup.py` needs it), **do not try to fix the old `setup.py`**.

Instead, manually add the missing dependency to the `run_pip` call in `build-tools/docs.py`:

```python
# In build-tools/docs.py
def build_versioned_docs(...):
    # ...
    # Add the missing dependency here
    env.run_pip("install", "jsonschema", "requests", "pyyaml", "deepdiff<7", "YOUR_MISSING_DEP", cwd=source_path)
```

This "overlay" strategy ensures we can build old docs without modifying historical git tags.
