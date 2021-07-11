"""
The :mod:`mmif` module contains the classes used to represent a full MMIF
file as a live Python object.

See the specification docs and the JSON Schema file for more information.
"""

import json
from datetime import datetime
from typing import List, Union, Optional, Dict, ClassVar, cast

import jsonschema.validators
from pyrsistent import pmap, pvector

import mmif
from mmif import ThingTypesBase
from mmif.vocabulary import AnnotationTypes, DocumentTypes
from .annotation import Annotation, Document
from .model import MmifObject, DataList, FreezableDataList
from .view import View

__all__ = ['Mmif']


class Mmif(MmifObject):
    """
    MmifObject that represents a full MMIF file.

    :param mmif_obj: the JSON data
    :param validate: whether to validate the data against the MMIF JSON schema.
    """

    view_prefix: ClassVar[str] = 'v_'
    id_delimiter: ClassVar[str] = ':'

    def __init__(self, mmif_obj: Union[bytes, str, dict] = None, *, validate: bool = True, frozen: bool = True) -> None:
        self.metadata: MmifMetadata = MmifMetadata()
        self.documents: DocumentsList = DocumentsList()
        self.views: ViewsList = ViewsList()
        if validate:
            self.validate(mmif_obj)
        self.disallow_additional_properties()
        self._attribute_classes = pmap({
            'metadata': MmifMetadata,
            'documents': DocumentsList,
            'views': ViewsList
        })
        self._required_attributes = pvector(["metadata", "documents", "views"])
        super().__init__(mmif_obj)
        if frozen:
            self.freeze_documents()
            self.freeze_views()

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
        self.views.append(new_view)
        return new_view

    def add_view(self, view: View, overwrite=False) -> None:
        """
        Appends a View object to the views list.

        Fails if there is already a view with the same ID in the MMIF object.

        :param view: the Document object to add
        :param overwrite: if set to True, will overwrite
                          an existing view with the same ID
        :return: None
        """
        self.views.append(view, overwrite)

    def add_document(self, document: Document, overwrite=False) -> None:
        """
        Appends a Document object to the documents list.

        Fails if there is already a document with the same ID in the MMIF object.

        :param document: the Document object to add
        :param overwrite: if set to True, will overwrite
                          an existing view with the same ID
        :return: None
        """
        if not self.documents.is_frozen():
            self.documents.append(document, overwrite)
        else:
            raise TypeError("MMIF object is frozen")

    def freeze(self):
        """
        Deeply freezes all elements. Returns True only when everything if frozen.
        """
        doc_frozen = self.freeze_documents()
        view_frozen = self.freeze_views()
        return view_frozen and doc_frozen
        
    def freeze_documents(self) -> bool:
        """
        Deeply freezes the list of documents. Returns the result of
        the deep_freeze() call, signifying whether everything
        was fully frozen or not.
        """
        return self.documents.deep_freeze()

    def freeze_views(self) -> bool:
        """
        Deeply freezes all of the existing views without freezing
        the list of views itself. Returns the conjunct of the returns
        of all of the deep_freeze() calls, signifying whether everything
        was fully frozen or not.
        """
        fully_frozen = True
        for view in self.views:
            fully_frozen &= view.deep_freeze()
        return fully_frozen

    def get_documents_in_view(self, vid: str = None) -> List[Document]:
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
                if prop_key in doc and doc.properties[prop_key] == prop_value:
                    docs.append(doc)
        docs.extend([document for document in self.documents if document.properties[prop_key] == prop_value])
        return docs

    def get_documents_locations(self, m_type: Union[DocumentTypes, str], path_only=False) -> List[str]:
        """
        This method returns the file paths of documents of given type.
        Only top-level documents have locations, so we only check them.

        :param m_type: the type to search for
        :return: a list of the values of the location fields in the corresponding documents
        """
        docs = [document for document in self.documents if document.is_type(m_type) and len(document.location) > 0]
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
        Finds a Document object with the given ID.

        :param doc_id: the ID to search for
        :return: a reference to the corresponding document, if it exists
        :raises Exception: if there is no corresponding document
        """
        if Mmif.id_delimiter in doc_id:
            vid, did = doc_id.split(Mmif.id_delimiter)
            view = self[vid]
            if isinstance(view, View):
                return view.get_document_by_id(did) 
            else:
                raise KeyError("{} view not found".format(vid))
        else:
            doc_found = self.documents.get(doc_id)
        if doc_found is None:
            raise KeyError("{} document not found".format(doc_id))
        return cast(Document, doc_found)

    def get_view_by_id(self, req_view_id: str) -> View:
        """
        Finds a View object with the given ID.

        :param req_view_id: the ID to search for
        :return: a reference to the corresponding view, if it exists
        :raises Exception: if there is no corresponding view
        """
        result = self.views.get(req_view_id)
        if result is None:
            raise KeyError("{} view not found".format(req_view_id))
        return result

    def get_alignments(self, at_type1: Union[str, ThingTypesBase], at_type2: Union[str, ThingTypesBase]) -> Dict[str, List[Annotation]]:
        """
        Finds views where alignments between two given annotation types occurred.

        :return: a dict that keyed by view IDs (str) and has lists of alignment Annotation objects as values.
        """
        v_and_a = {}
        at_type1 = ThingTypesBase.from_str(at_type1) if isinstance(at_type1, str) else at_type1
        at_type2 = ThingTypesBase.from_str(at_type2) if isinstance(at_type2, str) else at_type2
        assert at_type1 != at_type2, f"Alignment must be between two different types, given only one: {at_type1}"
        for alignment_view in self.get_all_views_contain(AnnotationTypes.Alignment):
            alignments = []
            contains_meta = alignment_view.metadata.contains[AnnotationTypes.Alignment]
            if 'sourceType' in contains_meta and 'targetType' in contains_meta:
                aligned_types = list({contains_meta['sourceType'], contains_meta['targetType']})
                if len(aligned_types) == 2 and at_type1 in aligned_types and at_type2 in aligned_types:
                    alignments.extend(alignment_view.annotations)
            else:
                for alignment in alignment_view.get_annotations(AnnotationTypes.Alignment):
                    aligned_types = set()
                    for ann_id in [alignment.properties['target'], alignment.properties['source']]:
                        ann_id = cast(str, ann_id)
                        if Mmif.id_delimiter in ann_id:
                            view_id, ann_id = ann_id.split(Mmif.id_delimiter)
                            aligned_type = cast(Annotation, self[view_id][ann_id]).at_type
                        else:
                            aligned_type = cast(Annotation, alignment_view[ann_id]).at_type
                        aligned_types.add(aligned_type)
                    aligned_types = list(aligned_types)  # because membership check for sets also checks hash() values
                    if len(aligned_types) == 2 and at_type1 in aligned_types and at_type2 in aligned_types:
                        alignments.append(alignment)
            if len(alignments) > 0:
                v_and_a[alignment_view.id] = alignments
        return v_and_a

    def get_views_for_document(self, doc_id: str):
        """
        Returns the list of all views that have annotations anchored on a particular document.
        Note that when the document is insids a view (generated during the pipeline's running),
        doc_id must be prefixed with the view_id.
        """
        views = []
        for view in self.views:
            annotations = view.get_annotations(document=doc_id)
            try:
                next(annotations)
                views.append(view)
            except StopIteration:
                # search failed by the full doc_id string, now try trimming the view_id from the string and re-do the search
                if Mmif.id_delimiter in doc_id:
                    vid, did = doc_id.split(Mmif.id_delimiter)
                    if view.id == vid:
                        annotations = view.get_annotations(document=did)
                        try:
                            next(annotations)
                            views.append(view)
                        except StopIteration:
                            # both search failed, give up and move to next view
                            pass
        return views

    def get_all_views_contain(self, at_types: Union[ThingTypesBase, str, List[Union[str, ThingTypesBase]]]) -> List[View]:
        """
        Returns the list of all views in the MMIF if given types
        are present in that view's 'contains' metadata.

        :param at_types: a list of types or just a type to check for. When given more than one types, all types must be found.
        :return: the list of views that contain the type
        """
        if isinstance(at_types, list):
            return [view for view in self.views
                    if all(map(lambda x: x in view.metadata.contains, at_types))]
        else:
            return [view for view in self.views if at_types in view.metadata.contains]

    def get_views_contain(self, at_types: Union[ThingTypesBase, str, List[Union[str, ThingTypesBase]]]) -> List[View]:
        """
        An alias to `get_all_views_contain` method.
        """
        return self.get_all_views_contain(at_types)

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

    # pytype: disable=bad-return-type
    def __getitem__(self, item: str) -> Union[Document, View, Annotation]:
        """
        getitem implementation for Mmif. When nothing is found, this will raise an error
        rather than returning a None (although pytype doesn't think so...)

        :raises KeyError: if the item is not found or if the search results are ambiguous
        :param item: the search string, a document ID, a view ID, or a view-scoped annotation ID
        :return: the object searched for
        """
        if item in self._named_attributes():
            return self.__dict__[item]
        split_attempt = item.split(Mmif.id_delimiter)

        document_result = self.documents.get(split_attempt[0])
        view_result = self.views.get(split_attempt[0])

        if len(split_attempt) == 1:
            anno_result = None
        elif view_result:
            anno_result = view_result[split_attempt[1]]
        else:
            raise KeyError("Tried to subscript into a view that doesn't exist")

        if view_result and document_result:
            raise KeyError("Ambiguous ID search result")
        if not (view_result or document_result):
            raise KeyError("ID not found: %s" % item)
        return anno_result or view_result or document_result
    # pytype: enable=bad-return-type


class MmifMetadata(MmifObject):
    """
    Basic MmifObject class to contain the top-level metadata of a MMIF file.

    :param metadata_obj: the JSON data
    """

    def __init__(self, metadata_obj: Union[bytes, str, dict] = None) -> None:
        # TODO (krim @ 10/7/20): there could be a better name and a better way to give a value to this
        self.mmif: str = f"http://mmif.clams.ai/{mmif.__specver__}"
        self._required_attributes = pvector(["mmif"])
        super().__init__(metadata_obj)


class DocumentsList(FreezableDataList[Document]):
    """
    DocumentsList object that implements :class:`mmif.serialize.model.DataList`
    for :class:`mmif.serialize.document.Document`.
    """
    _items: Dict[str, Document]

    def _deserialize(self, input_list: list) -> None:
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

    def _deserialize(self, input_list: list) -> None:
        """
        Extends base ``_deserialize`` method to initialize ``items`` as a dict from
        view IDs to :class:`mmif.serialize.view.View` objects.

        :param input_list: the JSON data that defines the list of views
        :return: None
        """
        self._items = {item['id']: View(item) for item in input_list}

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
