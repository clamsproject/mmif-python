"""
Version management for mmif-python package.

This module handles:
- Reading and validating the VERSION file
- Inferring the target MMIF specification version from git tags
- Supporting both remote (GitHub) and local MMIF repositories
"""

import json
import os
import re
import subprocess
from typing import Tuple, Optional
from urllib import request


def read_version_file(version_file: str = "VERSION") -> str:
    """
    Read the VERSION file and return the version string.

    Args:
        version_file: Path to the VERSION file (default: "VERSION")

    Returns:
        Version string (e.g., "1.0.0" or "1.0.0.dev1")

    Raises:
        FileNotFoundError: If VERSION file doesn't exist
        ValueError: If VERSION file is empty or contains invalid format
    """
    if not os.path.exists(version_file):
        raise FileNotFoundError(
            f"Cannot find {version_file} file. "
            f"Use `python scripts/manage_version.py` to generate one."
        )

    with open(version_file, 'r') as f:
        version = f.read().strip()

    if not version:
        raise ValueError(f"{version_file} is empty")

    # Validate version format: X.Y.Z or X.Y.Z.devN
    if not re.match(r'^\d+\.\d+\.\d+(?:\.dev\d+)?$', version):
        raise ValueError(
            f"Invalid version format in {version_file}: {version}. "
            f"Expected format: X.Y.Z or X.Y.Z.devN"
        )

    return version


def is_dev_version(version: str) -> bool:
    """Check if a version string represents a development version."""
    return '.dev' in version


def get_local_mmif_path() -> Optional[str]:
    """
    Get the local MMIF repository path from LOCALMMIF environment variable.

    Returns:
        Path to local MMIF repository, or None if not set
    """
    return os.environ.get('LOCALMMIF')


def get_latest_mmif_git_tag(local_mmif_path: Optional[str] = None) -> str:
    """
    Get the latest MMIF specification git tag.

    This function retrieves the latest version tag from the MMIF specification
    repository. It supports both local git repositories and remote GitHub queries.

    Args:
        local_mmif_path: Path to local MMIF git repository (optional).
                        If not provided, will check LOCALMMIF environment variable.
                        If neither is available, fetches from GitHub.

    Returns:
        Latest MMIF specification version tag (e.g., "1.0.0")

    Raises:
        RuntimeError: If no valid version tags are found
    """
    if local_mmif_path is None:
        local_mmif_path = get_local_mmif_path()

    if local_mmif_path is not None:
        # Get tags from local git repository
        result = subprocess.run(
            ['git', '--git-dir', f'{local_mmif_path}/.git', '--no-pager', 'tag'],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to get git tags from local MMIF repo at {local_mmif_path}: "
                f"{result.stderr}"
            )
        tags = result.stdout.split('\n')
    else:
        # Fetch tags from GitHub API
        tags = []
        page = 1
        while True:
            url = f'https://api.github.com/repos/clamsproject/mmif/tags?per_page=100&page={page}'
            try:
                res = request.urlopen(url)
                body = json.loads(res.read())
            except Exception as e:
                raise RuntimeError(f"Failed to fetch tags from GitHub: {e}")

            if not body:
                break

            tags.extend([tag['name'] for tag in body])
            page += 1

    # Filter for version tags matching X.Y.Z format
    # Note: Some legacy tags had prefixes like "spec-X.Y.Z" or "vocab-X.Y.Z"
    version_pattern = re.compile(r'(?:spec-|vocab-)?(\d+\.\d+\.\d+)$')
    valid_tags = []
    for tag in tags:
        match = version_pattern.match(tag.strip())
        if match:
            # Extract just the version part (without prefix)
            valid_tags.append(match.group(1))

    if not valid_tags:
        raise RuntimeError("No valid MMIF specification version tags found")

    # Sort by version numbers and return the highest
    def version_key(v):
        return tuple(map(int, v.split('.')))

    return sorted(valid_tags, key=version_key)[-1]


def get_spec_version_for_build(package_version: str,
                                 local_mmif_path: Optional[str] = None) -> str:
    """
    Determine which MMIF specification version to use for a build.

    Args:
        package_version: The mmif-python package version being built
        local_mmif_path: Path to local MMIF repository (optional)

    Returns:
        MMIF specification version string (e.g., "1.0.0")
    """
    latest_tag = get_latest_mmif_git_tag(local_mmif_path)

    # For release versions, use the latest stable tag
    # For dev versions, we still reference the latest tag for base types
    # (the actual vocabulary may come from develop branch)
    return latest_tag


def get_git_ref_for_resources(package_version: str,
                                latest_spec_tag: str,
                                local_mmif_path: Optional[str] = None) -> str:
    """
    Determine which git ref to use when fetching MMIF spec resources.

    For release versions: use the latest stable tag
    For dev versions: use 'develop' branch

    Args:
        package_version: The mmif-python package version being built
        latest_spec_tag: The latest MMIF spec tag
        local_mmif_path: Path to local MMIF repository (optional)

    Returns:
        Git ref string (tag name or branch name)
    """
    if is_dev_version(package_version):
        return 'develop'
    else:
        return latest_spec_tag


def get_version_info(version_file: str = "VERSION",
                      local_mmif_path: Optional[str] = None) -> Tuple[str, str, str]:
    """
    Get complete version information for a build.

    This is the main entry point for build scripts to get all version info.

    Args:
        version_file: Path to the VERSION file
        local_mmif_path: Path to local MMIF repository (optional)

    Returns:
        Tuple of (package_version, spec_version, git_ref_for_resources)

    Example:
        >>> package_ver, spec_ver, git_ref = get_version_info()
        >>> print(f"Building mmif-python {package_ver} targeting MMIF spec {spec_ver}")
    """
    package_version = read_version_file(version_file)
    spec_version = get_spec_version_for_build(package_version, local_mmif_path)
    git_ref = get_git_ref_for_resources(package_version, spec_version, local_mmif_path)

    return package_version, spec_version, git_ref
