"""
The :mod:`view` module contains the classes used to represent a MMIF view
as a live Python object.

In MMIF, views are created by apps in a pipeline that are annotating
data that was previously present in the MMIF file.
"""
import json
import warnings
from datetime import datetime
from typing import Dict, Union, Optional, Generator, List, cast

from mmif import DocumentTypes, AnnotationTypes, ThingTypesBase, ClamsTypesBase
from mmif.serialize.annotation import Annotation, Document
from mmif.serialize.model import PRMTV_TYPES, MmifObject, DataList, DataDict
from mmif.vocabulary.base_types import AnnotationTypesBase

__all__ = ['View', 'ViewMetadata', 'Contain']


class View(MmifObject):
    """
    View object that represents a single view in a MMIF file.

    A view is identified by an ID, and contains certain metadata,
    a list of annotations, and potentially a JSON-LD ``@context``
    IRI.

    If ``view_obj`` is not provided, an empty View will be generated.

    :param view_obj: the JSON data that defines the view
    """

    def __init__(self, view_obj: Optional[Union[bytes, str, dict]] = None, parent_mmif=None, *_) -> None:
        # used to autogenerate annotation ids
        self._id_counts = {}
        # used to access the parent MMIF object
        self._parent_mmif = parent_mmif
        self.reserved_names.update(("_parent_mmif", "_id_counts"))
        self._exclude_from_diff = {"_id_counts"}
        
        self.id: str = ''
        self.metadata: ViewMetadata = ViewMetadata()
        self.annotations: AnnotationsList = AnnotationsList()
        self.disallow_additional_properties()
        self._attribute_classes = {
            'metadata': ViewMetadata,
            'annotations': AnnotationsList
        }
        self._required_attributes = ["id", "metadata", "annotations"]
        super().__init__(view_obj)
        self._fix_old_short_ids()

    def _fix_old_short_ids(self):
        """
        to "update" old MMIF files that used "short" form of annotation IDs
        this will prepend the view ID to all annotation IDs, then persist 
        in the serialized MMIF file as well.
        """
        aids = list(self.annotations._items.keys())
        for aid in aids:
            if self.id_delimiter not in aid:
                # this is a short ID, prepend the view ID
                annotation = self.annotations._items.pop(aid)
                # first fix the ID assignment
                annotation.id = f"{self.id}{self.id_delimiter}{aid}"
                # then fix ID references; the prop keys here is NOT an exhaustive list,
                # hence need ad-hoc fixes in the future if we find more props used in the past
                # string references 
                mmif_docs = set(self._parent_mmif.documents._items.keys()) if self._parent_mmif else set()
                for propk in 'document source target'.split():
                    if propk in self.metadata.contains.get(annotation.at_type, {}):
                        propv = self.metadata.contains[annotation.at_type][propk]
                        if propv not in mmif_docs and self.id_delimiter not in propv:
                            self.metadata.contains[annotation.at_type][propk] = f"{self.id}{self.id_delimiter}{propv}"
                    if propk in annotation.properties:
                        propv = annotation.properties[propk]
                        if propv not in mmif_docs and self.id_delimiter not in propv:
                            annotation.properties[propk] = f"{self.id}{self.id_delimiter}{propv}"
                # list of string references
                for propk in 'targets representatives'.split():
                    if propk in self.metadata.contains.get(annotation.at_type, {}):
                        propv = self.metadata.contains[annotation.at_type][propk]
                        if isinstance(propv, list):
                            for i, item in enumerate(propv):
                                if item not in mmif_docs and self.id_delimiter not in item:
                                    propv[i] = f"{self.id}{self.id_delimiter}{item}"
                    if propk in annotation.properties:
                        propv = annotation.properties[propk]
                        if isinstance(propv, list):
                            for i, item in enumerate(propv):
                                if item not in mmif_docs and self.id_delimiter not in item:
                                    propv[i] = f"{self.id}{self.id_delimiter}{item}"
                self.annotations.append(annotation)

    def new_contain(self, at_type: Union[str, ThingTypesBase], **contains_metadata) -> Optional['Contain']:
        """
        Adds a new element to the ``contains`` metadata.

        :param at_type: the ``@type`` of the annotation type being added
        :param contains_metadata: any metadata associated with the annotation type
        :return: the generated :class:`Contain` object
        """
        if MmifObject.is_empty(at_type):
            raise ValueError("@type must not be empty.")
        else:
            return self.metadata.new_contain(at_type, **contains_metadata)
    
    def _set_ann_id(self, annotation: Annotation, identifier):
        if identifier is not None:
            # this if conditional is for backwards compatibility with 
            # old MMIF files that used short IDs
            # TODO will be removed in 2.0.0
            if self.id_delimiter not in identifier:
                annotation.id = f"{self.id}{self.id_delimiter}{identifier}"
            annotation.id = identifier
        else:
            prefix = annotation.at_type.get_prefix()
            new_num = self._id_counts.get(prefix, 0) + 1
            new_id = f'{prefix}_{new_num}'
            self._id_counts[prefix] = new_num
            annotation.id = self.id + self.id_delimiter + new_id
    
    def new_annotation(self, at_type: Union[str, ThingTypesBase], aid: Optional[str] = None, 
                       overwrite=False, **properties) -> 'Annotation':
        """
        Generates a new :class:`mmif.serialize.annotation.Annotation`
        object and adds it to the current view.

        Fails if there is already an annotation with the same ID
        in the view, unless ``overwrite`` is set to True.

        :param at_type: the desired ``@type`` of the annotation.
        :param aid: the desired ID of the annotation, when not given, 
                    the mmif SDK tries to automatically generate an ID based on 
                    Annotation type and existing annotations in the view. 
        :param overwrite: if set to True, will overwrite an
                          existing annotation with the same ID.
        :raises KeyError: if ``overwrite`` is set to False and
                          an annotation with the same ID exists
                          in the view.
        :return: the generated :class:`mmif.serialize.annotation.Annotation`
        """
        new_annotation = Annotation()
        new_annotation.at_type = at_type
        self._set_ann_id(new_annotation, aid)
        for propk, propv in properties.items():
            new_annotation.add_property(propk, propv)
        for propk, propv in self.metadata.contains.get(at_type, {}).items():
            new_annotation._props_ephemeral[propk] = propv
        return self.add_annotation(new_annotation, overwrite)

    def add_annotation(self, annotation: 'Annotation', overwrite=False) -> 'Annotation':
        """
        Adds an annotation to the current view.

        Fails if there is already an annotation with the same ID
        in the view, unless ``overwrite`` is set to True.

        :param annotation: the :class:`mmif.serialize.annotation.Annotation`
                           object to add
        :param overwrite: if set to True, will overwrite an
                          existing annotation with the same ID
        :raises KeyError: if ``overwrite`` is set to False and
                          an annotation with the same ID exists
                          in the view
        :return: the same Annotation object passed in as ``annotation``
        """
        if self.id_delimiter not in annotation.id:
            # this is a short ID, prepend the view ID
            annotation.id = f"{self.id}{self.id_delimiter}{annotation.id}"
        self.annotations.append(annotation, overwrite)
        self.new_contain(annotation.at_type)
        if annotation.at_type == AnnotationTypes.Alignment:
            self._parent_mmif._cache_alignment(annotation)
        return annotation
    
    def new_textdocument(self, text: str, lang: str = "en", did: Optional[str] = None, 
                         overwrite=False, **properties) -> 'Document':
        """
        Generates a new :class:`mmif.serialize.annotation.Document`
        object, particularly typed as TextDocument and adds it to the current view.

        Fails if there is already a text document with the same ID
        in the view, unless ``overwrite`` is set to True.

        :param text: text content of the new document
        :param lang: ISO 639-1 code of the language used in the new document
        :param did: the desired ID of the document, when not given, 
                    the mmif SDK tries to automatically generate an ID based on 
                    Annotation type and existing documents in the view. 
        :param overwrite: if set to True, will overwrite an
                          existing document with the same ID
        :raises KeyError: if ``overwrite`` is set to False and
                          an document with the same ID exists
                          in the view
        :return: the generated :class:`mmif.serialize.annotation.Document`
        """
        new_document = Document()
        new_document.at_type = DocumentTypes.TextDocument
        self._set_ann_id(new_document, did)
        new_document.text_language = lang
        new_document.text_value = text
        for propk, propv in properties.items():
            new_document.add_property(propk, propv)
        self.add_document(new_document, overwrite)
        return new_document

    def add_document(self, document: Document, overwrite=False) -> Annotation:
        """
        Appends a Document object to the annotations list.

        Fails if there is already a document with the same ID in the annotations list.

        :param document: the Document object to add
        :param overwrite: if set to True, will overwrite
                          an existing view with the same ID
        :return: None
        """
        return self.add_annotation(document, overwrite)

    def get_annotations(self, at_type: Optional[Union[str, ThingTypesBase]] = None, 
                        **properties) -> Generator[Annotation, None, None]:
        """
        Look for certain annotations in this view, specified by parameters

        :param at_type: @type of the annotations to look for. When this is None, any @type will match.
        :param properties: properties of the annotations to look for. When given more than one property, all properties \
        must match. Note that annotation type metadata are specified in the `contains` view metadata, not in individual \
        annotation objects.
        """
        def prop_check(k, v, *props):
            return any(k in prop and prop[k] == v for prop in props)

        for annotation in self.annotations:
            at_type_metadata = self.metadata.contains.get(annotation.at_type, {})
            if not at_type or (at_type and annotation.at_type == at_type):
                if all(map(lambda kv: prop_check(kv[0], kv[1], annotation.properties, at_type_metadata), 
                           properties.items())):
                    yield annotation
    
    def get_annotation_by_id(self, ann_id) -> Annotation:
        """
        .. deprecated:: 1.1.0
           Will be removed in 2.0.0. 
           Use general ``Mmif.__getitem__()`` method instead to retrieve 
           any annotation across the MMIF, or View.__getitems__() to 
           retrieve annotations within the view.
           
        Thinly wraps the Mmif.__getitem__ method and returns an Annotation 
        object. Note that although this method is under View class, it can 
        be used to retrieve any annotation across the entire MMIF.
        
        :param ann_id: the ID of the annotation to retrieve.
        :return: found :class:`mmif.serialize.annotation.Annotation` object.
        :raises KeyError: if the annotation with the given ID is not found
        """
        warnings.warn(
            "View.get_annotation_by_id() is deprecated, use view[ann_id] instead.",
            DeprecationWarning
        )
        ann_found = self._parent_mmif.__getitem__(ann_id)
        if not isinstance(ann_found, Annotation):
            raise KeyError(f"Annotation with ID {ann_id} not found in the MMIF object.")
        return cast(Annotation, ann_found)
        
    def get_documents(self) -> List[Document]:
        return [cast(Document, annotation) for annotation in self.annotations if annotation.is_document()]

    def get_document_by_id(self, doc_id) -> Document:
        """
        .. deprecated:: 1.1.0
           Will be removed in 2.0.0. 
           Use general ``Mmif.__getitem__()`` method instead to retrieve 
           any document across the MMIF, or View.__getitems__() to 
           retrieve documents within the view.

        Thinly wraps the Mmif.__getitem__ method and returns an Annotation 
        object. Note that although this method is under View class, it can 
        be used to retrieve any annotation across the entire MMIF.

        :param ann_id: the ID of the annotation to retrieve.
        :return: found :class:`mmif.serialize.annotation.Annotation` object.
        :raises KeyError: if the annotation with the given ID is not found
        """
        warnings.warn(
            "View.get_document_by_id() is deprecated, use view[doc_id] instead.",
            DeprecationWarning
        )
        doc_found = self.annotations[doc_id]
        if not isinstance(doc_found, Document):
            raise KeyError(f"Document \"{doc_id}\" not found in view {self.id}.")
        return cast(Document, doc_found)

    def __getitem__(self, key: str) -> 'Annotation':
        """
        index ([]) implementation for View.

        :raises KeyError: if the key is not found
        :param key: the search string.
        :return: the :class:`mmif.serialize.annotation.Annotation` object searched for
        """
        if key in self._named_attributes():
            return self.__dict__[key]
        anno_result = self.annotations.get(key)
        if not anno_result:
            raise KeyError("Annotation ID not found: %s" % key)
        return anno_result
    
    def set_error(self, err_message: str, err_trace: str) -> None:
        self.metadata.set_error(err_message, err_trace)
        self.annotations.empty()
    
    def get_error(self) -> Optional[str]:
        """
        Get the "text" representation of the error occurred during 
        processing. Text representation is supposed to be human-readable. 
        When ths view does not have any error, returns None.
        """
        if self.has_error():
            return self.metadata.get_error_as_text()
        else:
            return None

    def has_error(self) -> bool:
        return self.metadata.has_error()

    def has_warnings(self):
        return self.metadata.has_warnings()


