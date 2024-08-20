"""
Aggregatitive summary for mmif.serialize package:

''Prerequisites'': recall CLAMS MMIF structure at https://mmif.clams.ai/1.0.5/#the-structure-of-mmif-files

The MMIF follows JSON schema which consists of two data structures: dictionary/hash and list.
Therefore, for the purpose of best practice in Python's OOP, MMIF overwrites its own 'dict-like'
and 'list-like' classes.

As a high-level overview of the package, the following parent classes are defined first:

- `MmifObject`: a base class for MMIF objects that are ''dict-like''
- `DataList`: a base class for MMIF data fields that are ''list-like''
- `DataDict`: a base class for MMIF data fields that are ''dict-like''

Then, the following classes are defined and categorized into either ''dict-like''
or ''list-like'' child classes:

'''dict-like''':
    - `Mmif`: a class for MMIF objects
    - `MmifMetaData`: a class for MMIF metadata
    - `View`: a class for MMIF view
    - `ViewMetaData`: a class for MMIF view metadata
    - `ErrorDict`: a class for a specific view that contains error
    - `ContainsDict`: a class for `View`'s 'contains' field
    - `Annotation` & `Document`: a class for MMIF annotation and document
    - `AnnotationProperties` & `DocumentProperties`: a class for MMIF annotation properties
    - `Text`: a class for `Document`'s text field

'''list-like''':
    - `DocumentsList`: a class for a list of `Document` objects
    - `ViewsList`: a class for a list of `View` objects
    - `AnnotationsList`: a class for a list of `Annotation` objects

By doing so, the any field of a ''dict-like'' class should be accessed if and
only if by either bracket `[key]` or `.get(key)`. For a ''list-like'' class, the
elements are ordered and accessed by index, for example, `[idx]`.
"""
from .annotation import *
from .annotation import __all__ as anno_all
from .mmif import *
from .mmif import __all__ as mmif_all
from .view import *
from .view import __all__ as view_all

__all__ = anno_all + mmif_all + view_all
