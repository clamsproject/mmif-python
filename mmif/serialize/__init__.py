"""
Core package to provide serialization and deserialization of MMIF format.
"""

from .annotation import *
from .mmif import *
from .producer import *
from .view import *

# a literal, so that type checkers can follow the star import of this package
__all__ = [
    'Annotation', 'AnnotationProperties', 'Contain', 'Document',
    'DocumentProperties', 'EmptyOutputWarning', 'Mmif', 'ProducerContext',
    'Text', 'View', 'ViewMetadata', 'canonicalize_prop_name',
]
