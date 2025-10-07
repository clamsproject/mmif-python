.. _introduction:

Getting Started
===============


Overview 
---------

MultiMedia Interchange Format (MMIF) is a JSON(-LD)-based data format designed for reproducibility, transparency and interoperability for customized computational analysis application workflows.
This documentation focuses on Python implementation of the MMIF. To learn more about the data format specification, please visit the `MMIF website <https://mmif.clams.ai>`_.
``mmif-python`` is a public, open source implementation of the MMIF data format. ``mmif-python`` supports serialization/deserialization of MMIF objects from/to Python objects, as well as many navigation and manipulation helpers for MMIF objects. 

Prerequisites
-------------

* `Python <https://www.python.org>`_: the latest ``mmif-python`` requires Python 3.8 or newer. We have no plan to support `Python 2.7 <https://pythonclock.org/>`_. 

Installation 
---------------

Package ``mmif-python`` is distributed via the official PyPI. Users are supposed to pip-install to get latest release. 

.. code-block:: bash

  pip install mmif-python

This will install a package `mmif` to local python.


Installing from source tree for development
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::
  This is not necessary for most users who just want to use the ``mmif-python`` package. This is only for developers who want to modify the source code.

Following these instructions will install the ``mmif-python`` package in `"editable" mode <https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs>`_. This means that any changes you make to the source code will be immediately available to the installed package.

1. First, you need a general developer toolchain that includes the ``make`` command.
2. Then, run the following command in the root of the source tree:

   .. code-block:: bash

     make develop

   This will install all dependencies, run all the tests, and then install the package in editable mode.

3. If you want to skip the testing, you can run `make package` first, and then manually install the package in editable mode:

   .. code-block:: bash

     make package
     python3 -m pip install -e .


The MMIF format and specification is evolving over time, and ``mmif-python`` package will be updated along with the changes in MMIF format. 

.. note:: MMIF format is not always backward-compatible. To find out more about relations between MMIF specification versions and ``mmif-python`` versions, please take time to read our decision on the subject `here <https://mmif.clams.ai/versioning/>`_. If you need to know which python SDK supports which specification version, see :ref:`target-versions` page. 

MMIF Serialization
---------------------------

:class:`mmif.serialize.mmif.Mmif` represents the top-level MMIF object. For subcomponents of the MMIF (view objects, annotation objects, metadata for each object) are all subclass of :class:`mmif.serialize.model.MmifObject`, including the :class:`mmif.serialize.mmif.Mmif`. To start with an existing MMIF :class:`str`, simple initiate a new ``Mmif`` object with the file. 

.. code-block:: python 

  import mmif
  from mmif import Mmif

  mmif_str = """{
  "metadata": {
    "mmif": "http://mmif.clams.ai/1.0.0"
  },
  "documents": [
    {
      "@type": "http://mmif.clams.ai/vocabulary/VideoDocument/v1",
      "properties": {
        "id": "m1",
        "mime": "video/mp4",
        "location": "file:///var/archive/video-0012.mp4"
      }
    },
    {
      "@type": "http://mmif.clams.ai/vocabulary/TextDocument/v1",
      "properties": {
        "id": "m2",
        "mime": "text/plain",
        "location": "file:///var/archive/video-0012-transcript.txt"
      }
    }
  ],
  "views": []}"""
  mmif_obj = Mmif(mmif_str)


Few notes; 

#. MMIF does not carry the primary source files in it. 
#. MMIF encode the specification version at the top. As not all MMIF versions are backward-compatible, a version ``mmif-python`` implementation of the MMIF might not be able to load an unsupported version of MMIF string. 

When serializing back to :class:`str`, call :meth:`mmif.serialize.model.MmifObject.serialize` on the object. 

To get subcomponents, you can use various getters implemented in subclasses. For example; 

.. code-block:: python 

  from mmif.vocabulary.document_types import DocumentTypes

  for video in mmif_obj.Mmif.get_documents_by_type(DocumentTypes.VideoDocument):
    with open(video.location_path(), 'b') as in_video:
      # do something with the video file


For a full list of available helper methods, please refer to :ref:`the API documentation <apidoc>`. 

