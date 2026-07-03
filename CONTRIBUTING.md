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
    - When `develop` is ready for a new release, open a PR from `develop` to `main` using the "release" PR template. See the **Releases** section below for the required title format and preparation steps.
    - After merging the release candidate into `main`, manually tag the commit with the version number. This tag triggers the automated CI/CD pipeline for publishing.
6. **Branch Protection**: Both `main` and `develop` are protected branches. Direct pushes are disabled; all changes must be introduced via Pull Requests.

## Releases

Release PRs (from `develop` to `main`) are gated by the `release-check` CI workflow. Before opening one:

1. Title the PR exactly `releasing X.Y.Z` (strict semver); `release-check` reads the version from the title.
2. Run `python build-tools/prep_release.py X.Y.Z` and commit its changes. See inside the prep script to see what's actually prepared.

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

The CLI system automatically discovers subcommands at runtime. The entry point is configured in `pyproject.toml`:

```toml
[project.scripts]
mmif = "mmif:cli"
```

The `cli()` function in `mmif/__init__.py` handles discovery and delegation. It uses `pkgutil.walk_packages` to find all modules within the top-level of the `mmif.utils.cli` package. For the discovery logic to work, a "cli module" should implement the requirements outlined above. 

This means adding a properly structured module within the CLI package is all that's needed—the module name will automatically be registered as a subcommand. No modifications to `pyproject.toml` or other configuration files are required.

> [!NOTE]
> Any "client" code (not shell CLI) wants to use a module in `cli` package should be able to directly `from mmif.utils.cli import a_module`. However, for historical reasons, some CLI modules are manually imported in `mmif/__init__.py` (e.g., `source.py`) for backward compatibility for clients predating the discovery system. 

## Setup

```bash
pip install -e ".[dev]"
```

An editable install (`pip install -e .`) is required before running tests or building docs. The package uses `importlib.metadata` for version resolution at runtime, which only works when the package is registered in the environment. You can no longer run `pytest` or `pytype` directly against the source tree without installing first. If you want to avoid pulling in all dependencies, `pip install -e . --no-deps` is sufficient to register the package metadata.

## Local Development

All build tasks are handled by scripts in `build-tools/`. Each script is self-contained and installs its own dependencies as needed.

| Task | Command |
|------|---------|
| Build (sdist + wheel) | `python build-tools/build.py` |
| Run tests | `python build-tools/test.py` |
| Build docs | `python build-tools/docs.py` |
| Clean artifacts | `python build-tools/clean.py` |
| Publish | `python build-tools/publish.py` |

All scripts support `--help` for full usage details.

### Versioning

#### SDK version 

Versions are derived automatically from git tags via `setuptools-scm`.  There is no `VERSION` file to manage. At runtime, the version is accessed through `importlib.metadata`:

```python
from mmif.ver import __version__
```

For a dev install without a matching tag, `setuptools-scm` generates a version like `1.3.1.dev11+gb83b63ff5.d20260413`.

The MMIF spec version (`__specver__`) is derived at runtime from the `mmif-spec` URL in `pyproject.toml`'s `[project.urls]` section. For example, `mmif-spec = "https://mmif.clams.ai/1.1.0"` produces `__specver__ = "1.1.0"`. Do NOT hardcode this value in Python source — update the URL in `pyproject.toml` instead.

#### MMIF specification version

`mmif/res/mmif.json` is the MMIF JSON Schema, committed as static package data. When the MMIF spec releases a new version:

1. Update the `mmif-spec` URL in `pyproject.toml` `[project.urls]`
1. Re-fetch the schema, using something like:
   ```bash
   curl -sL "https://raw.githubusercontent.com/clamsproject/mmif/main/schema/mmif.json" \
     -o mmif/res/mmif.json
   ```
1. Run tests — `tests/test_specver.py` will fail if either value is stale

## Documentation

The documentation for `mmif-python` is built using Sphinx and published to the [CLAMS documentation hub](https://clams.ai).

### Building Documentation Locally

```bash
python3 build-tools/docs.py
```

The output will be in `docs-test`. For more options, run `python build-tools/docs.py --help`.

> [!NOTE]
> In CI, documentation is built and published automatically by the `publish.yml` workflow via the shared `sdk-docs.yml`. The CI calls `docs.py --build-ver <version> --output-dir _docs`. All CLAMS SDK repos use the same `docs.py` CLI interface (`--build-ver`, `--output-dir`).

> [!NOTE]
> Since the documentation build process is relying on the working `mmif` package, one must "build" the package first (e.g., `python -m pip install -e .`) before building the documentation.

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
python3 build-tools/docs.py --build-ver v1.0.0
```

This runs the build in a sandboxed temporary directory. A single `--build-ver` places the built docs **flat** in the output directory (`docs-test/` by default). The batch `--build-all-since` mode instead nests each version under a `<version>/` subdirectory of the output directory, so multiple versions can coexist. The flat single-version layout is what the CI docs-publish workflow relies on — it invokes `docs.py --build-ver <ver> --output-dir _docs` and uploads `_docs/` as-is, without needing to know whether the project is versioned.

> [!NOTE]
> In CI, documentation is built and published automatically by the `publish.yml` workflow via the shared `sdk-docs.yml`. The CI calls `docs.py --build-ver <version> --output-dir _docs`. All CLAMS SDK repos use the same `docs.py` CLI interface (`--build-ver`, `--output-dir`).

### Troubleshooting Old Version Builds

The build script (`build-tools/docs.py`) uses a "Modern Environment, Legacy Source" strategy. It checks out the old source code but installs modern build dependencies (Sphinx 7.x, Furo) to ensure the build works on up-to-date systems (including Python 3.12+).

If an old version fails to build because a dependency is missing, manually add it to the `run_pip` call in `build-tools/docs.py`:

```python
def build_versioned_docs(...):
    # ...
    env.run_pip("install", ..., "YOUR_MISSING_DEP", cwd=source_path)
```

This "overlay" strategy ensures we can build old docs without modifying historical git tags.

### Example MMIF Documents

Example MMIF documents live in `tests/mmif-examples/` and serve two roles: test fixtures (loaded by `tests/mmif_examples.py`) and documentation source (rendered by the `_mmif_example_builder` Sphinx extension at docs build time). See `tests/mmif-examples/README.md` for details.

## Migration from Makefile

The old `Makefile`, `setup.py`, and `requirements*.txt` files have been
removed. If you are accustomed to the old workflow, here is a mapping:

| Old command | New equivalent |
|-------------|----------------|
| `make package` / `python setup.py sdist` | `python build-tools/build.py` |
| `make develop` / `python setup.py develop` | `pip install -e ".[dev]"` |
| `make test` | `python build-tools/test.py` |
| `make doc` / `make doc-version` | `python build-tools/docs.py` |
| `make version` / `make devversion` | Automatic via `setuptools-scm` (tag-based) |
| `make clean` | `python build-tools/clean.py` |
| `make publish` | `python build-tools/publish.py` |
