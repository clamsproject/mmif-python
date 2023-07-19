"""
The :mod:`annotation` module contains the classes used to represent a
MMIF annotation as a live Python object.

In MMIF, annotations are created by apps in a pipeline as a part
of a view. For documentation on how views are represented, see
:mod:`mmif.serialize.view`.
"""
import importlib
import itertools
import os
import pathlib
import pkgutil
import re
import typing
import warnings
from typing import Union, Dict, List, Optional, Iterator, MutableMapping, TypeVar
from urllib.parse import urlparse

from mmif.vocabulary import ThingTypesBase, DocumentTypesBase
from .model import MmifObject, JSON_PRMTV_TYPES

__all__ = ['Annotation', 'AnnotationProperties', 'Document', 'DocumentProperties', 'Text']

T = TypeVar('T')

from .. import DocumentTypes, AnnotationTypes

discovered_docloc_plugins = {
    name[len('mmif_docloc_'):]: importlib.import_module(name) for _, name, _ in pkgutil.iter_modules() if re.match(r'mmif[-_]docloc[-_]', name)
}


class Annotation(MmifObject):
    """
    MmifObject that represents an annotation in a MMIF view.
    """

    def __init__(self, anno_obj: Optional[Union[bytes, str, dict]] = None) -> None:
        self._type: ThingTypesBase = ThingTypesBase('')
        # to store the parent view ID
        self._parent_view_id = ''
        self.reserved_names.add('_parent_view_id')
        if not hasattr(self, 'properties'):  # don't overwrite DocumentProperties on super() call
            self.properties: AnnotationProperties = AnnotationProperties()
            self._attribute_classes = {'properties': AnnotationProperties}
        self.disallow_additional_properties()
        self._required_attributes = ["_type", "properties"]
        super().__init__(anno_obj)
    
    def _deserialize(self, input_dict: dict) -> None:
        self.at_type = input_dict.pop('_type', '')
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
    def parent(self) -> str:
        return self._parent_view_id

    @parent.setter
    def parent(self, parent_view_id: str) -> None:
        # I want to make this to accept `View` object as an input too,
        # but import `View` will break the code due to circular imports
        self._parent_view_id = parent_view_id

    @property
    def id(self) -> str:
        return self.properties.id

    @id.setter
    def id(self, aid: str) -> None:
        self.properties.id = aid
        
    @staticmethod
    def check_prop_value_is_simple_enough(
            value: Union[JSON_PRMTV_TYPES, List[JSON_PRMTV_TYPES], List[List[JSON_PRMTV_TYPES]]]):
        def json_primitives(x): 
            return isinstance(x, typing.get_args(JSON_PRMTV_TYPES))
        return json_primitives(value) \
            or (isinstance(value, list) and all(map(json_primitives, value))) \
            or (all(map(lambda elem: isinstance(elem, list), value)) and map(json_primitives, [subelem for elem in value for subelem in elem]))

    def add_property(self, name: str,
                     value: Union[JSON_PRMTV_TYPES, List[JSON_PRMTV_TYPES], List[List[JSON_PRMTV_TYPES]]]
                     ) -> None:
        """
        Adds a property to the annotation's properties.
        :param name: the name of the property
        :param value: the property's desired value
        :return: None
        """
        if self.check_prop_value_is_simple_enough(value):
            self.properties[name] = value
        else:
            raise ValueError("Property values cannot be a complex object. It must be "
                             "either string, number, boolean, None, or a list of them."
                             f"(\"{name}\": \"{str(value)}\"")

    def get(self, prop_name: str) -> Union['AnnotationProperties', JSON_PRMTV_TYPES, List[JSON_PRMTV_TYPES], List[List[JSON_PRMTV_TYPES]]]:
        """
        A special getter for Annotation properties. This is to allow for
        directly accessing properties without having to go through the
        properties object.
        """
        if prop_name in {'at_type', '@type'}:
            return str(self._type)
        elif prop_name == 'properties':
            return self.properties
        elif prop_name in self.properties:
            return self.properties[prop_name]
        else:
            raise KeyError(f"Property {prop_name} does not exist in this annotation.")

    get_property = get

    def __getitem__(self, prop_name: str):
        return self.get(prop_name)
    
    def __contains__(self, item):
        try:
            self.get(item)
            return True
        except KeyError:
            return False
    
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
    def __init__(self, doc_obj: Optional[Union[bytes, str, dict]] = None) -> None:
        # see https://github.com/clamsproject/mmif-python/issues/226 for discussion
        # around the use of these three dictionaries
        self._props_original: DocumentProperties = DocumentProperties()
        self._props_existing: AnnotationProperties = AnnotationProperties()
        self._props_temporary: AnnotationProperties = AnnotationProperties()
        self.reserved_names.update(('_props_original', '_props_existing', '_props_temporary'))
        
        self._type: Union[ThingTypesBase, DocumentTypesBase] = ThingTypesBase('')
        self.properties = self._props_original
        self.disallow_additional_properties()
        self._attribute_classes = {'properties': DocumentProperties}
        super().__init__(doc_obj)
    
    def _add_property_from_annotation(self, annotation: Annotation):
        if annotation.at_type != AnnotationTypes.Annotation:
            raise ValueError("Only `Annotation` type can be added as a property to a `Document` object.")
        for prop_name, prop_value in annotation.properties.items():
            self._props_existing[prop_name] = prop_value

    def add_property(self, name: str,
                     value: Union[JSON_PRMTV_TYPES, List[JSON_PRMTV_TYPES]]
                     ) -> None:
        """
        Adds a property to the document's properties.
        
        Unlike the parent :class:`Annotation` class, added properties of a 
        ``Document`` object can be lost during serialization unless it belongs 
        to somewhere in a ``Mmif`` object. This is because we want to keep 
        ``Document`` object as "read-only" as possible. Thus, if you want to add 
        a property to a ``Document`` object, 
        
        * add the document to a ``Mmif`` object (either in the documents list or 
          in a view from the views list), or
        * directly write to ``Document.properties`` instead of using this method
          (which is not recommended). 
        
        With the former method, the SDK will record the added property as a 
        `Annotation` annotation object, separate from the original `Document` 
        object. See :meth:`.Mmif.generate_capital_annotations()` for more.
        
        A few notes to keep in mind:
        
        #. You can't overwrite an existing property of a ``Document`` object. 
        #. A MMIF can have multiple ``Annotation`` objects with the same 
           property name but different values. When this happens, the SDK will
           only keep the latest value (in order of appearances in views list) of 
           the property, effectively overwriting the previous values.
        """
        if name == "text":
            self.properties.text = Text(value)
        elif name == "mime":
            self.properties.mime = str(value)
        elif name == "location":
            self.location = value
        elif name not in self._props_original:
            if self.check_prop_value_is_simple_enough(value):
                self._props_temporary[name] = value
            else:
                super().add_property(name, value)

    def get(self, prop_name):
        """
        A special getter for Document properties. This is to allow for reading 
        the three properties in a specific order so that the latest value is 
        returned, in case there are multiple values for the same key.
        """
        if prop_name == 'id':
            # because all three dicts have `id` key as required field, we need
            # this special case to return the correct value from the correct dict
            return self.id
        elif prop_name == 'location':
            # because location is internally stored in self.location_,
            # it doesn't work with regular __getitem__ method
            return self.location
        elif prop_name in self._props_temporary:
            return self._props_temporary[prop_name]
        elif prop_name in self._props_existing:
            return self._props_existing[prop_name]
        else:
            return super().get(prop_name)

    get_property = get
    
    @property
    def text_language(self) -> str:
        if self.at_type == DocumentTypes.TextDocument:
            return self.properties.text_language
        else:
            raise ValueError("Only TextDocument can have `text` field.")

    @text_language.setter
    def text_language(self, lang_code: str) -> None:
        if self.at_type == DocumentTypes.TextDocument:
            self.properties.text_language = lang_code
        else:
            raise ValueError("Only TextDocument can have `text` field.")

    @property
    def text_value(self) -> str:
        if self.at_type == DocumentTypes.TextDocument:
            if self.location:
                if self.location_scheme() == 'file':
                    f = open(self.location_path(), 'r', encoding='utf8')
                    textvalue = f.read()
                    f.close()
                    return textvalue
                else: 
                    # TODO (krim @ 7/11/21): add more handlers for other types of locations (e.g. s3, https, ...)
                    return ''
            else:
                return self.properties.text_value
        else:
            raise ValueError("Only TextDocument can have `text` field.")

    @text_value.setter
    def text_value(self, text_value: str) -> None:
        if self.at_type == DocumentTypes.TextDocument:
            self.properties.text_value = text_value
        else:
            raise ValueError("Only TextDocument can have `text` field.")

    @property
    def location(self) -> Optional[str]:
        """
        ``location`` property must be a legitimate URI. That is, should the document be a local file
        then the file:// scheme must be used.
        Returns None when no location is set.
        """
        return self.properties.location

    @location.setter
    def location(self, location: str) -> None:
        self.properties.location = location

    def location_scheme(self) -> Optional[str]:
        """
        Retrieves URI scheme of the document location.
        Returns None when no location is set.
        """
        return self.properties.location_scheme()

    def location_address(self) -> Optional[str]:
        """
        Retrieves the full address from the document location URI.
        Returns None when no location is set.
        """
        return self.properties.location_address()

    def location_path(self) -> Optional[str]:
        """
        Retrieves a path that's resolved to a pathname in the local file system.
        To obtain the original value of the "path" part in the location string
        (before resolving), use ``properties.location_path_literal`` method.
        Returns None when no location is set.
        """
        return self.properties.location_path_resolved()


