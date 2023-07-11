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

Utility Plugins
^^^^^^^^^^^^^^^

.. warning::

  This feature is experimental and subject to change in the future.
  See `this issue <https://github.com/clamsproject/mmif-python/issues/224>`_ for limitations and known issues.

Utility plugins, or ``mmif-utils-`` plugins are used to provide monkeypatch functions to ``mmif-python``. 
Currently :class:`mmif.serialize.model.MmifObject` and its subclasses are the only classes that are under the scope of monkeypatching supported by the `mmif-python` core SDK. 
(Of course any Python developer can come up with other ways to custom patch any parts of the SDK, it's just not supported by the method described here.)

For writing pluggable monkeypatches for MMIF serialization classes, you need to implement a Python `"package" <https://docs.python.org/3/tutorial/modules.html#packages>`_ (do not confuse with PYPI distribution), that meets these requirements; 

#. the package must be named ``mmif_utils_<NAME>``. The prefix is important as it's used in the plugin discovery process from the core ``mmif-python`` modules. ``<NAME>`` can be any string, but it's recommended to use a name that describes the functionality of the plugin.
#. the top module of the package must have a dictionary named ``patches``. 
  #. The dictionary must be keyed with each class that you want to monkeypatch. The value of the key must be an iterable of functions that will be monkeypatched to the class. 
  #. The function must be a callable, and it must take the class instance as the first argument, so that when monkeypatched to a class, it can be called as a method of the class instance.

Here's a minimal example code snippet of a ``mmif-utils-`` plugin.

.. code-block:: python

  import cv2
  from mmif.serialize import Mmif
  from mmif.vocabulary import AnnotationTypes, DocumentTypes


  def get_framerate(mmif: Mmif, video_doc_id: str):  # first argument must be the class instance
      video_doc = mmif.get_document_by_id(video_doc_id)
      if video_doc is None or video_doc.at_type != DocumentTypes.VideoDocument:
          raise ValueError(f'Video document with id "{video_doc_id}" does not exist.')
      for v in mmif.get_views_for_document(video_doc_id):
          for a in v.get_annotations(AnnotationTypes.Annotation):
              framerate_keys = ('fps', 'framerate')
              for k, v in a.properties.items():
                  if k.lower() in framerate_keys:
                      return v
      cap = cv2.VideoCapture(video_doc.location_path())
      return cap.get(cv2.CAP_PROP_FPS)

  patches = {Mmif: [get_framerate]}  # all callables in the list must have `Mmif` instance as the first argument

Then when this code is loaded as a ``mmif-utils-`` plugin, the ``get_framerate`` function will be monkeypatched to the :class:`mmif.serialize.mmif.Mmif` class, and it can be called as a method of the class instance.
NOTE that a monkeypatch will "overwrite" the original method of the class, so it's important to make sure that the monkeypatched method has the same signature as the original method.
Also if there's no original method, the method from a plugin will be simply added to the class, not altering any existing code.
