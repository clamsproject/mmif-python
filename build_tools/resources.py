"""
Resource fetching for MMIF specification files.

This module handles fetching MMIF specification resources from either:
- Remote GitHub repository (default)
- Local MMIF git repository (via LOCALMMIF environment variable)

Resources include:
- JSON schema files
- YAML vocabulary files
- Annotation type version mappings
"""

import json
import os
import subprocess
from typing import Union, Optional
from urllib import request


def get_spec_file_at_gitref(git_ref: str,
                              filepath: str,
                              local_mmif_path: Optional[str] = None) -> bytes:
    """
    Fetch a file from the MMIF specification repository at a specific git ref.

    Args:
        git_ref: Git tag or branch name (e.g., "1.0.0" or "develop")
        filepath: Path to the file within the repository
                 May contain {version} placeholder (e.g., "docs/{version}/vocabulary/...")
        local_mmif_path: Path to local MMIF repository (optional)

    Returns:
        File contents as bytes

    Raises:
        RuntimeError: If file cannot be fetched from local or remote repository
    """
    # Substitute version placeholder if present
    filepath = filepath.format(version=git_ref)

    if local_mmif_path is not None:
        # Fetch from local git repository
        result = subprocess.run(
            ['git', '--git-dir', f'{local_mmif_path}/.git', '--no-pager',
             'show', f'{git_ref}:{filepath}'],
            capture_output=True
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to get {filepath} at {git_ref} from local MMIF repo: "
                f"{result.stderr.decode('utf-8')}"
            )
        return result.stdout
    else:
        # Fetch from GitHub
        file_url = f"https://raw.githubusercontent.com/clamsproject/mmif/{git_ref}/{filepath}"
        try:
            return request.urlopen(file_url).read()
        except Exception as e:
            raise RuntimeError(f"Failed to fetch {file_url}: {e}")


def write_resource_file(resource_dir: str,
                         resource_name: str,
                         resource_data: Union[bytes, str]) -> None:
    """
    Write a resource file to disk.

    Args:
        resource_dir: Directory to write the file to
        resource_name: Name of the file to write
        resource_data: File contents (bytes or string)
    """
    os.makedirs(resource_dir, exist_ok=True)

    mode = 'wb' if isinstance(resource_data, bytes) else 'w'
    filepath = os.path.join(resource_dir, resource_name)

    with open(filepath, mode) as f:
        f.write(resource_data)


def fetch_mmif_schema(git_ref: str,
                       local_mmif_path: Optional[str] = None) -> bytes:
    """
    Fetch the MMIF JSON schema file.

    Args:
        git_ref: Git tag or branch to fetch from
        local_mmif_path: Path to local MMIF repository (optional)

    Returns:
        JSON schema as bytes
    """
    schema_path = 'schema/mmif.json'
    return get_spec_file_at_gitref(git_ref, schema_path, local_mmif_path)


def fetch_clams_vocabulary(git_ref: str,
                             local_mmif_path: Optional[str] = None) -> bytes:
    """
    Fetch the CLAMS vocabulary YAML file.

    Args:
        git_ref: Git tag or branch to fetch from
        local_mmif_path: Path to local MMIF repository (optional)

    Returns:
        Vocabulary YAML as bytes
    """
    vocab_path = 'vocabulary/clams.vocabulary.yaml'

    if local_mmif_path is not None:
        # For local repos, read directly from filesystem
        filepath = os.path.join(local_mmif_path, vocab_path)
        if git_ref == 'develop' and os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                return f.read()

    # Otherwise fetch from git
    return get_spec_file_at_gitref(git_ref, vocab_path, local_mmif_path)


def fetch_annotation_type_versions(spec_version: str,
                                     local_mmif_path: Optional[str] = None) -> dict:
    """
    Fetch the annotation type versions mapping.

    Args:
        spec_version: MMIF specification version tag (e.g., "1.0.0")
        local_mmif_path: Path to local MMIF repository (optional)

    Returns:
        Dictionary mapping annotation type names to version strings
    """
    attypevers_path = 'docs/{version}/vocabulary/attypeversions.json'
    data = get_spec_file_at_gitref(spec_version, attypevers_path, local_mmif_path)
    return json.loads(data)


class ResourceFetcher:
    """
    Helper class for fetching multiple MMIF spec resources.

    This class encapsulates the logic for fetching all necessary resources
    for a build, handling both remote and local sources.
    """

    def __init__(self,
                 spec_version: str,
                 git_ref: str,
                 local_mmif_path: Optional[str] = None):
        """
        Initialize the resource fetcher.

        Args:
            spec_version: MMIF spec version tag (e.g., "1.0.0")
            git_ref: Git ref to fetch resources from (tag or branch)
            local_mmif_path: Path to local MMIF repository (optional)
        """
        self.spec_version = spec_version
        self.git_ref = git_ref
        self.local_mmif_path = local_mmif_path

    def fetch_all_resources(self) -> dict:
        """
        Fetch all required MMIF spec resources.

        Returns:
            Dictionary with keys:
                - 'schema': MMIF JSON schema (bytes)
                - 'vocabulary': CLAMS vocabulary YAML (bytes)
                - 'attypeversions': Annotation type versions (dict)
        """
        return {
            'schema': fetch_mmif_schema(self.git_ref, self.local_mmif_path),
            'vocabulary': fetch_clams_vocabulary(self.git_ref, self.local_mmif_path),
            'attypeversions': fetch_annotation_type_versions(
                self.spec_version, self.local_mmif_path
            )
        }
