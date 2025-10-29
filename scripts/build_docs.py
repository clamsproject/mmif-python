#!/usr/bin/env python3
"""
Documentation build script for mmif-python.

Replaces `make docs` and `make doc` Makefile targets.

Usage:
    python scripts/build_docs.py              # Single-version build (for development)
    python scripts/build_docs.py --multi      # Multi-version build (for publication)
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def get_latest_version_tag():
    """Get the latest version tag from git."""
    try:
        result = subprocess.run(
            ['git', 'tag'],
            capture_output=True,
            text=True,
            check=True
        )
        tags = [tag.strip() for tag in result.stdout.split('\n') if tag.strip()]

        # Filter and sort version tags
        import re
        version_pattern = re.compile(r'^\d+\.\d+\.\d+$')
        version_tags = [tag for tag in tags if version_pattern.match(tag)]

        if not version_tags:
            return None

        # Sort by version number
        return sorted(version_tags, key=lambda v: [int(x) for x in v.split('.')])[-1]
    except subprocess.CalledProcessError:
        return None


def install_dependencies():
    """Install documentation dependencies."""
    print("Installing documentation dependencies...")
    subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '--upgrade', '-r', 'requirements.txt'],
        check=True
    )
    subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '--upgrade', '-r', 'requirements.old'],
        check=False  # This file may not exist
    )


def build_single_version(output_dir='docs'):
    """
    Build single-version documentation for development.

    This is equivalent to `make doc` in the old Makefile.
    """
    print("Building single-version documentation...")

    # Remove existing docs
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)

    # Run sphinx-build
    subprocess.run(
        ['sphinx-build', 'documentation', output_dir, '-b', 'html', '-a'],
        check=True
    )

    print(f"Documentation built successfully in {output_dir}/")


def build_multi_version(output_dir='docs'):
    """
    Build multi-version documentation for publication.

    This is equivalent to `make docs` in the old Makefile.
    """
    print("Building multi-version documentation...")

    # Install dependencies
    install_dependencies()

    # Get latest version
    latest = get_latest_version_tag()
    if not latest:
        print("Warning: No version tags found. Using 'main' as latest.", file=sys.stderr)
        latest = 'main'

    # Remove existing docs
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)

    # Run sphinx-multiversion
    subprocess.run(
        ['sphinx-multiversion', 'documentation', output_dir, '-b', 'html', '-a'],
        check=True
    )

    # Create .nojekyll file for GitHub Pages
    nojekyll_path = os.path.join(output_dir, '.nojekyll')
    Path(nojekyll_path).touch()

    # Create symlink to latest version
    latest_link = os.path.join(output_dir, 'latest')
    latest_target = latest

    # Remove existing symlink if present
    if os.path.islink(latest_link):
        os.unlink(latest_link)

    # Create symlink (works on Unix-like systems)
    try:
        os.symlink(latest_target, latest_link)
        print(f"Created symlink: latest -> {latest_target}")
    except OSError as e:
        print(f"Warning: Could not create symlink: {e}", file=sys.stderr)
        print("You may need to create the symlink manually on Windows.", file=sys.stderr)

    # Create redirect index.html
    index_html = """<!DOCTYPE html>
<html>
<head>
    <title>Redirect to latest version</title>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="0; url=./latest/index.html">
</head>
<body>
    <p>Redirecting to <a href="./latest/index.html">latest documentation</a>...</p>
</body>
</html>
"""
    index_path = os.path.join(output_dir, 'index.html')
    with open(index_path, 'w') as f:
        f.write(index_html)

    print(f"Multi-version documentation built successfully in {output_dir}/")
    print(f"Latest version: {latest}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build documentation for mmif-python"
    )
    parser.add_argument(
        '--multi',
        action='store_true',
        help="Build multi-version documentation (for publication)"
    )
    parser.add_argument(
        '--output',
        '-o',
        metavar='DIR',
        default='docs',
        help="Output directory (default: docs)"
    )

    args = parser.parse_args()

    # Ensure we're in the project root
    if not os.path.exists('documentation'):
        print("Error: documentation/ directory not found.", file=sys.stderr)
        print("Please run this script from the project root directory.", file=sys.stderr)
        sys.exit(1)

    # Ensure VERSION file exists
    if not os.path.exists('VERSION'):
        print("Error: VERSION file not found.", file=sys.stderr)
        print("Run 'python scripts/manage_version.py' first.", file=sys.stderr)
        sys.exit(1)

    # Ensure generated code exists
    if not os.path.exists('mmif/ver'):
        print("Error: Generated code not found (mmif/ver/).", file=sys.stderr)
        print("Run 'pip install -e .' or 'python -m build' first.", file=sys.stderr)
        sys.exit(1)

    try:
        if args.multi:
            build_multi_version(args.output)
        else:
            build_single_version(args.output)
    except subprocess.CalledProcessError as e:
        print(f"Error: Documentation build failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
