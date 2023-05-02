#! /usr/bin/env python3
import io
import json
import os
import re
import shutil
import string
import subprocess
from os.path import join as pjoin
from typing import Union
from urllib import request

import setuptools.command.build_py
import setuptools.command.develop

name = "mmif-python"
version_fname = "VERSION"
vocabulary_templates_path = 'templates/python/vocabulary'
cmdclass = {}
LOCALMMIF = None
if 'LOCALMMIF' in os.environ:
    LOCALMMIF = os.environ['LOCALMMIF']
    print(f"==== using local MMIF files at '{LOCALMMIF}' ====")

# Used to have `import mmif` that imported `mmif` directory as a sibling, not `mmif` site-package,
# but that created a circular dependency (importing `mmif` requires packages in "requirements.txt")
# so we copy or move relevant package level variables used in the pre-build stage to here
mmif_name = "mmif"
mmif_res_pkg = 'res'
mmif_ver_pkg = 'ver'
mmif_vocabulary_pkg = 'vocabulary'
mmif_schema_res_oriname = 'schema/mmif.json'
mmif_schema_res_name = 'mmif.json'
mmif_vocab_res_oriname = 'vocabulary/clams.vocabulary.yaml'
mmif_vocab_attypevers_res_oriname = 'docs/{version}/vocabulary/attypeversions.json'
mmif_vocab_res_name = 'clams.vocabulary.yaml'


def do_not_edit_warning(dirname):
    with open(pjoin(dirname, 'do-not-edit.txt'), 'w') as warning:
        warning.write("Contents of this directory is automatically generated and should not be manually edited.\n")
        warning.write("Any manual changes will be wiped at next build time.\n")


def generate_subpack(parpack_name, subpack_name, init_contents=""):
    subpack_dir = pjoin(parpack_name, subpack_name)
    shutil.rmtree(subpack_dir, ignore_errors=True)
    os.makedirs(subpack_dir, exist_ok=True)
    do_not_edit_warning(subpack_dir)
    init_mod = open(pjoin(subpack_dir, '__init__.py'), 'w')
    init_mod.write(init_contents)
    init_mod.close()
    return subpack_dir


def generate_vocab_enum(spec_version, clams_types_vers, mod_name) -> str:
    
    template_file = os.path.join(vocabulary_templates_path, mod_name + '.txt')
    if mod_name.startswith('annotation'):
        base_class_name = 'AnnotationTypesBase'
    elif mod_name.startswith('document'):
        base_class_name = 'DocumentTypesBase'
    else: 
        base_class_name = 'ClamsTypesBase'

    file_out = io.StringIO()
    with open(template_file, 'r') as file_in:
        file_out.write(string.Template(file_in.read()).safe_substitute(VERSION=spec_version))
    for type_name, type_ver in clams_types_vers:
        vocab_url = f'http://mmif.clams.ai/vocabulary/{type_name}/{type_ver}'
        file_out.write(f"    {type_name} = {base_class_name}('{vocab_url}')\n")
    file_out.write(f"    typevers = {dict(clams_types_vers)}\n")

    string_out = file_out.getvalue()
    file_out.close()
    return string_out


def update_target_spec(target_vers_csv, specver):
    """
    Function to record target spec version at build time. 
    This will update ``documentation/target-versions.csv`` file. 
    And in the github action for publication (``.github/workflow/publish.yml``)
    the csv fill will be committed as a part of documentation publication. 
    The csv file is used for 
    
    #. Public website for ``mmif-python`` API
    #. ``sphinx-multiversion`` to generate ``ver`` package for older versions
    
    Unlike ``clams-python`` where this function is placed in ``documentation/conf.py``
    (because the file is a part of documentation? ),
    I put this function here in ``setup.py`` mainly because it is easier to access
    ``version`` and ``specver`` variables in the ``setup.py``. 
    
    Also note that there are two make goals for documentation generation. 
    
    #. ``doc``: generated a single-versioned documentation from current work tree
        * Uses vanilla ``sphinx-build`` command.
        * Vanilla ``sphinx-build`` does not invoke ``setup.py`` at all.
        * Thus, running vanilla cmd without sdist ran before will fail (e.g. ``ver`` package not found).
    #. ``docs``: generated multi-version documentation from git tags
        * Uses our fork of ``sphinx-multiversion`` (https://github.com/clamsproject/sphinx-multiversion)
        * This will invoke ``setup.py sdist`` for each version to make sure all source dist content is generated. 
    
    Finally, when this function is needed to be moved to conf.py (I think that's a more proper place),
    use this code snippet to import local ``mmif`` package and use __version__ and __specver__
     sys.path.append("..")
     import mmif
    """
    with open(target_vers_csv) as in_f, open(f'{target_vers_csv}.new', 'w') as out_f:
        lines = in_f.readlines()
        if not lines[1].startswith(version):
            lines.insert(1, f'{version},"{specver}"\n')
        for line in lines:
            out_f.write(line)
        shutil.move(out_f.name, in_f.name)


