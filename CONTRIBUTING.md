# Contributing to mmif-python

## Git Workflow

We follow a Gitflow-inspired branching model to maintain a stable `main` branch and a dynamic `develop` branch.

1. **Branch Roles**:
    - `main`: Reserved for stable, production-ready releases.
    - `develop`: The primary branch for ongoing development, feature integration, and bug fixes. This serves as the "staging" area for the next release.
2. **Issue Tracking**: Every contribution (bug fix or feature) must first be reported as a [GitHub Issue](https://github.com/clamsproject/mmif-python/issues). Issues should clearly define goals and, preferably, include an implementation plan.
3. **Branch Naming**: Create a dedicated working branch for each issue. Branches must be named using the format `NUM-short-description`, where `NUM` is the issue number (e.g., `113-fix-file-loading`).
4. **Pull Requests (PRs)**:
    - Once work is complete, open a PR targeting the `develop` branch.
    - **Communication**: High-level discussion and planning should occur in the issue thread. The PR conversation is strictly for code review and implementation-specific feedback.
5. **Releases**:
    - When `develop` is ready for a new release, open a PR from `develop` to `main` using the "release" PR template.
    - After merging the release candidate into `main`, manually tag the commit with the version number. This tag triggers the automated CI/CD pipeline for publishing.
6. **Branch Protection**: Both `main` and `develop` are protected branches. Direct pushes are disabled; all changes must be introduced via Pull Requests.

## CLI Scripts

The `mmif` command-line interface supports subcommands (e.g., `mmif source`, `mmif describe`). These are implemented as Python modules in `mmif/utils/cli/`.

### Adding a New CLI Script

To add a new CLI subcommand, create a Python module in `mmif/utils/cli/` with these three required functions:

1. **`prep_argparser(**kwargs)`** - Define and return an `argparse.ArgumentParser` instance for your subcommand. When called during discovery, the main CLI will pass `add_help=False` to this function to avoid duplicate help flags.

2. **`describe_argparser()`** - Return a tuple of two strings:
   - A one-line description (shown in `mmif --help`)
   - A more verbose description (shown in `mmif <subcommand> --help`)

3. **`main(args)`** - Execute the subcommand logic with the parsed arguments.

### Standard I/O Argument Pattern

To ensure a consistent user experience and avoid resource leaks, all CLI subcommands should adhere to the following I/O argument patterns using the `mmif.utils.cli.open_cli_io_arg` context manager (which replaces the deprecated `argparse.FileType`):

1. **Input**: Use a positional argument (usually named `MMIF_FILE`) that supports both file paths and STDIN. 
   - In `prep_argparser`, use `nargs='?'`, `type=str`, and `default=None`.
   - In `main`, use `with open_cli_io_arg(args.MMIF_FILE, 'r', default_stdin=True) as input_file:`.
2. **Output**: Use the `-o`/`--output` flag for the output destination.
   - In `prep_argparser`, use `type=str` and `default=None`.
   - In `main`, use `with open_cli_io_arg(args.output, 'w', default_stdin=True) as output_file:`.
3. **Formatting**: Use the `-p`/`--pretty` flag as a boolean switch (`action='store_true'`) to toggle between compact and pretty-printed JSON/MMIF output.

[!NOTE]
> CLI modules should typically act as thin wrappers. It is recommended to implement the core utility logic in other packages (e.g., `mmif.utils`) and import it into the CLI module. See existing modules like `summarize.py` (which imports from `mmif.utils.summarizer`) or `describe.py` for examples.

### How CLI Discovery Works

The CLI system automatically discovers subcommands at runtime. The entry point is configured in the build script (currently `setup.py`) as follows:

```python
entry_points={
    'console_scripts': [
        'mmif = mmif.__init__:cli',
    ],
},
```

The `cli()` function in `mmif/__init__.py` handles discovery and delegation. It uses `pkgutil.walk_packages` to find all modules within the top-level of the `mmif.utils.cli` package. For the discovery logic to work, a "cli module" should implement the requirements outlined above. 

This means adding a properly structured module within the CLI package is all that's needed—the module name will automatically be registered as a subcommand. No modifications to `setup.py` or other configuration files are required.

> [!NOTE]
> Any "client" code (not shell CLI) wants to use a module in `cli` package should be able to directrly `from mmif.utils.cli import a_module`. However, for historical reasons, some CLI modules are manually imported in `mmif/__init__.py` (e.g., `source.py`) for backward compatibility for clients predateing the discovery system. 

## Documentation

The documentation for `mmif-python` is built using Sphinx and published to the [CLAMS documentation hub](https://github.com/clamsproject/website-test).

### Building Documentation Locally

To build the documentation for the current checkout:

```bash
python3 build-tools/docs.py
```

The output will be in `docs-test`. For more options, run `python build-tools/docs.py --help`.

### API Documentation (autodoc)

As of 2026 (since the next version of 1.2.1), API documentation is **automatically generated** using `sphinx-apidoc`. When you run the documentation build:

1. The `run_apidoc()` function in `documentation/conf.py` runs automatically
2. It scans packages listed in `apidoc_package_names` (currently `mmif` and `mmif_docloc_http`)
3. RST files are generated in `documentation/autodoc/`
4. These files are **not tracked in git** - they're regenerated on each build

**When you add a new module or subpackage**, it will be automatically documented on the next build. No manual updates required.

**To add a new top-level package** (like `mmif_docloc_http`), add it to `apidoc_package_names` in `documentation/conf.py`.

**To exclude a subpackage** from documentation (like `mmif.res` or `mmif.ver`), add it to `apidoc_exclude_paths`.

**Module docstrings** in `__init__.py` files are used as package descriptions in the documentation. Keep them concise and informative.

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
