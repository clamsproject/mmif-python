"""
The :mod:`annotation` module contains the classes used to represent a
MMIF annotation as a live Python object.

In MMIF, annotations are created by apps in a pipeline as a part
of a view. For documentation on how views are represented, see
:mod:`mmif.serialize.view`.
"""

import pathlib
from typing import Union, Dict, List, Type
from urllib.parse import urlparse

from pyrsistent import pmap, pvector

from mmif.vocabulary import ThingTypesBase, DocumentTypesBase
from .model import FreezableMmifObject

__all__ = ['Annotation', 'AnnotationProperties', 'Document', 'DocumentProperties', 'Text']

JSON_COMPATIBLE_PRIMITIVES: Type = Union[str, int, float, bool, None]


class Annotation(FreezableMmifObject):
    """
    MmifObject that represents an annotation in a MMIF view.
    """

    def __init__(self, anno_obj: Union[bytes, str, dict] = None) -> None:
        self._type: ThingTypesBase = ThingTypesBase('')
        if not hasattr(self, 'properties'):  # don't overwrite DocumentProperties on super() call
            self.properties: AnnotationProperties = AnnotationProperties()
            self._attribute_classes = pmap({'properties': AnnotationProperties})
        self.disallow_additional_properties()
        self._required_attributes = pvector(["_type", "properties"])
        super().__init__(anno_obj)
    
    def _deserialize(self, input_dict: dict) -> None:
        self.at_type = input_dict.pop('_type')
        # TODO (krim @ 6/1/21): If annotation IDs must follow a certain string format,
        # (e.g. currently auto-generated IDs will always have "prefix"_"number" format)
        # here is the place to parse formatted IDs and store prefixes in the parent mmif object. 
        # (see https://github.com/clamsproject/mmif/issues/64#issuecomment-849241309 for discussion)
        super()._deserialize(input_dict)
        
    def is_type(self, at_type: Union[str, ThingTypesBase]) -> bool:
        """
        Check if the @type of this object matches.
        """
        return self.at_type == at_type

    @property
    def at_type(self) -> ThingTypesBase:
        return self._type

    @at_type.setter
    def at_type(self, at_type: Union[str, ThingTypesBase]) -> None:
        if isinstance(at_type, str):
            self._type = ThingTypesBase.from_str(at_type)
        else:
            self._type = at_type

    @property
    def id(self) -> str:
        return self.properties.id

    @id.setter
    def id(self, aid: str) -> None:
        self.properties.id = aid

    def add_property(self, name: str,
                     value: Union[JSON_COMPATIBLE_PRIMITIVES,
                                  List[JSON_COMPATIBLE_PRIMITIVES],
                                  List[List[JSON_COMPATIBLE_PRIMITIVES]]
                    ]) -> None:
        """
        Adds a property to the annotation's properties.
        :param name: the name of the property
        :param value: the property's desired value
        :return: None
        """
        json_primitives = lambda x:isinstance(x, JSON_COMPATIBLE_PRIMITIVES.__args__)
        if json_primitives(value) or (
                isinstance(value,list)
                and all(map(json_primitives, value)) or (
                        all(map(lambda elem: isinstance(elem, list), value))
                        and map(json_primitives, [subelem for elem in value for subelem in elem])
                )
        ):
            self.properties[name] = value
        else:
            raise ValueError("Property values cannot be a complex object. It must be "
                             "either string, number, boolean, None, or a list of them."
                             f"(\"{name}\": \"{str(value)}\"")

    def is_document(self):
        return isinstance(self.at_type, DocumentTypesBase)