def generate_vocabulary(spec_version, clams_types_vers):
    """
    :param spec_version:
    :param clams_types_vers: list of (name, version) tuples of annotation types in CLAMS vocab
    :param template_path: the directory of source txt files
    :return:
    """
    types = {
        'base_types': ['ThingTypesBase', 'ThingType', 'ClamsTypesBase', 'AnnotationTypesBase', 'DocumentTypesBase'],
        'annotation_types': ['AnnotationTypes'],
        'document_types': ['DocumentTypes']
    }
    vocabulary_dir = generate_subpack(
        mmif_name, mmif_vocabulary_pkg,
        '\n'.join(
            f"from .{mod_name} import {class_name}"
            for mod_name, classes in types.items()
            for class_name in classes
        ) + '\n\n' + "typevers = {**ThingType.typevers, **AnnotationTypes.typevers, **DocumentTypes.typevers}" + '\n'
    )
    document_types = []
    annotation_types = []
    base_types = []
    
    for n, v in clams_types_vers.items():
        if n == 'Thing':
            base_types.append((n, v))
        elif 'Document' in n:
            document_types.append((n, v))
        else:
            annotation_types.append((n, v))

    type_lists = {
        'document_types': document_types,
        'annotation_types': annotation_types,
        'base_types': base_types
    }

    for mod_name, type_ver_list in type_lists.items():
        enum_contents = generate_vocab_enum(spec_version, type_ver_list, mod_name)
        write_res_file(vocabulary_dir, mod_name+'.py', enum_contents)

    return vocabulary_dir


def get_latest_mmif_gittag():
    # vmaj, vmin, vpat = version.split('.')[0:3]
    res = request.urlopen('https://api.github.com/repos/clamsproject/mmif/git/refs/tags')
    body = json.loads(res.read())
    tags = [os.path.basename(tag['ref']) for tag in body]
    # sort and return highest version
    mmif_ver_format = lambda x: re.match(r'\d+\.\d+\.\d$', x)
    return sorted([tag for tag in tags if mmif_ver_format(tag)])[-1]


def get_spec_file_at_gitref(tag, filepath: str) -> bytes:
    filepath = filepath.format(version=tag)
    if LOCALMMIF is not None:
        return subprocess.run(f'git --git-dir {LOCALMMIF}/.git --no-pager show {tag}:{filepath}'.split(), capture_output=True).stdout
    file_url = f"https://raw.githubusercontent.com/clamsproject/mmif/{tag}/{filepath}"
    return request.urlopen(file_url).read()


def write_res_file(res_dir: str, res_name: str, res_data: Union[bytes, str]):
    open_ops = 'wb' if type(res_data) == bytes else 'w'
    res_file = open(pjoin(res_dir, res_name), open_ops)
    res_file.write(res_data)
    res_file.close()


# note that `VERSION` file will not included in s/bdist - s/bdist should already have `mmif_ver_pkg` properly generated
if os.path.exists(version_fname):
    with open(version_fname, 'r') as version_f:
        version = version_f.read().strip()
else:
    raise ValueError(f"Cannot find {version_fname} file. Use `make version` to generate one.")


