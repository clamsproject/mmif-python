#!/usr/bin/env python3
"""
Cleanup script for mmif-python build artifacts.

Replaces `make clean` and `make distclean` Makefile targets.

Usage:
    python scripts/clean.py              # Clean all build artifacts
    python scripts/clean.py --dist-only  # Clean only distribution artifacts
"""

import argparse
import os
import shutil
import subprocess
import sys


def remove_path(path, description=""):
    """Remove a file or directory if it exists."""
    if os.path.exists(path):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            print(f"Removed: {path}" + (f" ({description})" if description else ""))
            return True
        except Exception as e:
            print(f"Warning: Could not remove {path}: {e}", file=sys.stderr)
            return False
    return False


def clean_generated_code():
    """Remove generated code packages."""
    print("\nCleaning generated code...")
    paths = [
        ('mmif/ver', 'version package'),
        ('mmif/res', 'resources package'),
        ('mmif/vocabulary', 'vocabulary package'),
    ]

    for path, desc in paths:
        remove_path(path, desc)


def clean_build_artifacts():
    """Remove build artifacts."""
    print("\nCleaning build artifacts...")
    paths = [
        ('build', 'build directory'),
        ('mmif_python.egg-info', 'egg-info directory'),
        ('__pycache__', 'Python cache'),
    ]

    for path, desc in paths:
        remove_path(path, desc)

    # Remove all __pycache__ directories
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            cache_dir = os.path.join(root, '__pycache__')
            remove_path(cache_dir, 'Python cache')


def clean_dist_artifacts():
    """Remove distribution artifacts."""
    print("\nCleaning distribution artifacts...")
    paths = [
        ('dist', 'distribution directory'),
    ]

    for path, desc in paths:
        remove_path(path, desc)


def clean_test_artifacts():
    """Remove test and coverage artifacts."""
    print("\nCleaning test artifacts...")
    paths = [
        ('.pytest_cache', 'pytest cache'),
        ('.coverage', 'coverage data'),
        ('coverage.xml', 'coverage XML report'),
        ('htmlcov', 'coverage HTML report'),
        ('.hypothesis', 'hypothesis cache'),
        ('tests/.hypothesis', 'hypothesis test cache'),
        ('.pytype', 'pytype cache'),
    ]

    for path, desc in paths:
        remove_path(path, desc)


def clean_docs():
    """Remove generated documentation."""
    print("\nCleaning documentation...")
    remove_path('docs', 'generated documentation')


def clean_version_files():
    """Remove VERSION files."""
    print("\nCleaning version files...")
    paths = [
        ('VERSION', 'version file'),
        ('VERSION.dev', 'dev version file'),
    ]

    for path, desc in paths:
        remove_path(path, desc)


def restore_documentation_csv():
    """Restore documentation/target-versions.csv from git."""
    csv_file = 'documentation/target-versions.csv'
    if os.path.exists('.git'):
        try:
            print(f"\nRestoring {csv_file} from git...")
            subprocess.run(
                ['git', 'checkout', '--', csv_file],
                check=True,
                capture_output=True
            )
            print(f"Restored: {csv_file}")
        except subprocess.CalledProcessError:
            print(f"Warning: Could not restore {csv_file} from git", file=sys.stderr)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clean build artifacts for mmif-python"
    )
    parser.add_argument(
        '--dist-only',
        action='store_true',
        help="Clean only distribution artifacts (equivalent to make distclean)"
    )
    parser.add_argument(
        '--keep-version',
        action='store_true',
        help="Keep VERSION and VERSION.dev files"
    )
    parser.add_argument(
        '--keep-docs',
        action='store_true',
        help="Keep generated documentation"
    )

    args = parser.parse_args()

    print("mmif-python cleanup script")
    print("=" * 50)

    if args.dist_only:
        # Only clean distribution artifacts (make distclean)
        clean_dist_artifacts()
    else:
        # Full clean (make clean)
        clean_dist_artifacts()
        clean_build_artifacts()
        clean_test_artifacts()
        clean_generated_code()

        if not args.keep_version:
            clean_version_files()

        if not args.keep_docs:
            clean_docs()

        restore_documentation_csv()

    # Remove hidden cache directories
    print("\nCleaning hidden cache directories...")
    for item in os.listdir('.'):
        if item.startswith('.') and item.endswith('cache'):
            remove_path(item, 'cache directory')

    print("\n" + "=" * 50)
    print("Cleanup complete!")


if __name__ == '__main__':
    main()