class Document(Annotation):
    """
    Document object that represents a single document in a MMIF file.

    A document is identified by an ID, and contains certain attributes
    and potentially contains the contents of the document itself,
    metadata about how the document was created, and/or a list of
    subdocuments grouped together logically.

    If ``document_obj`` is not provided, an empty Document will be generated.

    :param document_obj: the JSON data that defines the document
    """
    def __init__(self, doc_obj: Union[bytes, str, dict] = None) -> None:
        self._parent_view_id = ''
        self._type: Union[str, DocumentTypesBase] = ''
        self.properties: DocumentProperties = DocumentProperties()
        self.disallow_additional_properties()
        self._attribute_classes = pmap({'properties': DocumentProperties})
        super().__init__(doc_obj)

    @property
    def parent(self) -> str:
        return self._parent_view_id

    @parent.setter
    def parent(self, parent_view_id: str) -> None:
        # I want to make this to accept `View` object as an input too,
        # but import `View` will break the code due to circular imports
        self._parent_view_id = parent_view_id

    def add_property(self, name: str,
                     value: Union[JSON_COMPATIBLE_PRIMITIVES,
                                  List[JSON_COMPATIBLE_PRIMITIVES]]) -> None:
        if name == "text":
            self.properties.text = Text(value)
        elif name == "location":
            self.location = value
        else:
            super().add_property(name, value)

    @property
    def text_language(self) -> str:
        return self.properties.text_language

    @text_language.setter
    def text_language(self, lang_code: str) -> None:
        self.properties.text_language = lang_code

    @property
    def text_value(self) -> str:
        return self.properties.text_value

    @text_value.setter
    def text_value(self, text_value: str) -> None:
        self.properties.text_value = text_value

    @property
    def location(self) -> str:
        return self.properties.location

    @location.setter
    def location(self, location: str) -> None:
        self.properties.location = location

    def location_scheme(self) -> str:
        return self.properties.location_scheme()

    def location_address(self) -> str:
        return self.properties.location_address()

    def location_path(self) -> str:
        return self.properties.location_path()


class AnnotationProperties(FreezableMmifObject):
    """
    AnnotationProperties object that represents the
    ``properties`` object within a MMIF annotation.

    :param mmif_obj: the JSON data that defines the properties
    """

    def __init__(self, mmif_obj: Union[bytes, str, dict] = None) -> None:
        self.id: str = ''
        self._required_attributes = pvector(["id"])
        super().__init__(mmif_obj)


class DocumentProperties(AnnotationProperties):
    """
    DocumentProperties object that represents the
    ``properties`` object within a MMIF document.

    :param mmif_obj: the JSON data that defines the properties
    """

    def __init__(self, mmif_obj: Union[bytes, str, dict] = None) -> None:
        self.mime: str = ''
        # note the trailing underscore here. I wanted to use the name `location`
        # for @property in this class and `Document` class, so had to use a diff
        # name for the variable. See `_serialize()` and `_deserialize()` below
        # to see how this exception is handled
        self.location_: str = ''
        self.text: Text = Text()
        self._attribute_classes = pmap({'text': Text})
        # in theory, either `location` or `text` should appear in a `document`
        # but with current implementation, there's no easy way to set a condition 
        # for `oneOf` requirement 
        # see MmifObject::_required_attributes in model.py 
        super().__init__(mmif_obj)

    def _deserialize(self, input_dict: dict) -> None:
        if "location" in input_dict:
            self.location = input_dict.pop("location")
        super()._deserialize(input_dict)

    def _serialize(self, alt_container: Dict = None) -> dict:
        serialized = super()._serialize()
        if "location_" in serialized:
            serialized["location"] = serialized.pop("location_")
        return serialized


    @property
    def text_language(self) -> str:
        return self.text.lang

    @text_language.setter
    def text_language(self, lang_code: str) -> None:
        self.text.lang = lang_code

    @property
    def text_value(self) -> str:
        return self.text.value

    @text_value.setter
    def text_value(self, s: str) -> None:
        self.text.value = s

    @property
    def location(self) -> str:
        return self.location_

    @location.setter
    def location(self, location: str) -> None:
        parsed_location = urlparse(location)
        if parsed_location.scheme is None or len(parsed_location.scheme) == 0:
            self.location_ = pathlib.Path(location).as_uri()
        else:
            self.location_ = location

    def location_scheme(self) -> str:
        return urlparse(self.location).scheme

    def location_address(self) -> str:
        parsed_location = urlparse(self.location)
        if len(parsed_location.netloc) == 0:
            return parsed_location.path
        else:
            return "".join((parsed_location.netloc, parsed_location.path))

    def location_path(self) -> str:
        return urlparse(self.location).path


class Text(FreezableMmifObject):

    def __init__(self, text_obj: Union[bytes, str, dict] = None) -> None:
        self._value: str = ''
        self._language: str = ''
        self.disallow_additional_properties()
        self._required_attributes = pvector(["_value"])
        super().__init__(text_obj)

    @property
    def lang(self) -> str:
        return self._language

    @lang.setter
    def lang(self, lang_code: str) -> None:
        # TODO (krim @ 8/11/20): add validation for language code (ISO 639)
        self._language = lang_code

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, s: str) -> None:
        self._value = s

