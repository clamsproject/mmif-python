"""
Vocabulary enum generation for MMIF Python SDK.

This module generates Python enum classes from CLAMS vocabulary definitions:
- Reads vocabulary YAML files
- Generates Python class files from templates
- Handles version updates for annotation types
"""

import io
import os
import shutil
import string
from typing import Dict, List, Tuple

import yaml


def create_subpackage(parent_package: str,
                       subpackage_name: str,
                       init_contents: str = "") -> str:
    """
    Create a Python subpackage with __init__.py and a warning file.

    Args:
        parent_package: Parent package directory (e.g., "mmif")
        subpackage_name: Name of subpackage to create (e.g., "vocabulary")
        init_contents: Contents for __init__.py file

    Returns:
        Path to the created subpackage directory
    """
    subpack_dir = os.path.join(parent_package, subpackage_name)

    # Remove existing directory if present
    shutil.rmtree(subpack_dir, ignore_errors=True)

    # Create new directory
    os.makedirs(subpack_dir, exist_ok=True)

    # Write warning file
    warning_file = os.path.join(subpack_dir, 'do-not-edit.txt')
    with open(warning_file, 'w') as f:
        f.write("Contents of this directory is automatically generated and should not be manually edited.\n")
        f.write("Any manual changes will be wiped at next build time.\n")

    # Write __init__.py
    init_file = os.path.join(subpack_dir, '__init__.py')
    with open(init_file, 'w') as f:
        f.write(init_contents)

    return subpack_dir


def generate_vocab_enum_module(spec_version: str,
                                 type_versions: List[Tuple[str, str]],
                                 module_name: str,
                                 template_path: str) -> str:
    """
    Generate a vocabulary enum module from a template.

    Args:
        spec_version: MMIF specification version (e.g., "1.0.0")
        type_versions: List of (type_name, version) tuples
        module_name: Name of the module (e.g., "annotation_types")
        template_path: Path to template directory

    Returns:
        Generated module contents as a string
    """
    template_file = os.path.join(template_path, f'{module_name}.txt')

    if not os.path.exists(template_file):
        raise FileNotFoundError(f"Template not found: {template_file}")

    # Determine base class name
    if module_name.startswith('annotation'):
        base_class_name = 'AnnotationTypesBase'
    elif module_name.startswith('document'):
        base_class_name = 'DocumentTypesBase'
    else:
        base_class_name = 'ClamsTypesBase'

    # Read template and substitute version
    with open(template_file, 'r') as f:
        template_content = f.read()

    output = io.StringIO()
    output.write(string.Template(template_content).safe_substitute(VERSION=spec_version))

    # Generate enum entries
    for type_name, type_ver in type_versions:
        vocab_url = f'http://mmif.clams.ai/vocabulary/{type_name}/{type_ver}'
        output.write(f"    {type_name} = {base_class_name}('{vocab_url}')\n")

    # Add version mapping dictionary
    output.write(f"    _typevers = {dict(type_versions)}\n")

    result = output.getvalue()
    output.close()
    return result


def determine_type_versions_for_dev(
    latest_vocab_yaml: bytes,
    dev_vocab_yaml: bytes,
    latest_attypeversions: Dict[str, str]
) -> Dict[str, str]:
    """
    Determine annotation type versions for a dev build.

    For dev builds, we need to:
    1. Start with versions from the latest release
    2. For new types not in latest: assign 'v1'
    3. For modified types: increment version

    Args:
        latest_vocab_yaml: Vocabulary YAML from latest release tag
        dev_vocab_yaml: Vocabulary YAML from develop branch
        latest_attypeversions: Type versions from latest release

    Returns:
        Dictionary mapping type names to version strings
    """
    # Parse both vocabularies
    latest_types = {
        t['name']: t
        for t in yaml.safe_load_all(latest_vocab_yaml)
        if t  # Filter out None values
    }

    dev_types = {
        t['name']: t
        for t in yaml.safe_load_all(dev_vocab_yaml)
        if t  # Filter out None values
    }

    # Start with latest versions
    type_versions = latest_attypeversions.copy()

    # Process each type in dev vocabulary
    for type_name, type_def in dev_types.items():
        if type_name not in latest_types:
            # New type - assign v1
            type_versions[type_name] = 'v1'
        elif latest_types[type_name] != type_def:
            # Modified type - increment version
            current_ver = type_versions.get(type_name, 'v1')
            if current_ver.startswith('v'):
                ver_num = int(current_ver[1:])
                type_versions[type_name] = f'v{ver_num + 1}'
            else:
                type_versions[type_name] = 'v2'

    return type_versions


def generate_vocabulary_package(
    package_dir: str,
    spec_version: str,
    type_versions: Dict[str, str],
    template_path: str = 'templates/python/vocabulary'
) -> str:
    """
    Generate the complete vocabulary package.

    Args:
        package_dir: Parent package directory (e.g., "mmif")
        spec_version: MMIF specification version
        type_versions: Dictionary mapping type names to versions
        template_path: Path to template directory

    Returns:
        Path to the generated vocabulary package
    """
    # Categorize types
    base_types = []
    document_types = []
    annotation_types = []

    for type_name, type_ver in type_versions.items():
        if type_name == 'Thing':
            base_types.append((type_name, type_ver))
        elif 'Document' in type_name:
            document_types.append((type_name, type_ver))
        else:
            annotation_types.append((type_name, type_ver))

    # Define module structure
    modules = {
        'base_types': base_types,
        'annotation_types': annotation_types,
        'document_types': document_types
    }

    type_classes = {
        'base_types': ['ThingTypesBase', 'ThingType', 'ClamsTypesBase',
                      'AnnotationTypesBase', 'DocumentTypesBase'],
        'annotation_types': ['AnnotationTypes'],
        'document_types': ['DocumentTypes']
    }

    # Generate __init__.py imports
    init_imports = '\n'.join(
        f"from .{mod_name} import {class_name}"
        for mod_name, classes in type_classes.items()
        for class_name in classes
    )
    init_imports += '\n\n'
    init_imports += "_typevers = {**ThingType._typevers, **AnnotationTypes._typevers, **DocumentTypes._typevers}\n"

    # Create vocabulary package
    vocab_dir = create_subpackage(package_dir, 'vocabulary', init_imports)

    # Generate each module
    for module_name, type_list in modules.items():
        module_content = generate_vocab_enum_module(
            spec_version, type_list, module_name, template_path
        )
        module_file = os.path.join(vocab_dir, f'{module_name}.py')
        with open(module_file, 'w') as f:
            f.write(module_content)

    return vocab_dir
