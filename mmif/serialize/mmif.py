"""
The :mod:`mmif` module contains the classes used to represent a full MMIF
file as a live Python object.

See the specification docs and the JSON Schema file for more information.
"""

import json
import math
import warnings
from collections import defaultdict
from datetime import datetime
from typing import List, Union, Optional, Dict, cast, Iterator

import jsonschema.validators

import mmif
from mmif import ThingTypesBase
from mmif.serialize.annotation import Annotation, Document
from mmif.serialize.model import MmifObject, DataList
from mmif.serialize.view import View
from mmif.vocabulary import AnnotationTypes, DocumentTypes

__all__ = ['Mmif']


class MmifMetadata(MmifObject):
    """
    Basic MmifObject class to contain the top-level metadata of a MMIF file.

    :param metadata_obj: the JSON data
    """

    def __init__(self, metadata_obj: Optional[Union[bytes, str, dict]] = None, *_) -> None:
        # TODO (krim @ 10/7/20): there could be a better name and a better way to give a value to this
        self.mmif: str = f"http://mmif.clams.ai/{mmif.__specver__}"
        self._required_attributes = ["mmif"]
        super().__init__(metadata_obj)


class DocumentsList(DataList[Document]):
    """
    DocumentsList object that implements :class:`mmif.serialize.model.DataList`
    for :class:`mmif.serialize.document.Document`.
    """
    _items: Dict[str, Document]

    def _deserialize(self, input_list: list) -> None:  # pytype: disable=signature-mismatch
        """
        Extends base ``_deserialize`` method to initialize ``items`` as a dict from
        document IDs to :class:`mmif.serialize.document.Document` objects.

        :param input_list: the JSON data that defines the list of documents
        :return: None
        """
        self._items = {item['properties']['id']: Document(item) for item in input_list}

    def append(self, value: Document, overwrite=False) -> None:
        """
        Appends a document to the list.

        Fails if there is already a document with the same ID
        in the list, unless ``overwrite`` is set to True.

        :param value: the :class:`mmif.serialize.document.Document`
                      object to add
        :param overwrite: if set to True, will overwrite an
                          existing document with the same ID
        :raises KeyError: if ``overwrite`` is set to False and
                          a document with the same ID exists
                          in the list
        :return: None
        """
        super()._append_with_key(value.id, value, overwrite)


class ViewsList(DataList[View]):
    """
    ViewsList object that implements :class:`mmif.serialize.model.DataList`
    for :class:`mmif.serialize.view.View`.
    """
    _items: Dict[str, View]

    def __init__(self, mmif_obj: Optional[Union[bytes, str, list]] = None, parent_mmif=None, *_):
        self._parent_mmif = parent_mmif
        self.reserved_names.update(("_parent_mmif", "_id_counts"))
        super().__init__(mmif_obj)

    def _deserialize(self, input_list: list) -> None:  # pytype: disable=signature-mismatch
        """
        Extends base ``_deserialize`` method to initialize ``items`` as a dict from
        view IDs to :class:`mmif.serialize.view.View` objects.

        :param input_list: the JSON data that defines the list of views
        :return: None
        """
        if input_list:
            self._items = {item['id']: View(item, self._parent_mmif) for item in input_list}

    def append(self, value: View, overwrite=False) -> None:
        """
        Appends a view to the list.

        Fails if there is already a view with the same ID
        in the list, unless ``overwrite`` is set to True.

        :param value: the :class:`mmif.serialize.view.View`
                      object to add
        :param overwrite: if set to True, will overwrite an
                          existing view with the same ID
        :raises KeyError: if ``overwrite`` is set to False and
                          a view with the same ID exists
                          in the list
        :return: None
        """
        super()._append_with_key(value.id, value, overwrite)

    def get_last_contentful_view(self) -> Optional[View]:
        """
        Returns the last view that is contentful, i.e., has no error or warning .
        """
        for view in reversed(self._items.values()):
            if 'error' not in view.metadata and 'warnings' not in view.metadata:
                return view
    
    def get_last_view(self) -> Optional[View]:
        """
        Returns the last view appended.
        """
        if self._items:
            return self._items[list(self._items.keys())[-1]]
            
    def get_last(self) -> Optional[View]:
        warnings.warn('get_last() is deprecated, use get_last_contentful_view() instead.', DeprecationWarning)
        return self.get_last_contentful_view()


