#!/usr/bin/env python3
"""
Version management script for mmif-python.

Replaces `make version` and `make devversion` Makefile targets.

This is a CLI wrapper around the build_tools.version module.

Usage:
    python scripts/manage_version.py              # Interactive release version
    python scripts/manage_version.py --dev        # Generate dev version
    python scripts/manage_version.py --set 1.0.0  # Set specific version
"""

import argparse
import os
import re
import subprocess
import sys

# Import from build_tools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from build_tools import version as version_utils


def parse_version(version: str) -> tuple:
    """
    Parse a version string into components.

    Args:
        version: Version string (e.g., "1.2.3" or "1.2.3.dev4")

    Returns:
        Tuple of (major, minor, patch, dev_number)
        dev_number is 0 for release versions
    """
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:\.dev(\d+))?$', version)
    if not match:
        raise ValueError(f"Invalid version format: {version}")

    major, minor, patch, dev = match.groups()
    return (int(major), int(minor), int(patch), int(dev) if dev else 0)


def format_version(major: int, minor: int, patch: int, dev: int = 0) -> str:
    """Format version components into a version string."""
    if dev:
        return f"{major}.{minor}.{patch}.dev{dev}"
    else:
        return f"{major}.{minor}.{patch}"


def increase_patch(version: str) -> str:
    """Increase the patch version number."""
    major, minor, patch, _ = parse_version(version)
    return format_version(major, minor, patch + 1)


def add_dev(version: str) -> str:
    """Convert a version to dev1."""
    major, minor, patch, _ = parse_version(version)
    return format_version(major, minor, patch, 1)


def increase_dev(version: str) -> str:
    """Increase the dev version number."""
    major, minor, patch, dev = parse_version(version)
    if dev == 0:
        raise ValueError(f"Version {version} is not a dev version")
    return format_version(major, minor, patch, dev + 1)


def get_local_git_tags() -> str:
    """Get latest tag from local git repository."""
    try:
        result = subprocess.run(
            ['git', 'tag'],
            capture_output=True,
            text=True,
            check=True
        )
        tags = result.stdout.strip().split('\n')
        version_pattern = re.compile(r'^(\d+\.\d+\.\d+(?:\.dev\d+)?)$')
        version_tags = [tag for tag in tags if version_pattern.match(tag)]

        if not version_tags:
            return '0.0.0'

        # Sort and return latest
        return sorted(version_tags, key=lambda v: [int(x) if x.isdigit() else 0
                                                    for x in re.split(r'[.\D]', v)])[-1]
    except subprocess.CalledProcessError:
        return '0.0.0'


def generate_dev_version() -> str:
    """
    Generate a dev version based on latest mmif-python and mmif spec tags.

    Logic:
    - If mmif-python major.minor matches mmif spec major.minor:
        - If latest mmif-python is dev: increment dev number
        - Otherwise: increase patch and add .dev1
    - Otherwise: use mmif spec version with .dev1
    """
    python_ver = get_local_git_tags()
    if python_ver == '0.0.0':
        # Fetch from GitHub using build_tools
        try:
            python_ver = version_utils.get_latest_mmif_git_tag()
        except RuntimeError:
            python_ver = '0.0.0'

    # Fetch MMIF spec version using build_tools
    try:
        spec_ver = version_utils.get_latest_mmif_git_tag()
    except RuntimeError as e:
        print(f"Error: Could not fetch MMIF spec version: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse versions
    py_major, py_minor, py_patch, py_dev = parse_version(python_ver)
    spec_major, spec_minor, spec_patch, _ = parse_version(spec_ver)

    # Check if major.minor match
    if py_major == spec_major and py_minor == spec_minor:
        if py_dev > 0:
            # Increment dev number
            return increase_dev(python_ver)
        else:
            # Increase patch and add .dev1
            return add_dev(increase_patch(python_ver))
    else:
        # Use spec version with .dev1
        return add_dev(spec_ver)


def write_version_file(version: str, filename: str = "VERSION") -> None:
    """Write version to file."""
    with open(filename, 'w') as f:
        f.write(version + '\n')
    print(f"Version set to: {version}")
    print(f"Written to: {filename}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manage version numbers for mmif-python"
    )
    parser.add_argument(
        '--dev',
        action='store_true',
        help="Generate a development version"
    )
    parser.add_argument(
        '--set',
        metavar='VERSION',
        help="Set a specific version (e.g., 1.0.0 or 1.0.0.dev1)"
    )
    parser.add_argument(
        '--output',
        metavar='FILE',
        default='VERSION',
        help="Output file (default: VERSION)"
    )

    args = parser.parse_args()

    # Check if VERSION.dev exists (from old Makefile system)
    version_dev_file = 'VERSION.dev'
    if os.path.exists(version_dev_file) and not args.set and not args.dev:
        # Use existing VERSION.dev
        with open(version_dev_file, 'r') as f:
            version = f.read().strip()
        write_version_file(version, args.output)
        return

    if args.set:
        # Validate the version format
        try:
            parse_version(args.set)
            write_version_file(args.set, args.output)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.dev:
        # Generate dev version
        version = generate_dev_version()
        write_version_file(version, args.output)
        # Also write to VERSION.dev for compatibility
        write_version_file(version, version_dev_file)
    else:
        # Interactive mode
        current = get_local_git_tags()
        if current == '0.0.0':
            current = fetch_latest_tag('clamsproject/mmif-python')

        print(f"Current version: {current}")
        suggested = increase_patch(current)
        print(f"Suggested version (increase patch): {suggested}")

        user_input = input(f"Enter new version (or press Enter for {suggested}): ").strip()

        if user_input:
            try:
                parse_version(user_input)
                write_version_file(user_input, args.output)
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            write_version_file(suggested, args.output)


if __name__ == '__main__':
    main()
