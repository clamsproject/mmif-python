# Shim: re-export vocabulary types from clams-vocabulary package.
# This preserves all existing `from mmif.vocabulary import ...` patterns.

from clams_vocabulary.base import (
    ThingTypesBase,
    ClamsTypesBase,
    AnnotationTypesBase,
    DocumentTypesBase,
)
from clams_vocabulary import AnnotationTypes, DocumentTypes, ThingType

# Merged _typevers (consumed by mmif/__init__.py via star import)
_typevers = {
    **ThingType._typevers,
    **AnnotationTypes._typevers,
    **DocumentTypes._typevers,
}
