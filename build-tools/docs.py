import argparse
import subprocess
import sys
import os
import venv
import tempfile
import shutil
from pathlib import Path

def run_command(command, cwd=None, check=True, env=None):
    """Helper to run a shell command."""
    print(f"Running: {' '.join(str(c) for c in command)}")
    result = subprocess.run(command, cwd=cwd, env=env)
    if check and result.returncode != 0:
        print(f"Error: Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)
    return result

class Venv:
    """A helper class to manage a virtual environment."""
    def __init__(self, venv_dir):
        self.venv_dir = Path(venv_dir)
        self.python = self.venv_dir / "bin" / "python"
        self.pip = self.venv_dir / "bin" / "pip"
        self.sphinx_build = self.venv_dir / "bin" / "sphinx-build"

    def create(self):
        print(f"Creating virtual environment in: {self.venv_dir}")
        venv.create(self.venv_dir, with_pip=True)

    def run_pip(self, *args, cwd=None):
        run_command([self.pip, *args], cwd=cwd)

    def run_python(self, *args, cwd=None):
        run_command([self.python, *args], cwd=cwd)

    def run_sphinx_build(self, *args, cwd=None, check=True):
        return run_command([self.sphinx_build, *args], cwd=cwd, check=check)

def build_docs_local(source_dir: Path):
    """
    Builds documentation for the provided source directory.
    Assumes it's running in an environment with necessary tools.
    """
    print("--- Running in Local Build Mode ---")
    
    # 1. Generate source code and install in editable mode.
    print("\n--- Step 1: Generating source code and installing in editable mode ---")
    run_command([sys.executable, "-m", "pip", "install", "-e", "."], cwd=source_dir)

    # 2. Install documentation-specific dependencies.
    print("\n--- Step 2: Installing documentation dependencies ---")
    doc_reqs = Path.cwd() / "build-tools" / "requirements.docs.txt"
    if not doc_reqs.exists():
        print(f"Error: Documentation requirements not found at {doc_reqs}")
        sys.exit(1)
    run_command([sys.executable, "-m", "pip", "install", "-r", str(doc_reqs)])

    # 3. Build the documentation using Sphinx.
    print("\n--- Step 3: Building Sphinx documentation ---")
    docs_source_dir = source_dir / "documentation"
    docs_build_dir = docs_source_dir / "_build" / "html"
    sphinx_command = [
        "sphinx-build",
        str(docs_source_dir),
        str(docs_build_dir),
        "-b", "html",  # build html
        "-a",          # write all files (rebuild everything)
        "-E",          # don't use a saved environment, reread all files
    ]
    run_command(sphinx_command)

    print(f"\nDocumentation build complete. Output in: {docs_build_dir}")
    return docs_build_dir

def build_versioned_docs(env: Venv, source_path: Path, version: str):
    """
    Build documentation for a specific version with unified furo theme.
    Works for all versions (old and new) with consistent visual output.
    """
    print(f"\n--- Building documentation for version {version} ---")

    # Skip old pinned requirements.txt as they have Python 3.13 incompatible deps
    # Instead, install modern versions of core dependencies
    # Pin deepdiff<7 for compatibility with orderly-set 5.3.x (required by older versions)
    print("\n--- Installing modern compatible dependencies ---")
    env.run_pip("install", "jsonschema", "requests", "pyyaml", "deepdiff<7", cwd=source_path)

    # Install sphinx 7.x (Python 3.13 compatible), furo theme, and m2r2
    print("\n--- Installing sphinx and furo theme ---")
    env.run_pip("install", "sphinx>=7.0,<8.0", "furo", "m2r2", cwd=source_path)

    # Write VERSION file (needed for setup.py and sphinx)
    version_file = source_path / "VERSION"
    version_file.write_text(version)

    # Inject linkcode_resolve function into conf.py for GitHub source links
    print("\n--- Injecting linkcode_resolve into conf.py ---")
    conf_py = source_path / "documentation" / "conf.py"
    if conf_py.exists():
        linkcode_snippet = f'''

# -- Injected linkcode configuration for GitHub source links --
import inspect
import os
import sys
from pathlib import Path

def linkcode_resolve(domain, info):
    if domain != 'py' or not info.get('module'):
        return None
    try:
        obj = sys.modules.get(info['module'])
        if obj is None: return None
        for part in info['fullname'].split('.'):
            obj = getattr(obj, part)
        unwrapped_obj = inspect.unwrap(obj)
        filename = inspect.getsourcefile(unwrapped_obj)
        if not filename: return None
        lines, start_lineno = inspect.getsourcelines(unwrapped_obj)
        end_lineno = start_lineno + len(lines) - 1
        repo_root = Path(__file__).parent.parent
        rel_path = Path(filename).relative_to(repo_root)
        return f"https://github.com/clamsproject/mmif-python/blob/{version}/{{rel_path}}#L{{start_lineno}}-L{{end_lineno}}"
    except Exception:
        return None
'''
        with open(conf_py, "a") as f:
            f.write(linkcode_snippet)

    # Install package in develop mode to generate code (ver, res, vocabulary)
    # Uses setup.py develop for compatibility with all versions
    print("\n--- Installing package in develop mode ---")
    env.run_python("setup.py", "develop", cwd=source_path)

    # Build documentation with sphinx-build
    print("\n--- Building Sphinx documentation ---")
    docs_source_dir = source_path / "documentation"
    docs_build_dir = docs_source_dir / "_build" / "html"

    # Run sphinx-build with unified parameters for visual consistency
    result = env.run_sphinx_build(
        str(docs_source_dir),
        str(docs_build_dir),
        "-b", "html",
        "-D", f"project=mmif-python-{version}",
        "-D", f"version={version}",
        "-D", "extensions=sphinx.ext.autodoc,sphinx.ext.linkcode,m2r2",
        "-D", "html_theme=furo",
        "-a",  # write all files
        "-E",  # don't use saved environment
        "--keep-going",  # continue past errors
        cwd=source_path,
        check=False
    )

    # Verify output was created
    index_html = docs_build_dir / "index.html"
    if not index_html.exists():
        print(f"Error: Documentation build failed - no index.html created")
        sys.exit(1)

    if result.returncode != 0:
        print(f"Warning: Sphinx build had errors (exit code {result.returncode}), but output was created")

    return docs_build_dir


def build_docs_for_version(version: str, output_base_dir: Path, repo_path: Path = None):
    """
    Builds docs for a specific version in a sandbox.
    Uses local repo copy instead of cloning for efficiency.

    Args:
        version: Git tag/ref to build
        output_base_dir: Directory to output built docs
        repo_path: Path to local repo to copy from (defaults to cwd)
    """
    print(f"--- Running in Version Build Mode for version: {version} ---")

    if repo_path is None:
        repo_path = Path.cwd()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        source_path = tmp_path / "source"
        venv_path = tmp_path / "venv"

        print(f"\n--- Step 1: Copying local repository to temporary directory ---")
        shutil.copytree(repo_path, source_path, symlinks=True)
        # Reset to clean state and checkout the target version
        run_command(["git", "checkout", "."], cwd=source_path)
        run_command(["git", "clean", "-fdx"], cwd=source_path)
        run_command(["git", "checkout", version], cwd=source_path)

        print(f"\n--- Step 2: Creating and setting up virtual environment ---")
        env = Venv(venv_path)
        env.create()
        # Use setuptools<80 for compatibility with older setup.py files
        # that use the old import structure
        env.run_pip("install", "--upgrade", "pip", "setuptools<80", "wheel")

        print(f"\n--- Step 3: Building documentation ---")
        built_docs_path = build_versioned_docs(env, source_path, version)

        print(f"\n--- Step 4: Copying built artifacts to output directory ---")
        version_output_dir = output_base_dir / version
        if version_output_dir.exists():
            print(f"Removing existing directory: {version_output_dir}")
            shutil.rmtree(version_output_dir)
        shutil.copytree(built_docs_path, version_output_dir)

        print(f"\nDocumentation for {version} built successfully in: {version_output_dir}")

def get_all_tags():
    """Get all git tags sorted by version."""
    result = subprocess.run(
        ["git", "tag", "--sort=version:refname"],
        capture_output=True, text=True, check=True
    )
    return [tag.strip() for tag in result.stdout.strip().split('\n') if tag.strip()]


def get_tags_since(since_version: str):
    """Get all tags >= since_version."""
    all_tags = get_all_tags()
    try:
        start_idx = all_tags.index(since_version)
        return all_tags[start_idx:]
    except ValueError:
        print(f"Warning: Version {since_version} not found in tags.")
        return []


def main():
    parser = argparse.ArgumentParser(
        description="Build documentation for the mmif-python project. "
                    "Can build for the current directory or a specific git version in a sandbox."
    )
    parser.add_argument(
        "--build-ver",
        metavar="<git-ref>",
        help="Build docs for a specific git ref (tag/branch) in a temporary, sandboxed environment."
    )
    parser.add_argument(
        "--build-all-since",
        metavar="<version>",
        help="Build docs for all versions since (and including) the specified version."
    )
    parser.add_argument(
        "--output-dir",
        metavar="<path>",
        default="docs-testbuilds",
        help="The base directory for versioned documentation output (default: docs-testbuilds)."
    )
    parser.add_argument(
        "--list-versions",
        action="store_true",
        help="List all available versions and exit."
    )
    args = parser.parse_args()

    if args.list_versions:
        tags = get_all_tags()
        print("Available versions:")
        for tag in tags:
            print(f"  {tag}")
        return

    if args.build_all_since:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True)
        versions = get_tags_since(args.build_all_since)
        print(f"Building documentation for {len(versions)} versions: {versions}")
        failed = []
        for i, version in enumerate(versions, 1):
            print(f"\n{'='*60}")
            print(f"Building version {version} ({i}/{len(versions)})")
            print(f"{'='*60}")
            try:
                build_docs_for_version(version, output_dir)
            except Exception as e:
                print(f"ERROR building {version}: {e}")
                failed.append((version, str(e)))

        print(f"\n{'='*60}")
        print(f"BUILD SUMMARY")
        print(f"{'='*60}")
        print(f"Total versions: {len(versions)}")
        print(f"Successful: {len(versions) - len(failed)}")
        print(f"Failed: {len(failed)}")
        if failed:
            print("\nFailed versions:")
            for version, error in failed:
                print(f"  {version}: {error}")
    elif args.build_ver:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True)
        build_docs_for_version(args.build_ver, output_dir)
    else:
        build_docs_local(Path.cwd())

if __name__ == "__main__":
    main()
