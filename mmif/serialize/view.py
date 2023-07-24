"""
The :mod:`view` module contains the classes used to represent a MMIF view
as a live Python object.

In MMIF, views are created by apps in a pipeline that are annotating
data that was previously present in the MMIF file.
"""
from datetime import datetime
from typing import Dict, Union, Optional, Generator, List, cast

from mmif.vocabulary import ThingTypesBase, ClamsTypesBase
from .annotation import Annotation, Document
from .model import MmifObject, DataList, DataDict

__all__ = ['View', 'ViewMetadata', 'Contain']

from .. import DocumentTypes


class View(MmifObject):
    """
    View object that represents a single view in a MMIF file.

    A view is identified by an ID, and contains certain metadata,
    a list of annotations, and potentially a JSON-LD ``@context``
    IRI.

    If ``view_obj`` is not provided, an empty View will be generated.

    :param view_obj: the JSON data that defines the view
    """

    def __init__(self, view_obj: Optional[Union[bytes, str, dict]] = None) -> None:
        # used to autogenerate annotation ids
        self._id_counts = {}
        self.reserved_names.add("_id_counts")
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
        for item in self.annotations:
            item.parent = self.id

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
    
    def _set_id(self, annotation: Annotation, identifier):
        if identifier is not None:
            annotation.id = identifier
        else:
            prefix = annotation.at_type.get_prefix()
            new_num = self._id_counts.get(prefix, 0) + 1
            new_id = f'{prefix}_{new_num}'
            self._id_counts[prefix] = new_num
            annotation.id = new_id

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
        self._set_id(new_annotation, aid)
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
        annotation.parent = self.id
        self.annotations.append(annotation, overwrite)
        self.new_contain(annotation.at_type)
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
        self._set_id(new_document, did)
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
    
    def get_annotation_by_id(self, ann_id):
        ann_found = self.annotations.get(ann_id)
        if ann_found is None or not isinstance(ann_found, Annotation):
            raise KeyError(f"Annotation \"{ann_id}\" is not found in view {self.id}.")
        else:
            return ann_found
        
    def get_documents(self) -> List[Document]:
        return [cast(Document, annotation) for annotation in self.annotations if annotation.is_document()]

    def get_document_by_id(self, doc_id) -> Document:
        doc_found = self.annotations.get(doc_id)
        if doc_found is None or not isinstance(doc_found, Document):
            raise KeyError(f"Document \"{doc_id}\" not found in view {self.id}.")
        else:
            return doc_found

    def __getitem__(self, key: str) -> 'Annotation':
        """
        getitem implementation for View.

        >>> obj = View('''{"id": "v1","metadata": {"contains": {"BoundingBox": {}},"document": "m1","tool": "http://tools.clams.io/east/1.0.4"},"annotations": [{"@type": "BoundingBox","properties": {"id": "bb1","coordinates": [[90,40], [110,40], [90,50], [110,50]] }}]}''')
        >>> type(obj['bb1'])
        <class 'mmif.serialize.annotation.Annotation'>
        >>> obj['asdf']
        Traceback (most recent call last):
            ...
        KeyError: 'Annotation ID not found: asdf'

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


class ViewMetadata(MmifObject):
    """
    ViewMetadata object that represents the ``metadata`` object within a MMIF view.

    :param viewmetadata_obj: the JSON data that defines the metadata
    """

    def __init__(self, viewmetadata_obj: Optional[Union[bytes, str, dict]] = None) -> None:
        self.document: str = ''
        self.timestamp: Optional[datetime] = None
        self.app: str = ''
        self.contains: ContainsDict = ContainsDict()
        self.parameters: dict = {}
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
    
    def add_contain(self, contain: 'Contain', at_type: Union[str, ThingTypesBase]):
        self.contains[at_type] = contain

    def add_parameters(self, **runtime_params):
        self.parameters.update(dict(runtime_params))

    def add_parameter(self, param_key, param_value):
        self.parameters[param_key] = param_value

    def get_parameter(self, param_key):
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
    def __init__(self, error_obj: Optional[Union[bytes, str, dict]] = None) -> None:
        self.message: str = ''
        self.stackTrace: str = ''
        super().__init__(error_obj)
        

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
        self._items = {ThingTypesBase.from_str(key): Contain(value) for key, value in input_dict.items()}

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
        return item in self._items

    def pop(self, key):
        self._items.pop(key)