class AnnotationProperties(MmifObject, MutableMapping[str, T]):
    """
    AnnotationProperties object that represents the
    ``properties`` object within a MMIF annotation.

    :param mmif_obj: the JSON data that defines the properties
    """

    def __delitem__(self, key: str) -> None:
        for k in self.__iter__():
            if k == key:
                if k not in self._required_attributes:
                    del self.__dict__[k]
                else:
                    raise AttributeError(f'Cannot delete a required attribute "{key}"!')
        raise KeyError(f'Key "{key}" not found.')
                
    def __iter__(self) -> Iterator[str]:
        """
        ``__iter__`` on Mapping should basically work as ``keys()`` method of vanilla dict
        however, when MMIF objects are serialized, all optional (not in ``_req_atts``),
        empty props are ignored (note that emtpy but required props are serialized 
        with the *emtpy* value). 
        Hence, this ``__iter__`` method should also work in the same way and 
        ignore empty optional props. 
        """
        for key in itertools.chain(self._named_attributes(), self._unnamed_attributes):
            if key in self._required_attributes:
                yield key
            else:
                try:
                    self.__getitem__(key)
                    yield key
                except KeyError:
                    pass

    def __init__(self, mmif_obj: Optional[Union[bytes, str, dict]] = None) -> None:
        self.id: str = ''
        self._required_attributes = ["id"]
        super().__init__(mmif_obj)


