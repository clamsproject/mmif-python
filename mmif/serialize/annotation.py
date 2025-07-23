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
from typing import Union, Dict, Optional, Iterator, MutableMapping, TypeVar
from urllib.parse import urlparse

from mmif.vocabulary import ThingTypesBase, DocumentTypesBase
from .model import MmifObject, PRMTV_TYPES
from .. import DocumentTypes, AnnotationTypes
import mmif_docloc_http

__all__ = ['Annotation', 'AnnotationProperties', 'Document', 'DocumentProperties', 'Text']

T = TypeVar('T')
LIST_PRMTV = typing.List[PRMTV_TYPES]  # list of values (most cases for annotation props)
LIST_LIST_PRMTV = typing.List[LIST_PRMTV]   # list of lists of values (e.g. for coordinates)
DICT_PRMTV = typing.Dict[str, PRMTV_TYPES]  # dict of values (`text` prop of `TextDocument` and other complex props)
DICT_LIST_PRMTV = typing.Dict[str, LIST_PRMTV]  # dict of list of values (even more complex props)


# some built-in document location helpers
discovered_docloc_plugins = {
    'http': mmif_docloc_http,
    'https': mmif_docloc_http
}
discovered_docloc_plugins.update({
    name[len('mmif_docloc_'):]: importlib.import_module(name) for _, name, _ in pkgutil.iter_modules() if re.match(r'mmif[-_]docloc[-_]', name)
})