class ViewMetadata(MmifObject):
    """
    ViewMetadata object that represents the ``metadata`` object within a MMIF view.

    :param viewmetadata_obj: the JSON data that defines the metadata
    """

    def __init__(self, viewmetadata_obj: Optional[Union[bytes, str, dict]] = None, *_) -> None:
        self.document: str = ''
        self.timestamp: Optional[datetime] = None
        self.app: str = ''
        self.contains: ContainsDict = ContainsDict()
        self.parameters: Dict[str, str] = {}
        self.appConfiguration: Dict[str, Union[PRMTV_TYPES, List[PRMTV_TYPES]]] = {}
        self.error: Union[dict, ErrorDict] = {}
        self.warnings: List[str] = []
        self._required_attributes = ["app"]
        self._attribute_classes = {
            'error': ErrorDict,
            'contains': ContainsDict
        }
        # in theory, *oneOf* `contains`, `error`, or `warnings` should appear in a `view`
        # but with current implementation, there's no easy way to set a condition 
        # for `oneOf` requirement 
        # see MmifObject::_required_attributes in model.py 
        # also see this class' `_serialize()` override implementation
        super().__init__(viewmetadata_obj)

    def _serialize(self, alt_container: Optional[Dict] = None) -> dict:
        serialized = super()._serialize()
        # `_serialize()` eliminates any *empty* attributes, so 
        # when no "contains", "errors", nor "warnings", at least add an empty contains back
        if not (self.contains.items() or self.error or self.warnings):
            serialized['contains'] = {}
        return serialized
    
    def has_error(self) -> bool:
        return len(self.error) > 0
    
    def has_warnings(self):
        return len(self.warnings) > 0
    
    def get_error_as_text(self) -> str:
        if self.has_error():
            if isinstance(self.error, ErrorDict):
                return str(self.error)
            elif isinstance(self.error, dict):
                return f"Error: {json.dumps(self.error, indent=2)}"
            else:
                return f"Error (unknown error format): {self.error}"
        else:
            raise KeyError(f"No error found")
            
    def new_contain(self, at_type: Union[str, ThingTypesBase], **contains_metadata) -> Optional['Contain']:
        """
        Adds a new element to the ``contains`` dictionary.

        :param at_type: the ``@type`` of the annotation type being added
        :param contains_metadata: any metadata associated with the annotation type
        :return: the generated :class:`Contain` object
        """
        if isinstance(at_type, str):
            at_type = ThingTypesBase.from_str(at_type)
            
        if at_type not in self.contains:
            new_contain = Contain(contains_metadata)
            self.add_contain(new_contain, at_type)
            return new_contain
    
    def add_contain(self, contain: 'Contain', at_type: Union[str, ThingTypesBase]) -> None:
        self.contains[at_type] = contain

    def add_app_configuration(self, config_key: str, config_value: Union[PRMTV_TYPES, List[PRMTV_TYPES]]) -> None:
        """
        Add a configuration key-value pair to the app_configuration dictionary.
        """
        self.appConfiguration[config_key] = config_value

    def get_app_configuration(self, config_key: str) -> Union[PRMTV_TYPES, List[PRMTV_TYPES]]:
        """
        Get a configuration value from the app_configuration dictionary.
        """
        try:
            return self.appConfiguration[config_key]
        except KeyError:
            raise KeyError(f"app is not configured for \"{config_key}\" key in the view: {self.serialize()}")

    def add_parameters(self, **runtime_params: str):
        """
        Add runtime parameters as a batch (dict) to the view metadata. Note that parameter values must be strings.
        """
        for k, v in runtime_params.items():
            self.add_parameter(k, v)

    def add_parameter(self, param_key: str, param_value: str):
        """
        Add a single runtime parameter to the view metadata. Note that parameter value must be a string.
        """
        assert isinstance(param_value, str), \
                f"Parameter value must be a string, \"{param_value}\" ({type(param_value)}) is given for key \"{param_key}\"."
        self.parameters[param_key] = param_value

    def get_parameter(self, param_key: str) -> str:
        """
        Get a runtime parameter from the view metadata.
        """
        try:
            return self.parameters[param_key]
        except KeyError:
            raise KeyError(f"parameter \"{param_key}\" is not set in the view: {self.serialize()}")
    
    def set_error(self, message: str, stack_trace: str):
        self.error = ErrorDict({"message": message, "stackTrace": stack_trace})
        self.contains.empty()
    
    def add_warnings(self, *warnings: Warning):
        for warning in warnings:
            self.warnings.append(f'{warning.__class__.__name__}: {" - ".join(warning.args)}')

    def emtpy_warnings(self):
        self.warnings = []