class DocumentProperties(AnnotationProperties):
    """
    DocumentProperties object that represents the
    ``properties`` object within a MMIF document.

    :param mmif_obj: the JSON data that defines the properties
    """

    def __init__(self, mmif_obj: Optional[Union[bytes, str, dict]] = None) -> None:
        self.mime: str = ''
        # note the trailing underscore here. I wanted to use the name `location`
        # for @property in this class and `Document` class, so had to use a diff
        # name for the variable. See `_serialize()` and `_deserialize()` below
        # to see how this exception is handled
        self.location_: str = ''
        self.text: Text = Text()
        self._attribute_classes = {'text': Text}
        # in theory, either `location` or `text` should appear in a `document`
        # but with current implementation, there's no easy way to set a condition 
        # for `oneOf` requirement 
        # see MmifObject::_required_attributes in model.py 
        super().__init__(mmif_obj)

    def _deserialize(self, input_dict: dict) -> None:
        if "location" in input_dict:
            self.location = input_dict.pop("location")
        super()._deserialize(input_dict)

    def _serialize(self, alt_container: Optional[Dict] = None) -> dict:
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
    def location(self) -> Optional[str]:
        """
        ``location`` property must be a legitimate URI. That is, should the document be a local file 
        then the file:// scheme must be used. 
        Returns None when no location is set.
        """
        return self.location_ if len(self.location_) > 0 else None

    @location.setter
    def location(self, location: str) -> None:
        parsed_location = urlparse(location)
        if parsed_location.scheme is None or len(parsed_location.scheme) == 0:
            self.location_ = pathlib.Path(location).as_uri()
        else:
            self.location_ = location

    def location_scheme(self) -> Optional[str]:
        """
        Retrieves URI scheme of the document location.
        Returns None when no location is set.
        """
        if self.location is None:
            return None
        return urlparse(self.location).scheme

    def location_address(self) -> Optional[str]:
        """
        Retrieves the full address from the document location URI.
        Returns None when no location is set.
        """
        if self.location is None:
            return None
        parsed_location = urlparse(self.location)
        if len(parsed_location.netloc) == 0:
            return parsed_location.path
        else:
            return "".join((parsed_location.netloc, parsed_location.path))

    def location_path(self) -> Optional[str]:
        warnings.warn('location_path() is deprecated. Use location_path_resolved() instead.', DeprecationWarning)
        return self.location_path_resolved()
    
    def location_path_resolved(self, nonexist_ok=True) -> Optional[str]:
        """
        Retrieves only path name of the document location (hostname is ignored), 
        and then try to resolve the path name in the local file system.
        This method should be used when the document scheme is ``file`` or empty.
        For other schemes, users should install ``mmif-locdoc-<scheme>`` plugin.
        
        Returns None when no location is set.
        Raise ValueError when no code found to resolve the given location scheme.
        """
        if self.location is None:
            return None
        scheme = self.location_scheme()
        if scheme in ('', 'file'):
            p = urlparse(self.location).path
        elif scheme in discovered_docloc_plugins:
            p = discovered_docloc_plugins[scheme].resolve(self.location)
        else:
            raise ValueError(f'Cannot resolve location of scheme "{scheme}". Interested in developing mmif-locdoc-{scheme} plugin? See https://clams.ai/mmif-python/plugins')
        if not nonexist_ok and not os.path.exists(p):
            raise FileNotFoundError(f'Cannot find file "{p}"')
        else:
            return p

    def location_path_literal(self) -> Optional[str]:
        """
        Retrieves only path name of the document location (hostname is ignored). 
        Returns None when no location is set.
        """
        if self.location is None:
            return None
        return urlparse(self.location).path


class Text(MmifObject):

    def __init__(self, text_obj: Optional[Union[bytes, str, dict]] = None) -> None:
        self._value: str = ''
        self._language: str = ''
        self.disallow_additional_properties()
        self._required_attributes = ["_value"]
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