class Mmif(MmifObject):
    """
    MmifObject that represents a full MMIF file.

    :param mmif_obj: the JSON data
    :param validate: whether to validate the data against the MMIF JSON schema.
    """

    def __init__(self, mmif_obj: Optional[Union[bytes, str, dict]] = None, *, validate: bool = True) -> None:
        self.metadata: MmifMetadata = MmifMetadata()
        self.documents: DocumentsList = DocumentsList()
        self.views: ViewsList = ViewsList()
        if validate and mmif_obj is not None:
            self.validate(mmif_obj)
        self.disallow_additional_properties()
        self._attribute_classes = {
            'metadata': MmifMetadata,
            'documents': DocumentsList,
            'views': ViewsList
        }
        self._required_attributes = ["metadata", "documents", "views"]
        super().__init__(mmif_obj)

    @staticmethod
    def validate(json_str: Union[bytes, str, dict]) -> None:
        """
        Validates a MMIF JSON object against the MMIF Schema.
        Note that this method operates before processing by MmifObject._load_str,
        so it expects @ and not _ for the JSON-LD @-keys.

        :raises jsonschema.exceptions.ValidationError: if the input fails validation
        :param json_str: a MMIF JSON dict or string
        :return: None
        """
        # NOTE that schema file first needs to be copied to resources directory
        # this is automatically done via setup.py, so for users this shouldn't be a matter

        if isinstance(json_str, bytes):
            json_str = json_str.decode('utf8')
        schema = json.loads(mmif.get_mmif_json_schema())
        if isinstance(json_str, str):
            json_str = json.loads(json_str)
        jsonschema.validators.validate(json_str, schema)

    def serialize(self, pretty: bool = False, sanitize: bool = False, autogenerate_capital_annotations=True) -> str:
        """
        Serializes the MMIF object to a JSON string.

        :param sanitize: If True, performs some sanitization of before returning 
            the JSON string. See :meth:`sanitize` for details.
        :param autogenerate_capital_annotations: If True, automatically convert 
            any "pending" temporary properties from `Document` objects to 
            `Annotation` objects. See :meth:`generate_capital_annotations` for 
            details.
        :param pretty: If True, returns string representation with indentation.
        :return: JSON string of the MMIF object.
        """
        if autogenerate_capital_annotations:
            self.generate_capital_annotations()
        # sanitization should be done after `Annotation` annotations are generated
        if sanitize:
            self.sanitize()
        return super().serialize(pretty)

    def _deserialize(self, input_dict: dict) -> None:
        """
        Deserializes the MMIF JSON string into a Mmif object.
        After *regular* deserialization, this method will perform the following 
        *special* handling of Annotation.properties that allows apps to access 
        Annotation/Document properties that are not encoded in the objects 
        themselves. This is to allow apps to access in a more intuitive way, 
        without having too much hassle to iterate views and manually collect the properties.
        
        1. This will read in existing *view*-scoped properties from *contains*
        metadata and attach them to the corresponding ``Annotation`` objects.

        1. This will read in existing ``Annotation`` typed annotations and 
        attach the document-level properties to the ``Document`` objects, 
        using an ephemeral property dict. 
        
        """
        super()._deserialize(input_dict)
        for view in self.views:
            view._parent_mmif = self
            # this dict will be populated with properties 
            # that are not encoded in individual annotations objects themselves
            extrinsic_props = defaultdict(dict)
            for at_type, type_lv_props in view.metadata.contains.items():
                for prop_key, prop_value in type_lv_props.items():
                    extrinsic_props[at_type][prop_key] = prop_value
            for ann in view.get_annotations():
                ## for "capital" Annotation properties
                # first add all extrinsic properties to the Annotation objects
                # as "ephemeral" properties
                for prop_key, prop_value in extrinsic_props[ann.at_type].items():
                    ann._props_ephemeral[prop_key] = prop_value
                # then, do the same to associated Document objects. Note that, 
                # in a view, it is guaranteed that all Annotation objects are not duplicates
                if ann.at_type == AnnotationTypes.Annotation:
                    doc_id = ann.get_property('document')
                    try:
                        for prop_key, prop_value in ann.properties.items():
                            doc = cast(Document, self.__getitem__(doc_id))
                            if not isinstance(doc, Document):
                                raise KeyError
                            doc._props_ephemeral[prop_key] = prop_value
                    except KeyError:
                        warnings.warn(f"Annotation {ann.id} has a document ID {doc_id} that "
                                      f"does not exist in the MMIF object. Skipping.", RuntimeWarning)
                        
                ## caching start and end points for time-based annotations
                # add quick access to `start` and `end` values if the annotation is using `targets` property
                if 'targets' in ann.properties:
                    if 'start' in ann.properties or 'end' in ann.properties:
                        raise ValueError(f"Annotation {ann.id} has `targets` and `start`/`end` "
                                         f"properties at the same time. Annotation anchors are ambiguous.")
                    ann._props_ephemeral['start'] = self._get_linear_anchor_point(ann, start=True)
                    ann._props_ephemeral['end'] = self._get_linear_anchor_point(ann, start=False)
                
                ## caching alignments
                if ann.at_type == AnnotationTypes.Alignment:
                    self._cache_alignment(ann)
    
    def _cache_alignment(self, alignment_ann: Annotation):
        def _when_failed():
            warnings.warn(
                f"Alignment {alignment_ann.id} has `source` and `target` properties that do not point to Annotation objects.",
                RuntimeWarning)
        ## caching alignments
        if all(map(lambda x: x in alignment_ann.properties, ('source', 'target'))):
            try:
                source_ann = self[alignment_ann.get('source')]
                target_ann = self[alignment_ann.get('target')]
                if isinstance(source_ann, Annotation) and isinstance(target_ann, Annotation):
                    source_ann._cache_alignment(alignment_ann, target_ann)
                    target_ann._cache_alignment(alignment_ann, source_ann)
                else:
                    _when_failed()
            except KeyError:
                _when_failed()

    def generate_capital_annotations(self):
        """
        Automatically convert any "pending" temporary properties from 
        `Document` objects to `Annotation` objects . The generated `Annotation` 
        objects are then added to the last `View` in the views lists. 
        
        See https://github.com/clamsproject/mmif-python/issues/226 for rationale
        behind this behavior and discussion.
        """
        # this view will be the default kitchen sink for all generated annotations.
        last_view = self.views.get_last_contentful_view()
        
        # proceed only when there's at least one view
        if last_view:
            
            # this app name is used to check a view is generated by the "currently running" app.
            # knowing the currently running app is important so that properties of `Document` objects generated by the 
            # current app can be properly recorded inside the `Document` objects (since they are "writable" to the 
            # current app), instead of being recorded in a separate `Annotation` object.
            current_app = last_view.metadata.app

            # to avoid duplicate property recording, this will be populated with
            # existing Annotation objects from all existing views
            existing_anns = defaultdict(lambda: defaultdict(dict))
            # ideally, if we can "de-duplicate" props at `add_property()` time, that'd be more efficient, 
            # but that is impossible without looking for the target `document` across other views and top documents list
            
            # new properties to record in the current serialization call
            anns_to_write = defaultdict(dict)
            for view in self.views:
                doc_id = None
                if AnnotationTypes.Annotation in view.metadata.contains:
                    if 'document' in view.metadata.contains[AnnotationTypes.Annotation]:
                        doc_id = view.metadata.contains[AnnotationTypes.Annotation]['document']
                    for ann in view.get_annotations(AnnotationTypes.Annotation):
                        if doc_id is None:
                            # note that in the input MMIF that generated with old implementation,
                            # this value can be in the "short" form, i.e., without view ID prefix
                            # however, after deserialization, all document IDs should have the 
                            # view ID prefix, at least within in-memory representation.
                            doc_id = ann.get_property('document')
                        existing_anns[doc_id].update(ann.properties.items())
                for doc in view.get_documents():
                    anns_to_write[doc.id].update(doc._props_pending.items())
            for doc in self.documents:
                anns_to_write[doc.id].update(doc._props_pending.items())
            # additional iteration of views, to find a proper view to add the 
            # generated annotations. If none found, use the last view as the kitchen sink
            last_view_for_docs = defaultdict(lambda: last_view)
            doc_ids = set(anns_to_write.keys())
            for doc_id in doc_ids:
                if len(last_view.annotations) == 0:
                    # meaning, this new app didn't generate any annotation except for these document properties
                    # thus, we should add capital annotations to the last (empty) view
                    last_view_for_docs[doc_id] = last_view
                    break
                for view in reversed(self.views):
                    if any(view.get_annotations(document=doc_id)):
                        last_view_for_docs[doc_id] = view 
                        break
            for doc_id, found_props in anns_to_write.items():
                # ignore the "empty" id property from temporary dict 
                # `id` is "required" attribute for `AnnotationProperty` class 
                # thus will always be present in `props` dict as a key with emtpy value
                # also ignore duplicate k-v pairs
                props = {}
                for k, v in found_props.items():
                    if k != 'id' and existing_anns[doc_id][k] != v:
                        props[k] = v
                if props:
                    view_to_write = last_view_for_docs[doc_id]
                    if view_to_write.metadata.app == current_app and doc_id in view_to_write.annotations:
                        view_to_write[doc_id].properties.update(props)
                    else:
                        if len(anns_to_write) == 1:
                            # if there's only one document, we can record the doc_id in the contains metadata
                            view_to_write.metadata.new_contain(AnnotationTypes.Annotation, document=doc_id)
                            props.pop('document', None)
                        else:
                            # otherwise, doc_id needs to be recorded in the annotation property
                            props['document'] = doc_id
                        view_to_write.new_annotation(AnnotationTypes.Annotation, **props)

    def sanitize(self):
        """
        Sanitizes a Mmif object by running some safeguards.
        Concretely, it performs the following before returning the JSON string.
        
        #. validating output using built-in MMIF jsonschema
        #. remove non-existing annotation types from ``contains`` metadata
    
        """
        for view in self.views:
            existing_at_types = set(annotation.at_type for annotation in view.annotations)
            to_pop = set()
            for contains_at_type in view.metadata.contains.keys():
                if contains_at_type not in existing_at_types:
                    to_pop.add(contains_at_type)
            for key in to_pop:
                view.metadata.contains.pop(key)
        serialized = self.serialize()
        self.validate(serialized)

    def new_view_id(self) -> str:
        """
        Fetches an ID for a new view.

        :return: the ID
        """
        index = len(self.views)
        new_id = self.view_prefix + str(index)
        while new_id in self.views:
            index += 1
            new_id = self.view_prefix + str(index)
        return new_id

    def new_view(self) -> View:
        """
        Creates an empty view with a new ID and appends it to the views list.

        :return: a reference to the new View object
        """
        new_view = View()
        new_view.id = self.new_view_id()
        new_view.metadata.timestamp = datetime.now()
        self.add_view(new_view)
        return new_view

    def add_view(self, view: View, overwrite=False) -> None:
        """
        Appends a View object to the views list.

        Fails if there is already a view with the same ID or a document 
        with the same ID in the MMIF object.

        :param view: the Document object to add
        :param overwrite: if set to True, will overwrite
                          an existing view with the same ID
        :raises KeyError: if ``overwrite`` is set to False and existing 
                          object (document or view) with the same ID exists
        :return: None
        """
        if view.id in self.documents:
            raise KeyError(f"{view.id} already exists in the documents list. ")
        view._parent_mmif = self
        self.views.append(view, overwrite)

    def add_document(self, document: Document, overwrite=False) -> None:
        """
        Appends a Document object to the documents list.

        Fails if there is already a document with the same ID or a view 
        with the same ID in the MMIF object.

        :param document: the Document object to add
        :param overwrite: if set to True, will overwrite
                          an existing view with the same ID
        :raises KeyError: if ``overwrite`` is set to False and existing 
                          object (document or view) with the same ID exists
        :return: None
        """
        if document.id in self.views:
            raise KeyError(f"{document.id} already exists in the views list. ")
        self.documents.append(document, overwrite)

    def get_documents_in_view(self, vid: Optional[str] = None) -> List[Document]:
        """
        Method to get all documents object queries by a view id.

        :param vid: the source view ID to search for
        :return: a list of documents matching the requested source view ID, or an empty list if the view not found
        """
        view = self.views.get(vid)
        if view is not None:
            return view.get_documents()
        else:
            return []

    def get_documents_by_type(self, doc_type: Union[str, DocumentTypes]) -> List[Document]:
        """
        Method to get all documents where the type matches a particular document type, which should be one of the CLAMS document types.

        :param doc_type: the type of documents to search for, must be one of ``Document`` type defined in the CLAMS vocabulary.
        :return: a list of documents matching the requested type, or an empty list if none found.
        """
        docs = []
        # although only `TextDocument`s are allowed in view:annotations list, this implementation is more future-proof
        for view in self.views:
            docs.extend([document for document in view.get_documents() if document.is_type(doc_type)])
        docs.extend([document for document in self.documents if document.is_type(doc_type)])
        return docs

    def get_documents_by_app(self, app_id: str) -> List[Document]:
        """
        Method to get all documents object queries by its originated app name.

        :param app_id: the app name to search for
        :return: a list of documents matching the requested app name, or an empty list if the app not found
        """
        docs = []
        for view in self.views:
            if view.metadata.app == app_id:
                docs.extend(view.get_documents())
        return docs

    def get_documents_by_property(self, prop_key: str, prop_value: str) -> List[Document]:
        """
        Method to retrieve documents by an arbitrary key-value pair in the document properties objects.

        :param prop_key: the metadata key to search for
        :param prop_value: the metadata value to match
        :return: a list of documents matching the requested metadata key-value pair
        """
        docs = []
        for view in self.views:
            for doc in view.get_documents():
                if prop_key in doc and doc.get(prop_key) == prop_value:
                    docs.append(doc)
        docs.extend([document for document in self.documents if document[prop_key] == prop_value])
        return docs

    def get_documents_locations(self, m_type: Union[DocumentTypes, str], path_only=False) -> List[Union[str, None]]:
        """
        This method returns the file paths of documents of given type.
        Only top-level documents have locations, so we only check them.

        :param m_type: the type to search for
        :return: a list of the values of the location fields in the corresponding documents
        """
        docs = [document for document in self.documents if document.is_type(m_type) and document.location is not None]
        if path_only:
            return [doc.location_path() for doc in docs]
        else:
            return [doc.location for doc in docs]

    def get_document_location(self, m_type: Union[DocumentTypes, str], path_only=False) -> Optional[str]:
        """
        Method to get the location of *first* document of given type.

        :param m_type: the type to search for
        :return: the value of the location field in the corresponding document
        """
        # TODO (krim @ 8/10/20): Is returning the first location desirable?
        locations = self.get_documents_locations(m_type, path_only=path_only)
        return locations[0] if len(locations) > 0 else None

    def get_document_by_id(self, doc_id: str) -> Document:
        """
        .. deprecated:: 1.1.0
           Will be removed in 2.0.0. 
           Use general ``__getitem__()`` method instead, e.g., ``mmif[doc_id]``.
           
        Finds a Document object with the given ID.

        :param doc_id: the ID to search for
        :return: a reference to the corresponding document, if it exists
        :raises KeyError: if there is no corresponding document
        """
        warnings.warn(
            "Mmif.get_document_by_id() is deprecated, use mmif[doc_id] instead.",
            DeprecationWarning
        )
        doc_found = self.__getitem__(doc_id)
        if not isinstance(doc_found, Document):
            raise KeyError(f"Document with ID {doc_id} not found in the MMIF object.")
        return cast(Document, doc_found)

    def get_view_by_id(self, view_id: str) -> View:
        """
        .. deprecated:: 1.1.0
           Will be removed in 2.0.0. 
           Use general ``__getitem__()`` method instead, e.g., ``mmif[view_id]``.
           
        Finds a View object with the given ID.

        :param view_id: the ID to search for
        :return: a reference to the corresponding view, if it exists
        :raises Exception: if there is no corresponding view
        """
        warnings.warn(
            "Mmif.get_view_by_id() is deprecated, use mmif[view_id] instead.",
            DeprecationWarning
        )
        view_found = self.__getitem__(view_id)
        if not isinstance(view_found, View):
            raise KeyError(f"View with ID {view_id} not found in the MMIF object.")
        return cast(View, view_found)

    def get_alignments(self, at_type1: Union[str, ThingTypesBase], at_type2: Union[str, ThingTypesBase]) -> Dict[str, List[Annotation]]:
        """
        Finds views where alignments between two given annotation types occurred.

        :return: a dict that keyed by view IDs (str) and has lists of alignment Annotation objects as values.
        """
        v_and_a = {}
        at_type1, at_type2 = [ThingTypesBase.from_str(x) if isinstance(x, str) else x for x in (at_type1, at_type2)]
        assert at_type1 != at_type2, f"Alignment must be between two different types, given only one: {at_type1}"
        for alignment_view in self.get_all_views_contain(AnnotationTypes.Alignment):
            alignments = []
            contains_meta = alignment_view.metadata.contains[AnnotationTypes.Alignment]
            if 'sourceType' in contains_meta and 'targetType' in contains_meta:
                aligned_types = [ThingTypesBase.from_str(x) 
                                 for x in {contains_meta['sourceType'], contains_meta['targetType']}]
                if len(aligned_types) == 2 and at_type1 in aligned_types and at_type2 in aligned_types:
                    alignments.extend(alignment_view.annotations)
            else:
                for alignment in alignment_view.get_annotations(AnnotationTypes.Alignment):
                    aligned_types = set()
                    for ann_id in [alignment['target'], alignment['source']]:
                        ann_id = cast(str, ann_id)
                        aligned_type = cast(Annotation, self[ann_id]).at_type
                        aligned_types.add(aligned_type)
                    aligned_types = list(aligned_types)  # because membership check for sets also checks hash() values
                    if len(aligned_types) == 2 and at_type1 in aligned_types and at_type2 in aligned_types:
                        alignments.append(alignment)
            if len(alignments) > 0:
                v_and_a[alignment_view.id] = alignments
        return v_and_a

    def get_views_for_document(self, doc_id: str) -> List[View]:
        """
        Returns the list of all views that have annotations anchored on a particular document.
        Note that when the document is inside a view (generated during the pipeline's running),
        doc_id must be prefixed with the view_id.
        """
        views = []
        for view in self.views:
            annotations = view.get_annotations(document=doc_id)
            try:
                next(annotations)
                views.append(view)
            except StopIteration:
                pass
        return views

    def get_all_views_with_error(self) -> List[View]:
        """
        Returns the list of all views in the MMIF that have errors. 
        
        :return: the list of views that contain errors but no annotations
        """
        return [v for v in self.views if v.has_error()]
    
    get_views_with_error = get_all_views_with_error
            
    def get_all_views_contain(self, *at_types: Union[ThingTypesBase, str]) -> List[View]:
        """
        Returns the list of all views in the MMIF if given types
        are present in that view's 'contains' metadata.

        :param at_types: a list of types or just a type to check for. When given more than one types, all types must be found.
        :return: the list of views that contain the type
        """
        return [view for view in self.views
                if all(map(lambda x: x in view.metadata.contains, at_types))]

    get_views_contain = get_all_views_contain
    
    def get_view_with_error(self) -> Optional[View]:
        """
        Returns the last view appended that contains an error.
        
        :return: the view, or None if no error is found
        """
        for view in reversed(self.views):
            if view.has_error():
                return view
        return None
    
    def get_last_error(self) -> Optional[str]:
        """
        Returns the last error message found in the views.
        
        :return: the error message in human-readable format, or None if no error is found
        """
        v = self.get_view_with_error()
        return v.get_error() if v is not None else None

    def get_view_contains(self, at_types: Union[ThingTypesBase, str, List[Union[str, ThingTypesBase]]]) -> Optional[View]:
        """
        Returns the last view appended that contains the given
        types in its 'contains' metadata.

        :param at_types: a list of types or just a type to check for. When given more than one types, all types must be found.
        :return: the view, or None if the type is not found
        """
        # will return the *latest* view
        # works as of python 3.6+ (checked by setup.py) because dicts are deterministically ordered by insertion order
        for view in reversed(self.views):
            if isinstance(at_types, list):
                if all(map(lambda x: x in view.metadata.contains, at_types)):
                    return view
            else:
                if at_types in view.metadata.contains:
                    return view
        return None

    def _is_in_time_range(self, ann: Annotation, range_s: Union[int, float], range_e: Union[int, float]) -> bool:
        """
        Checks if the annotation is anchored within the given time range. Any overlap is considered included. 

        :param ann: the Annotation object to check, must be time-based itself or anchored to time-based annotations
        :param range_s: the start time point of the range (in milliseconds)
        :param range_e: the end time point of the range (in milliseconds)

        :return: True if the annotation is anchored within the time range, False otherwise
        """
        ann_s, ann_e = self.get_start(ann), self.get_end(ann)
        return (ann_s < range_s < ann_e) or (ann_s < range_e < ann_e) or (ann_s > range_s and ann_e < range_e)

    def get_annotations_between_time(self, start: Union[int, float], end: Union[int, float], time_unit: str = "ms",
                                     at_types: List[Union[ThingTypesBase, str]] = []) -> Iterator[Annotation]:
        """
        Finds annotations that are anchored between the given time points.

        :param start: the start time point in the unit of `input_unit`
        :param end: the end time point in the unit of `input_unit`
        :param time_unit: the unit of the input time points. Default is `ms`.
        :param at_types: a list of annotation types to filter with. Any type in this list will be included in the return.
        :return: an iterator of Annotation objects that are anchored between the given time points
        """
        assert start < end, f"Start time point must be smaller than the end time point, given {start} and {end}"
        assert start >= 0, f"Start time point must be non-negative, given {start}"
        assert end >= 0, f"End time point must be non-negative, given {end}"
        
        from mmif.utils.timeunit_helper import convert

        time_anchors_in_range = []
        uniq_types = set(ThingTypesBase.from_str(t) if isinstance(t, str) else t for t in at_types)

        for view in self.get_all_views_contain(AnnotationTypes.TimeFrame) + self.get_all_views_contain(AnnotationTypes.TimePoint):
            time_unit_in_view = view.metadata.contains.get(AnnotationTypes.TimeFrame)["timeUnit"]
            
            start_time = convert(start, time_unit, time_unit_in_view, 1)
            end_time = convert(end, time_unit, time_unit_in_view, 1)
            for ann in view.get_annotations():
                if ann.at_type in (AnnotationTypes.TimeFrame, AnnotationTypes.TimePoint) and self._is_in_time_range(ann, start_time, end_time):
                    time_anchors_in_range.append(ann)
        time_anchors_in_range.sort(key=lambda x: self.get_start(x))
        for time_anchor in time_anchors_in_range:
            if not uniq_types or time_anchor.at_type in uniq_types:
                yield time_anchor
            for aligned in time_anchor.get_all_aligned():
                if not uniq_types or aligned.at_type in uniq_types:
                    yield aligned

    def _get_linear_anchor_point(self, ann: Annotation, targets_sorted=False, start: bool = True) -> Union[int, float]:
        # TODO (krim @ 2/5/24): Update the return type once timeunits are unified to `ms` as integers (https://github.com/clamsproject/mmif/issues/192)
        """
        Retrieves the anchor point of the annotation. Currently, this method only supports linear anchors, 
        namely time and text, hence does not work with spatial anchors (polygons or video-object).
        
        :param ann: An Annotation object that has a linear anchor point. Namely, some subtypes of `Region` vocabulary type.
        :param start: If True, returns the start anchor point. Otherwise, returns the end anchor point. N/A for `timePoint` anchors.
        :param targets_sorted: If True, the method will assume that the targets are sorted in the order of the anchor points.
        :return: the anchor point of the annotation. 1d for linear regions (time, text)
        """
        props = ann.properties
        if 'timePoint' in props:
            return ann.get_property('timePoint')
        elif 'targets' in props:
            if 'start' in props or 'end' in props:
                raise ValueError(f"Annotation {ann.id} has `targets` and `start`/`end` "
                                 f"properties at the same time. Annotation anchors are ambiguous.")

            if not targets_sorted:
                point = math.inf if start else -1
                comp = min if start else max
                for target_id in ann.get_property('targets'):
                    point = comp(point, self._get_linear_anchor_point(self[target_id], start=start))
                return point
            target_id = ann.get_property('targets')[0 if start else -1]
            return self._get_linear_anchor_point(self[target_id], start=start)
        elif (start and 'start' in props) or (not start and 'end' in props):
            return ann.get_property('start' if start else 'end')
        else:
            raise ValueError(f"{ann.id} ({ann.at_type}) does not have a valid anchor point. Is it a valid 'Region' type?")
    
    def get_start(self, annotation: Annotation) -> Union[int, float]:
        """
        An alias to `get_anchor_point` method with `start=True`.
        """
        return self._get_linear_anchor_point(annotation, start=True)
    
    def get_end(self, annotation: Annotation) -> Union[int, float]:
        """
        An alias to `get_anchor_point` method with `start=False`.
        """
        return self._get_linear_anchor_point(annotation, start=False)

    def __getitem__(self, item: str) \
            -> Union[Document, View, Annotation, MmifMetadata, DocumentsList, ViewsList]:
        """
        index ([]) implementation for Mmif. This will try to find any object, given an identifier or an immediate 
        attribute name. When nothing is found, this will raise an error rather than returning a None 

        :raises KeyError: if the item is not found or if the search results are ambiguous
        :param item: an attribute name or an object identifier (a document ID, a view ID, or an annotation ID). When 
                     annotation ID is given as a "short" ID (without view ID prefix), the method will try to find a 
                     match from the first view, and return immediately if found.
        :return: the object searched for
        :raise KeyError: if the item is not found or multiple objects are found with the same ID
        """
        if item in self._named_attributes():
            return self.__dict__[item]
        if self.id_delimiter in item:
            vid, _ = item.split(self.id_delimiter, 1)
            return self.views[vid].annotations[item]
        else:
            # search for document first, then views
            # raise KeyError if nothing is found
            try:
                return self.documents.__getitem__(item)
            except KeyError:
                try:
                    return self.views.__getitem__(item)
                except KeyError:
                    raise KeyError(f"Object with ID {item} not found in the MMIF object. ")
    
    def get(self, obj_id, default=None):
        """
        High-level getter for Mmif. This will try to find any object, given 
        an identifier or an immediate attribute name. When nothing is found, 
        this will return a default value instead of raising an error.

        :param obj_id: an immediate attribute name or an object identifier 
                     (a document ID, a view ID, or an annotation ID). When 
                     annotation ID is given as a "short" ID (without view 
                     ID prefix), the method will try to find a match from 
                     the first view, and return immediately if found.
        :param default: the default value to return if none is found
        :return: the object searched for or the default value
        """
        try:
            return self.__getitem__(obj_id)
        except KeyError:
            return default