class Annotation(MmifObject):
    """
    MmifObject that represents an annotation in a MMIF view.
    """

    def __init__(self, anno_obj: Optional[Union[bytes, str, dict]] = None, *_) -> None:
        self._type: ThingTypesBase = ThingTypesBase('')
        # to store the parent view ID
        self._props_ephemeral: AnnotationProperties = AnnotationProperties()
        self._alignments = {}  # to hold alignment information (Alignment anno long_id -> aligned anno long_id)
        self.reserved_names.update(('_props_ephemeral', '_alignments'))
        if not hasattr(self, 'properties'):  # don't overwrite DocumentProperties on super() call
            self.properties: AnnotationProperties = AnnotationProperties()
            self._attribute_classes = {'properties': AnnotationProperties}
        self.disallow_additional_properties()
        self._required_attributes = ["_type", "properties"]
        super().__init__(anno_obj)
    
    def __hash__(self):
        return hash(self.serialize())
    
    def _deserialize(self, input_dict: dict) -> None:
        self.at_type = input_dict.pop('_type', '')
        # TODO (krim @ 6/1/21): If annotation IDs must follow a certain string format,
        # (e.g. currently auto-generated IDs will always have "prefix"_"number" format)
        # here is the place to parse formatted IDs and store prefixes in the parent mmif object. 
        # (see https://github.com/clamsproject/mmif/issues/64#issuecomment-849241309 for discussion)
        super()._deserialize(input_dict)
        for k, v in self.properties.items():
            self._add_prop_aliases(k, v)
                            
    def _cache_alignment(self, alignment_ann: 'Annotation', alignedto_ann: 'Annotation') -> None:
        """
        Cache alignment information. This cache will not be serialized. 
        
        :param alignment_ann: the Alignment annotation that has this annotation on one side
        :param alignedto_ann: the annotation that this annotation is aligned to (other side of Alignment)
        """
        self._alignments[alignment_ann] = alignedto_ann
    
    def aligned_to_by(self, alignment: 'Annotation') -> Optional['Annotation']:
        """
        Retrieves the other side of ``Alignment`` annotation that has this annotation on one side. 
        
        :param alignment: ``Alignment`` annotation that has this annotation on one side
        :return: the annotation that this annotation is aligned to (other side of ``Alignment``), 
                 or None if this annotation is not used in the ``Alignment``.
        """
        return self._alignments.get(alignment)
    
    def get_all_aligned(self) -> Iterator['Annotation']:
        """
        Generator to iterate through all alignments and aligned annotations. Note that this generator will yield
        the `Alignment` annotations as well. Every odd-numbered yield will be an `Alignment` annotation, and every
        even-numbered yield will be the aligned annotation. If there's a specific annotation type that you're looking
        for, you need to filter the generated results outside. 
        
        :return: yields the alignment annotation and the aligned annotation.
                 The order is decided by the order of appearance of Alignment annotations in the MMIF
        """
        for alignment, aligned in self._alignments.items():
            yield alignment
            yield aligned
        
        
    def _add_prop_aliases(self, key_to_add, val_to_add):
        """
        Method to handle aliases of the same property.
        Annotation property aliases were first introduced in MMIF 1.0.2, 
        with addition of general `label` property to all `Annotation` 
        subtypes, and effectively deprecated `frameType` and `boxType`
        in `TimeFrame` and `BoundingBox` respectively.
        """
        prop_aliases = AnnotationTypes._prop_aliases.get(self._type.shortname, {})
        for alias_rep, alias_group in prop_aliases.items():
            if key_to_add in alias_group:
                for alias in alias_group:
                    if alias != key_to_add:
                        self._props_ephemeral[alias] = val_to_add
                        if alias in self.properties.keys():
                            warning_msg = (f'Both "{key_to_add}" and "{alias}" are in the properties of "{self.id}", '
                                           f'however ')
                            if alias == alias_rep:
                                warning_msg += f'"{key_to_add}" is an alias of "{alias_rep}".'
                            else:
                                warning_msg += f'"{key_to_add}" and "{alias}" are both aliases of "{alias_rep}".'
                            warning_msg += f'Having two synonyms in the same annotation can cause unexpected behavior. '
                            warnings.warn(warning_msg, UserWarning)

    def is_type(self, at_type: Union[str, ThingTypesBase]) -> bool:
        """
        Check if the @type of this object matches.
        """
        if isinstance(at_type, str):
            at_type = ThingTypesBase.from_str(at_type)
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
        if self.id_delimiter in self.properties.id:
            id_split = self.properties.id.split(self.id_delimiter)
            if len(id_split) == 2:
                return id_split[0]
        raise ValueError(f'Annotation {self.id} does not have a parent view, or its ID does not follow the expected format. ')
    
    @parent.setter
    def parent(self, parent_id: str) -> None:
        """
        .. deprecated:: 1.1.0
           Will be removed in 2.0.0. 
           Setting parent ID is no longer allowed. Instead, the parent ID
           should be prefixed to the annotation ID. 
          
        Sets the parent view ID of this annotation.
        :param parent_id: 
        """
        warnings.warn(
            "Setting parent ID is deprecated and nothing happened. Use prefixed annotation ID instead.",
            DeprecationWarning
        )


    @property
    def id(self) -> str:
        return self.properties.id

    @id.setter
    def id(self, aid: str) -> None:
        self.properties.id = aid
        
    @property
    def long_id(self) -> str:
        warnings.warn(
            'long_id is deprecated. Use `id` instead. ', DeprecationWarning
        )
        return self.id
    
    @long_id.setter
    def long_id(self, long_id: str) -> None:
        warnings.warn(
            'long_id is deprecated. Use `id` instead. ', DeprecationWarning
        )
        self.id = long_id
    
    @property
    def _short_id(self) -> str:
        # TODO (krim @ 6/27/25): DELETE THIS METHOD!
        """
        Method to directly get "short" form of the ID, not supposed to be used for general purpose, since 
        we want to force usage of "long" form ID when recording and referring annotations. 
        :return: 
        """
        return self.properties.id
    
    @staticmethod
    def check_prop_value_is_simple_enough(
            value: Union[PRMTV_TYPES, LIST_PRMTV, LIST_LIST_PRMTV, DICT_PRMTV, DICT_LIST_PRMTV]) -> bool:
        
        def json_primitives(x): 
            return isinstance(x, typing.get_args(PRMTV_TYPES))
        
        def json_primitives_list(x):
            return isinstance(x, list) and all(map(json_primitives, x))
        
        def json_primitives_list_of_list(x):
            return all(map(lambda elem: isinstance(elem, list), x) and map(json_primitives, [subelem for elem in x for subelem in elem]))

        return json_primitives(value) \
            or json_primitives_list(value) \
            or json_primitives_list_of_list(value) \
            or (isinstance(value, dict) and all(map(lambda x: isinstance(x[0], str) and (json_primitives(x[1]) or json_primitives_list(x[1])), value.items())))

    def add_property(self, name: str,
                     value: Union[PRMTV_TYPES, LIST_PRMTV, LIST_LIST_PRMTV, DICT_PRMTV, DICT_LIST_PRMTV]) -> None:
        """
        Adds a property to the annotation's properties.
        
        :param name: the name of the property
        :param value: the property's desired value
        :return: None
        """
        # if self.check_prop_value_is_simple_enough(value):
        self.properties[name] = value
        # else:
        #     raise ValueError("Property values cannot be a complex object. It must be "
        #                      "either string, number, boolean, None, a JSON array of them, "
        #                      "or a JSON object of them keyed by strings."
        #                      f"(\"{name}\": \"{str(value)}\"")
        self._add_prop_aliases(name, value)

    def __getitem__(self, prop_name: str):
        if prop_name in {'at_type', '@type'}:
            return str(self._type)
        elif prop_name == 'properties':
            return self.properties
        elif prop_name in self.properties:
            return self.properties[prop_name]
        elif prop_name in self._props_ephemeral:
            return self._props_ephemeral[prop_name]
        else:
            raise KeyError(f"Property {prop_name} does not exist in this annotation.")

    def get(self, prop_name: str, default=None):
        """
        A getter for Annotation, will search for a property by its name, 
        and return the value if found, or the default value if not found.
        This is designed to allow for directly accessing properties without 
        having to go through the properties object, or view-level 
        annotation metadata (common properties) encoded in the 
        ``view.metadata.contains`` dict. Note that the regular properties 
        will take the priority over the view-level common properties when 
        there are name conflicts.
        
        :param prop_name: the name of the property to get
        :param default: the value to return if the property is not found
        :return: the value of the property
        """
        try:
            return self.__getitem__(prop_name)
        except KeyError:
            return default

    get_property = get

    def __contains__(self, item):
        try:
            self.__getitem__(item)
            return True
        except KeyError:
            return False
    
    def _get_label(self) -> str:
        """
        Another prototypical method to handle property aliases.
        See :meth:`.Annotation._add_prop_aliases` for more details on 
        what property aliases are.
        Not recommended to use this method as `_add_prop_aliases` method 
        is preferred. 
        """
        if 'label' in self:
            return str(self.get('label'))
        elif self._type.shortname == 'TimeFrame' and 'frameType' in self:
            return str(self.get('frameType'))
        elif self._type.shortname == 'BoundingBox' and 'boxType' in self:
            return str(self.get('boxType'))
        else:
            raise KeyError("No label found in this annotation.")
    
    def is_document(self):
        return isinstance(self._type, DocumentTypesBase)


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
    def __init__(self, doc_obj: Optional[Union[bytes, str, dict]] = None, *_) -> None:
        # see https://github.com/clamsproject/mmif-python/issues/226 for discussion
        # around the use of these three dictionaries
        # (names changed since, `existing` >> `ephemeral` and `temporary` >> `pending`)
        self._props_original: DocumentProperties = DocumentProperties()
        self._props_pending: AnnotationProperties = AnnotationProperties()
        self.reserved_names.update(('_props_original', '_props_pending'))
        
        self._type: Union[ThingTypesBase, DocumentTypesBase] = ThingTypesBase('')
        self.properties = self._props_original
        self.disallow_additional_properties()
        self._attribute_classes = {'properties': DocumentProperties}
        super().__init__(doc_obj)
    
    def add_property(self, name: str,
                     value: Union[PRMTV_TYPES, LIST_PRMTV]
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
        # we don't checking if this k-v already exists in _original (new props) or _ephemeral (read from existing MMIF)
        # because it is impossible to keep the _original updated when a new annotation is added (via `new_annotation`)
        # without look across other views and top-level documents list. Also see 
        # ``mmif.serialize.mmif.Mmif.generate_capital_annotations`` for where the "de-duplication" happens.
        if name == "text":
            self.properties.text = Text(value)
        elif name == "mime":
            self.properties.mime = str(value)
        elif name == "location":
            self.location = value
        elif name not in self._props_original:
            if self.check_prop_value_is_simple_enough(value):
                self._props_pending[name] = value
            else:
                super().add_property(name, value)

    def get(self, prop_name, default=None):
        """
        A special getter for Document properties. The major difference from
        the super class's :py:meth:`Annotation.get` method is that Document 
        class has one more set of *"pending"* properties, that are added after 
        the Document object is created and will be serialized as a separate 
        :py:class:`Annotation` object of which ``@type = Annotation``. The 
        pending properties will take the priority over the regular properties 
        when there are conflicts.
        """
        if prop_name == 'id':
            # because all three dicts have `id` key as required field, we need
            # this special case to return the correct value from the correct dict
            return self.id
        elif prop_name == 'location':
            # because location is internally stored in self.location_,
            # it doesn't work with regular __getitem__ method
            return self.location
        elif prop_name in self._props_pending:
            return self._props_pending[prop_name]
        elif prop_name in self._props_ephemeral:
            return self._props_ephemeral[prop_name]
        else:
            return super().get(prop_name)

    get_property = get
    
    @property
    def text_language(self) -> str:
        if self._type == DocumentTypes.TextDocument:
            return self.properties.text_language
        else:
            raise ValueError("Only TextDocument can have `text` field.")

    @text_language.setter
    def text_language(self, lang_code: str) -> None:
        if self._type == DocumentTypes.TextDocument:
            self.properties.text_language = lang_code
        else:
            raise ValueError("Only TextDocument can have `text` field.")

    @property
    def text_value(self) -> str:
        if self._type == DocumentTypes.TextDocument:
            if self.location:
                f = open(self.location_path(nonexist_ok=False), 'r', encoding='utf8')
                textvalue = f.read()
                f.close()
                return textvalue
            else:
                return self.properties.text_value
        else:
            raise ValueError("Only TextDocument can have `text` field.")

    @text_value.setter
    def text_value(self, text_value: str) -> None:
        if self._type == DocumentTypes.TextDocument:
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

    def location_path(self, nonexist_ok=True) -> Optional[str]:
        """
        Retrieves a path that's resolved to a pathname in the local file system.
        To obtain the original value of the "path" part in the location string
        (before resolving), use ``properties.location_path_literal`` method.
        Returns None when no location is set.
        
        :param nonexist_ok: if False, raise FileNotFoundError when the resolved path doesn't exist
        """
        return self.properties.location_path_resolved(nonexist_ok=nonexist_ok)


class AnnotationProperties(MmifObject, MutableMapping[str, T]):
    """
    AnnotationProperties object that represents the
    ``properties`` object within a MMIF annotation.

    :param mmif_obj: the JSON data that defines the properties
    """

    def __delitem__(self, key: str) -> None:
        frm = None
        for k in self.__iter__():
            if k == key:
                if k in self._required_attributes:
                    raise AttributeError(f'Cannot delete a required attribute "{key}"!')
                elif k in self._unnamed_attributes:
                    frm = self._unnamed_attributes
                    break
                else:
                    frm = self.__dict__
                    break
        if frm is not None:
            del frm[key]
        else:
            raise KeyError(f'Key "{key}" not found.')
                
    def __iter__(self) -> Iterator[str]:
        """
        ``__iter__`` on Mapping should basically work as ``keys()`` method 
        of vanilla dict.
        """
        for key in itertools.chain(self._named_attributes(), self._unnamed_attributes):
            yield key
                
    def __getitem__(self, key):
        """
        Parent MmifObject class has a __getitem__ method that checks if 
        the value is empty when asked for an unnamed attribute. But for 
        AnnotationProperties, any arbitrary property that's added 
        explicitly by the user (developer) should not be ignored and 
        returned even the value is empty. 
        """
        if key in self._named_attributes():
            return self.__dict__[key]
        else:
            return self._unnamed_attributes[key]

    def __init__(self, mmif_obj: Optional[Union[bytes, str, dict]] = None, *_) -> None:
        self.id: str = ''
        # any individual at_type (subclassing this class) can have its own set of required attributes
        self._required_attributes = ["id"]
        # allowing additional attributes for arbitrary annotation properties
        self._unnamed_attributes = {}
        super().__init__(mmif_obj)


class DocumentProperties(AnnotationProperties):
    """
    DocumentProperties object that represents the
    ``properties`` object within a MMIF document.

    :param mmif_obj: the JSON data that defines the properties
    """

    def __init__(self, mmif_obj: Optional[Union[bytes, str, dict]] = None, *_) -> None:
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
        """
        .. deprecated:: 1.0.2
           Will be removed in 2.0.0. 
           Use :meth:`location_path_resolved` instead.
        """
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

    def __init__(self, text_obj: Optional[Union[bytes, str, dict]] = None, *_) -> None:
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

