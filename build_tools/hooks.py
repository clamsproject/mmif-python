"""
Setuptools build hooks for mmif-python.

This module provides the integration between the build tools and setuptools.
It implements custom command classes that run during the build process to:
- Generate the ver/ package with version info
- Generate the res/ package with MMIF spec resources
- Generate the vocabulary/ package with type enums
"""

import os
from typing import Optional

import yaml

from . import version as version_utils
from . import resources as resource_utils
from . import vocabulary as vocab_utils


def setup_hooks(dist=None) -> None:
    """
    Setuptools entry point hook for build-time code generation.

    This function is called by setuptools via the finalize_distribution_options
    entry point defined in pyproject.toml. It runs before building wheels/sdists.

    Args:
        dist: setuptools Distribution object (optional, provided by setuptools)
    """
    run_build_hooks()


def run_build_hooks(package_version: Optional[str] = None,
                     local_mmif_path: Optional[str] = None) -> None:
    """
    Execute all build hooks to generate required packages.

    This is the main entry point called by setuptools command classes or entry point.

    Args:
        package_version: Package version (if None, will read from VERSION file)
        local_mmif_path: Path to local MMIF repository (if None, will check env var)
    """
    # Get version info
    if package_version is None:
        package_version, spec_version, git_ref = version_utils.get_version_info(
            local_mmif_path=local_mmif_path
        )
    else:
        spec_version = version_utils.get_spec_version_for_build(
            package_version, local_mmif_path
        )
        git_ref = version_utils.get_git_ref_for_resources(
            package_version, spec_version, local_mmif_path
        )

    if local_mmif_path is None:
        local_mmif_path = version_utils.get_local_mmif_path()

    if local_mmif_path:
        print(f"==== Using local MMIF files at '{local_mmif_path}' ====")

    print(f"Building mmif-python {package_version} targeting MMIF spec {spec_version}")
    print(f"Fetching resources from git ref: {git_ref}")

    # Package names
    mmif_package = 'mmif'
    ver_package = 'ver'
    res_package = 'res'
    vocab_package = 'vocabulary'

    # Generate ver/ package
    generate_ver_package(mmif_package, ver_package, package_version, spec_version)

    # Fetch resources
    fetcher = resource_utils.ResourceFetcher(spec_version, git_ref, local_mmif_path)
    resources = fetcher.fetch_all_resources()

    # Generate res/ package
    generate_res_package(mmif_package, res_package, resources)

    # Generate vocabulary/ package
    generate_vocabulary_package(
        mmif_package, vocab_package, spec_version, git_ref,
        resources, local_mmif_path
    )


def generate_ver_package(parent_package: str,
                          subpackage_name: str,
                          package_version: str,
                          spec_version: str) -> None:
    """
    Generate the ver/ package with version information.

    Args:
        parent_package: Parent package name (e.g., "mmif")
        subpackage_name: Subpackage name (e.g., "ver")
        package_version: mmif-python package version
        spec_version: MMIF specification version
    """
    init_contents = f'__version__ = "{package_version}"\n__specver__ = "{spec_version}"\n'

    vocab_utils.create_subpackage(parent_package, subpackage_name, init_contents)
    print(f"Generated {parent_package}/{subpackage_name}/ package")


def generate_res_package(parent_package: str,
                          subpackage_name: str,
                          resources: dict) -> None:
    """
    Generate the res/ package with MMIF spec resources.

    Args:
        parent_package: Parent package name (e.g., "mmif")
        subpackage_name: Subpackage name (e.g., "res")
        resources: Dictionary of resources (schema, vocabulary)
    """
    res_dir = vocab_utils.create_subpackage(parent_package, subpackage_name)

    # Write schema file
    resource_utils.write_resource_file(res_dir, 'mmif.json', resources['schema'])

    # Write vocabulary file
    resource_utils.write_resource_file(
        res_dir, 'clams.vocabulary.yaml', resources['vocabulary']
    )

    print(f"Generated {parent_package}/{subpackage_name}/ package")


def generate_vocabulary_package(parent_package: str,
                                  subpackage_name: str,
                                  spec_version: str,
                                  git_ref: str,
                                  resources: dict,
                                  local_mmif_path: Optional[str]) -> None:
    """
    Generate the vocabulary/ package with type enums.

    Args:
        parent_package: Parent package name (e.g., "mmif")
        subpackage_name: Subpackage name (e.g., "vocabulary")
        spec_version: MMIF specification version
        git_ref: Git ref used for fetching resources
        resources: Dictionary of resources including attypeversions
        local_mmif_path: Path to local MMIF repository (optional)
    """
    attypeversions = resources['attypeversions']
    package_version_is_dev = version_utils.is_dev_version(
        version_utils.read_version_file()
    )

    if package_version_is_dev:
        # For dev versions, we need to handle version increments
        latest_vocab_yaml = resource_utils.fetch_clams_vocabulary(
            spec_version, local_mmif_path
        )
        dev_vocab_yaml = resources['vocabulary']

        type_versions = vocab_utils.determine_type_versions_for_dev(
            latest_vocab_yaml, dev_vocab_yaml, attypeversions
        )
    else:
        # For release versions, use the versions from the spec
        type_versions = attypeversions

    # Generate the vocabulary package
    vocab_utils.generate_vocabulary_package(
        parent_package, spec_version, type_versions
    )

    print(f"Generated {parent_package}/{subpackage_name}/ package")


def create_build_hook_decorator(setuptools_cmd_class):
    """
    Create a decorator that adds build hooks to a setuptools command class.

    This decorator wraps the run() method of a setuptools command class
    to execute our build hooks before the original run() method.

    Args:
        setuptools_cmd_class: A setuptools command class (e.g., sdist, develop)

    Returns:
        The decorated command class with build hooks integrated
    """
    original_run = setuptools_cmd_class.run

    def new_run(self):
        # Run our build hooks
        run_build_hooks()
        # Then run the original command
        original_run(self)

    setuptools_cmd_class.run = new_run
    return setuptools_cmd_class