class ErrorDict(MmifObject):
    """
    Error object that stores information about error occurred during processing. 
    """
    def __init__(self, error_obj: Optional[Union[bytes, str, dict]] = None, *_) -> None:
        self.message: str = ''
        self.stackTrace: str = ''
        super().__init__(error_obj)
    
    def __str__(self):
        return f"({self.message})\n\n{self.stackTrace}"
        

class Contain(DataDict[str, str]):
    """
    Contain object that represents the metadata of a single
    annotation type in the ``contains`` metadata of a MMIF view.
    """


class AnnotationsList(DataList[Union[Annotation, Document]]):
    """
    AnnotationsList object that implements :class:`mmif.serialize.model.DataList`
    for :class:`mmif.serialize.annotation.Annotation`.
    """
    _items: Dict[str, Union[Annotation, Document]]

    def _deserialize(self, input_list: list) -> None:  # pytype: disable=signature-mismatch
        """
        Extends base ``_deserialize`` method to initialize ``items`` as a dict from
        annotation IDs to :class:`mmif.serialize.annotation.Annotation` objects.

        :param input_list: the JSON data that defines the list of annotations
        :return: None
        """
        self._items = {item['properties']['id']: Document(item)
                       if ClamsTypesBase.attype_iri_isdocument(item['_type']) else Annotation(item)
                       for item in input_list}

    def append(self, value: Union[Annotation, Document], overwrite=False) -> None:
        """
        Appends an annotation to the list.

        Fails if there is already an annotation with the same ID
        in the list, unless ``overwrite`` is set to True.

        :param value: the :class:`mmif.serialize.annotation.Annotation`
                      object to add
        :param overwrite: if set to True, will overwrite an
                          existing annotation with the same ID
        :raises KeyError: if ``overwrite`` is set to False and
                          an annotation with the same ID exists
                          in the list
        :return: None
        """
        super()._append_with_key(value.id, value, overwrite)


