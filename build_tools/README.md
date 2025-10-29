# build_tools

This directory contains library modules for the mmif-python build system. These modules are **not meant to be run directly** by developers.

## Architecture

The `build_tools/` package provides core functionality that is used in two ways:

1. **During package builds** - Automatically invoked by setuptools via the entry point defined in `pyproject.toml`
2. **By CLI wrapper scripts** - Called by user-facing scripts in the `scripts/` directory


## For Developers

**DO NOT run these modules directly.** Instead, use the CLI wrapper scripts in the `scripts/` directory:

```bash
# Version management
python scripts/manage_version.py              # Interactive version setting
python scripts/manage_version.py --dev        # Generate dev version
python scripts/manage_version.py --set 1.0.0  # Set specific version

# Documentation
python scripts/build_docs.py                  # Build single-version docs
python scripts/build_docs.py --multi          # Build multi-version docs

# Cleanup
python scripts/clean.py                       # Clean all build artifacts
python scripts/clean.py --dist-only           # Clean only distribution files
```

## For Package Builds

The `hooks.py` module is automatically invoked by setuptools when building the package:

```bash
# These commands automatically trigger build_tools.hooks:setup_hooks()
pip install -e .                              # Development install
python -m build                               # Build wheel and sdist
```

The entry point is configured in `pyproject.toml`:

```toml
[project.entry-points."setuptools.finalize_distribution_options"]
build_hooks = "build_tools.hooks:setup_hooks"
```
