.. _plugins:

Developing plugins for MMIF Python SDK
======================================


Overview 
--------

As MMIF JSON files can carry information about media document files without actually carrying file contents, file accessing modules in ``mmif`` Python package (distributed as ``mmif-python`` on PyPI) are designed to be lightweight and flexible so that it can work with additional "plugin" Python packages that can handle concrete file access. 


This documentation focuses on Python implementation of the MMIF. To learn more about the data format specification, please visit the `MMIF website <https://mmif.clams.ai>`_.
``mmif-python`` is a public, open source implementation of the MMIF data format. ``mmif-python`` supports serialization/deserialization of MMIF objects from/to Python objects, as well as many navigation and manipulation helpers for MMIF objects. 

Developer can write simple plugins that can provide additional functionalities to ``mmif-python``. For example, ``mmif-python`` does not provide any file access functionality beyond a local file system (with ``file`` scheme), but it can be extended with a plugin that can handle file access over different protocols (e.g. ``http``, ``s3``, ``ftp``, etc). 

This document contains information about how to write plugins for ``mmif-python``.

.. _docloc_plugin:
Document Location Scheme Plugins
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:class:`mmif.serialize.annotation.Document` class has various methods to access parts of ``location`` property of the document. The location is in `URI/IRI format <https://en.wikipedia.org/wiki/Uniform_Resource_Identifier>`_ (``SCHEME://HOSTNAME/PATH``, in a nutshell) and it has to be resolved to a local file for CLAMS Apps to process the local file to analyze and extract information about the media and its contents. The core ``mmif-python`` distribution only provides a default implementation that can handle ``file`` scheme URIs. 

To add a document location handler plugin, you need to implement a Python `"package" <https://docs.python.org/3/tutorial/modules.html#packages>`_ (do not confuse with PYPI distribution), that meets these requirements; 

#. the package must be named ``mmif_docloc_<SCHEME>``. For example, to implement a handler for ``s3`` scheme, the package name must be ``mmif_docloc_s3``. The prefix is important as it's used in the plugin discovery process from the core ``mmif-python`` modules.
#. the top module of the package must have a function named ``resolve``. The function must take a single argument, which is a :class:`str` of the document location URI. The function must return a :class:`str` of the local file path. For example, if the document location is ``s3://mybucket/myfile.mp4``, a Python user should be able to to something like this; 

.. code-block:: python

   import mmif_docloc_s3
   resolved = mmif_docloc_s3.resolve('s3://mybucket/myfile.mp4')
   # then resolved must be a local file path that can be used to open the file


Here's a minimal example codebase that you refer to when you develop a ``docloc`` plugin. 

(However, before you start writing your own plugin for a specific URI scheme, checking `if there's already a PyPI distribution <https://pypi.org/search/?q=mmif-docloc->`_ for the scheme might be a good idea.)

.. code-block:: sh 

   $ tree .
   .
   ├── mmif_docloc_dummy
   │   └── __init__.py
   ├── pyproject.toml
   └── setup.cfg

    $ cat pyproject.toml
   [build-system]
   requires = ["setuptools"]
   build-backend = "setuptools.build_meta"

   $ cat setup.cfg
   [metadata]
   name = mmif_docloc_dummy  # this name is IMPORTANT
   version = 0.0.1
   description = a plugin to mmif-pyhon to handle `dummy` location scheme


And the plugin code. 

.. code-block:: python 

   # mmif_docloc_dummy/__init__.py
   doc_types = {'video': 'mp4'}

   def resolve(docloc):
       scheme = 'dummy'
       if docloc.startswith(f'{scheme}://'):
           doc_id, doc_type = docloc.split('.')
           return f'/path/to/{doc_id}.{doc_types[doc_type]}'
       else:
           raise ValueError(f'cannot handle document location scheme: {docloc}')

Bulit-in Document Location Scheme Plugins
^^^^

At the moment, ``mmif-python`` PyPI distribution ships a built-in *docloc* plugin that support both ``http`` and ``https`` schemes.
Take a look at :mod:`mmif_docloc_http` module for details. 