class ContainsDict(DataDict[ThingTypesBase, Contain]):

    def _deserialize(self, input_dict: dict) -> None:
        for key, value in input_dict.items():
            if isinstance(key, str):
                key = ThingTypesBase.from_str(key)
            self._items[key] = Contain(value)

    def update(self, other: Union[dict, 'ContainsDict'], overwrite=False):
        for k, v in other.items():
            if isinstance(k, str):
                k = ThingTypesBase.from_str(k)
            self._append_with_key(k, v, overwrite=overwrite)
            
    def get(self, key: Union[str, ThingTypesBase], default=None):
        if isinstance(key, str):
            key = ThingTypesBase.from_str(key)
        return self._items.get(key, default)
    
    def __contains__(self, item: Union[str, ThingTypesBase]):
        if isinstance(item, str):
            # in general, when querying with a string, do not use fuzzy equality
            if 'vocab.lappsgrid.org' in item and item.split('/')[-1] in ThingTypesBase.old_lapps_type_shortnames:
                # first, some quirks for legacy LAPPSgrid types
                shortname = item.split('/')[-1]
                item = AnnotationTypesBase(f'http://mmif.clams.ai/vocabulary/{shortname}/v1')
                for key in self._items.keys():
                    if item._eq_internal(key, fuzzy=False):
                        return True
                return False
            else:
                # otherwise just string match 
                string_keys = [str(k) for k in self._items.keys()]
                return item in string_keys
        else:
            return item in self._items

    def pop(self, key):
        self._items.pop(key)