def prep_ext_files(setuptools_cmd):
    ori_run = setuptools_cmd.run

    def mod_run(self):
        # will infer the `spec_ver` from the latest git tag available either on GH or local `mmif` repository.
        # NOTE that when `make develop`, it will use specification files from upstream "develop" branch of `mmif` repo
        latest_mmif_gittag = get_latest_mmif_gittag()
        spec_file_gitref = latest_mmif_gittag if '.dev' not in version else 'develop'
        # legacy version tags were formatted as xx-a.b.c (e.g., vocab-0.0.1)
        spec_version = latest_mmif_gittag.split('-')[-1]
        # making resources into a python package so that `pkg_resources` can access resource files
        res_dir = generate_subpack(mmif_name, mmif_res_pkg)

        # the following will generate a new version value based on VERSION file
        generate_subpack(mmif_name, mmif_ver_pkg, f'__version__ = "{version}"\n__specver__ = "{spec_version}"')
        update_target_spec('documentation/target-versions.csv', spec_version)

        # and write resource files
        for res_name, res_oriname in [(mmif_schema_res_name, mmif_schema_res_oriname), (mmif_vocab_res_name, mmif_vocab_res_oriname)]:
            if LOCALMMIF:
                res_content = open(pjoin(LOCALMMIF, res_oriname)).read()
            else:
                res_content = get_spec_file_at_gitref(spec_file_gitref, res_oriname)
            write_res_file(res_dir, res_name, res_content)

        # write vocabulary enum
        import yaml
        attypevers = json.load(io.BytesIO(get_spec_file_at_gitref(latest_mmif_gittag, mmif_vocab_attypevers_res_oriname)))
        if '.dev' not in version:
            vocab_yaml_file = io.BytesIO(get_spec_file_at_gitref(latest_mmif_gittag, mmif_vocab_res_oriname))
            clams_types_vers = {t['name']: attypevers[t['name']] for t in list(yaml.safe_load_all(vocab_yaml_file.read()))}
        else:
            last_clams_types = {t['name']: t for t in yaml.safe_load_all(get_spec_file_at_gitref(latest_mmif_gittag, mmif_vocab_res_oriname))}
            if LOCALMMIF:
                new_clams_types = {t['name']: t for t in yaml.safe_load_all(open(pjoin(LOCALMMIF, mmif_vocab_res_oriname)))}
            else:
                new_clams_types = {t['name']: t for t in yaml.safe_load_all(get_spec_file_at_gitref(spec_file_gitref, mmif_vocab_res_oriname))}
            clams_types_vers = {n: attypevers[n] for n, t in last_clams_types.items()}
            for tname in new_clams_types:
                if tname not in last_clams_types:
                    clams_types_vers[tname] = 'v1'
                elif last_clams_types[tname] != new_clams_types[tname]:
                    clams_types_vers[tname] = f'v{int(clams_types_vers[tname][1:])+1}'
        generate_vocabulary(spec_version, clams_types_vers)
        ori_run(self)

    setuptools_cmd.run = mod_run
    return setuptools_cmd


@prep_ext_files
class SdistCommand(setuptools.command.sdist.sdist):
    pass


@prep_ext_files
class DevelopCommand(setuptools.command.develop.develop):
    pass


cmdclass['sdist'] = SdistCommand
cmdclass['develop'] = DevelopCommand

with open('README.md') as readme:
    long_desc = readme.read()

with open('requirements.txt') as requirements:
    requires = requirements.readlines()

setuptools.setup(
    name=name,
    version=version,
    author="Brandeis Lab for Linguistics and Computation",
    author_email="admin@clams.ai",
    description="Python implementation of MultiMedia Interchange Format specification. (https://mmif.clams.ai)",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    url="https://mmif.clams.ai",
    packages=setuptools.find_packages(),
    cmdclass=cmdclass,
    # this is for *building*, building (build, bdist_*) doesn't get along with MANIFEST.in
    # so using this param explicitly is much safer implementation
    package_data={
        'mmif': [f'{mmif_res_pkg}/*', f'{mmif_ver_pkg}/*', f'{mmif_vocabulary_pkg}/*'],
    },
    install_requires=requires,
    extras_require={
        'dev': [
            'pytest',
            'pytest-pep8',
            'pytest-cov',
            'pytype',
            'sphinx'
        ]
    },
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers ',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3 :: Only',
    ]
)
