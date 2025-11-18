"""
The :mod:`model` module contains the classes used to represent an
abstract MMIF object as a live Python object.

The :class:`MmifObject` class or one of its derivatives is subclassed by
all other classes defined in this SDK, except for :class:`MmifObjectEncoder`.

These objects are generally instantiated from JSON, either as a string
or as an already-loaded Python dictionary. This base class provides the
core functionality for deserializing MMIF JSON data into live objects
and serializing live objects into MMIF JSON data. Specialized behavior
for the different components of MMIF is added in the subclasses.

This module defines two main collection types:

- :class:`DataList`: List-like collections that support integer/slice
  indexing. For ID-based access, use indexing or ``get`` in the container
  level. For example, for DocumentList, use its parent Mmif object's
  getter methods to access documents by ID. (e.g., ``mmif['doc1']``).
- :class:`DataDict`: Dict-like collections that support string key access.

"""

import json
import warnings
from datetime import datetime
from typing import Union, Any, Dict, Optional, TypeVar, Generic, Generator, Iterator, Type, Set, ClassVar, List

T = TypeVar('T')
S = TypeVar('S')
PRMTV_TYPES: Type = Union[str, int, float, bool, None]

__all__ = [
    'MmifObject',
    'MmifObjectEncoder',
    'DataList',
    'DataDict',
    'PRMTV_TYPES'
]


class MmifObject(object):
    """
    Abstract superclass for MMIF related key-value pair objects.

    Any MMIF object can be initialized as an empty placeholder or
    an actual representation with a JSON formatted string or equivalent
    `dict` object argument.

    This superclass has four specially designed instance variables, and these
    variable names cannot be used as attribute names for MMIF objects.

    1. _unnamed_attributes:
       Only can be either None or an empty dictionary. If it's set to None,
       it means the class won't take any ``Additional Attributes`` in the 
       JSON schema sense. If it's an empty dict, users can throw any k-v 
       pairs to the class, as long as the key is not a "reserved" name, 
       and those additional attributes will be stored in this dict while
       in memory. 
    2. _attribute_classes:
       This is a dict from a key name to a specific python class to use for
       deserialize the value. Note that a key name in this dict does NOT
       have to be a *named* attribute, but is recommended to be one.
    3. _required_attributes:
       This is a simple list of names of attributes that are required in 
       the object. When serialize, an object will skip its *empty* (e.g. 
       zero-length, or None) attributes unless they are in this list. 
       Otherwise, the serialized JSON string would have empty 
       representations (e.g. ``""``, ``[]``).
    4. _exclude_from_diff:
       This is a simple list of names of attributes that should be excluded 
       from the diff calculation in ``__eq__``. 

    # TODO (krim @ 8/17/20): this dict is however, a duplicate with the type hints in the class definition.
    Maybe there is a better way to utilize type hints (e.g. getting them 
    as a programmatically), but for now developers should be careful to 
    add types to hints as well as to this dict.

    Also note that those special attributes MUST be set in the __init__()
    before calling super method, otherwise deserialization will not work.

    And also, a subclass that has one or more *named* attributes, it must
    set those attributes in the __init__() before calling super method. 
    When serializing a MmifObject, all *empty* attributes will be ignored, 
    so for optional named attributes, you must leave the values empty 
    (len == 0), but NOT None. Any None-valued named attributes will cause 
    issues with current implementation.

    :param mmif_obj: JSON string or `dict` to initialize an object.
     If not given, an empty object will be initialized, sometimes with
     an ID value automatically generated, based on its parent object.
    """
    
    view_prefix: ClassVar[str] = 'v_'
    id_delimiter: ClassVar[str] = ':'

    # these are the reserved names that cannot be used as attribute names, and 
    # they won't be serialized
    reserved_names: Set[str] = {
        'reserved_names',
        '_unnamed_attributes',
        '_attribute_classes',
        '_required_attributes',
        '_exclude_from_diff',
        '_contextual_attributes'
    }
    _unnamed_attributes: Optional[dict]
    _exclude_from_diff: Set[str]
    _contextual_attributes: Set[str]
    _attribute_classes: Dict[str, Type] = {}  # Mapping: str -> Type

    def __init__(self, mmif_obj: Optional[Union[bytes, str, dict]] = None, *_) -> None:
        if isinstance(mmif_obj, bytes):
            mmif_obj = mmif_obj.decode('utf8')
        if not hasattr(self, '_required_attributes'):
            self._required_attributes = []
        if not hasattr(self, '_exclude_from_diff'):
            self._exclude_from_diff = set()
        if not hasattr(self, '_contextual_attributes'):
            self._contextual_attributes = set()
        if not hasattr(self, '_unnamed_attributes'):
            self._unnamed_attributes = {}
        if mmif_obj is not None:
            self.deserialize(mmif_obj)

    def disallow_additional_properties(self) -> None:
        """
        Call this method in :func:`__init__` to prevent the insertion
        of unnamed attributes after initialization.
        """
        self._unnamed_attributes = None

    def set_additional_property(self, key: str, value: Any) -> None:
        """
        Method to set values in _unnamed_attributes.

        :param key: the attribute name
        :param value: the desired value
        :return: None
        :raise: AttributeError if additional properties are disallowed by :func:`disallow_additional_properties`
        """
        if self._unnamed_attributes is None:
            raise AttributeError(f"Additional properties are disallowed by {self.__class__}")
        self._unnamed_attributes[key] = value  # pytype: disable=unsupported-operands

    def _named_attributes(self) -> Generator[str, None, None]:
        """
        Returns a generator of the names of all of this object's named attributes.

        :return: generator of names of all named attributes
        """
        return (n for n in self.__dict__.keys() if n not in self.reserved_names)

    def serialize(self, pretty: bool = False, include_context: bool = True) -> str:
        """
        Generates JSON representation of an object.

        :param pretty: If True, returns string representation with indentation.
        :param include_context: If ``False``, excludes contextual attributes from
                                serialization. Contextual attributes hold information
                                that varies at runtime (e.g., timestamps) and do not
                                constitute the core information of the MMIF object.
                                This is useful for comparing two MMIF objects for equality.
        :return: JSON string of the object.
        """
        return json.dumps(self._serialize(include_context=include_context), indent=2 if pretty else None, cls=MmifObjectEncoder)

    def _serialize(self, alt_container: Optional[Dict] = None, include_context: bool = True) -> dict:
        """
        Maps a MMIF object to a plain python dict object,
        rewriting internal keys that start with '_' to
        start with '@' per the JSON-LD schema.

        If a subclass needs special treatment during the mapping, it needs to
        override this method.

        :param alt_container: optional alternative container dict to serialize instead of _unnamed_attributes
        :param include_context: See :meth:`serialize` for details.
        :return: the prepared dictionary
        """
        container = alt_container if alt_container is not None else self._unnamed_attributes
        serializing_obj = {}
        try:
            for k, v in container.items():   # pytype: disable=attribute-error
                if v is None:
                    continue
                k = str(k)
                if not include_context and k in self._contextual_attributes:
                    continue
                if k.startswith('_'):   # _ as a placeholder ``@`` in json-ld
                    k = f'@{k[1:]}'
                # Recursively serialize nested MmifObjects with the same include_context parameter
                if isinstance(v, MmifObject):
                    serializing_obj[k] = v._serialize(include_context=include_context)
                else:
                    serializing_obj[k] = v
        except AttributeError as e:
            # means _unnamed_attributes is None, so nothing unnamed would be serialized
            pass
        for k, v in self.__dict__.items():
            if k in self.reserved_names:
                continue
            if not include_context and k in self._contextual_attributes:
                continue
            if k not in self._required_attributes and self.is_empty(v):
                continue
            if k.startswith('_'):       # _ as a placeholder ``@`` in json-ld
                k = f'@{k[1:]}'
            # Recursively serialize nested MmifObjects with the same include_context parameter
            if isinstance(v, MmifObject):
                serializing_obj[k] = v._serialize(include_context=include_context)
            else:
                serializing_obj[k] = v
        return serializing_obj

    @staticmethod
    def is_empty(obj) -> bool:
        """
        return True if the obj is None or "emtpy". The emptiness first defined as
        having zero length. But for objects that lack __len__ method, we need
        additional check.
        """
        if obj is None:
            return True
        if hasattr(obj, '__len__') and len(obj) == 0:
            return True
        return False

    @staticmethod
    def _load_json(json_obj: Union[dict, str]) -> dict:
        """
        Maps JSON-format MMIF strings and dicts into Python dicts
        with identifier-compliant keys. To do this, it replaces "@"
        signs in JSON-LD field names with "_" to be python-compliant.

        >>> "_type" in MmifObject._load_json('{ "@type": "some_type", "@value": "some_value"}').keys()
        True
        >>> "_value" in MmifObject._load_json('{ "@type": "some_type", "@value": "some_value"}').keys()
        True

        :param json_str: the JSON data to load and process
        :return: the mapped data as a dict
        """
        def from_atsign(d: Dict[str, Any]) -> dict:
            for k in list(d.keys()):
                if k.startswith('@'):
                    d[f'_{k[1:]}'] = d.pop(k)
            return d

        def deep_from_atsign(d: dict) -> dict:
            new_d = d.copy()
            from_atsign(new_d)
            for key, value in new_d.items():
                if type(value) is dict:
                    new_d[key] = deep_from_atsign(value)
            return new_d

        if type(json_obj) is dict:
            return deep_from_atsign(json_obj)
        elif type(json_obj) is str:
            return json.loads(json_obj, object_hook=from_atsign)
        else:
            raise TypeError(f"tried to load MMIF JSON in a format other than str or dict: {type(json_obj)}")

    def deserialize(self, mmif_json: Union[str, dict]) -> None:
        """
        Takes a JSON-formatted string or a simple `dict` that's json-loaded from
        such a string as an input and populates object's fields with the values
        specified in the input.

        :param mmif_json: JSON-formatted string or dict from such a string
         that represents a MMIF object
        """
        mmif_json = self._load_json(mmif_json)
        self._deserialize(mmif_json)

    def _deserialize(self, input_dict: dict) -> None:
        """
        Maps a plain python dict object to a MMIF object.
        If a subclass needs a special treatment during the mapping, it needs to
        override this method.

        This default method won't work for generic types (e.g. List[X], Dict[X, Y]).
        For now, lists are abstracted as DataList and dicts are abstracted as XXXMetadata classes.
        However, if an attribute uses a generic type (e.g. view_metadata.contains: Dict[str, Contain])
        that class should override _deserialize of its own.

        :param input_dict: the prepared JSON data that defines the object
        """
        for k, v in input_dict.items():
            if self._attribute_classes and k in self._attribute_classes:
                self[k] = self._attribute_classes[k](v, self)
            else:
                self[k] = v

    def __str__(self) -> str:
        return self.serialize()

    def __eq__(self, other) -> bool:
        """
        Compares two MmifObject instances for equality by comparing their serialized
        representations with contextual attributes excluded.

        This avoids issues with DeepDiff accessing properties that may raise exceptions,
        and properly handles comparison by ignoring contextual attributes like timestamps
        and stack traces that vary based on runtime environment.

        See https://github.com/clamsproject/mmif-python/issues/311 for details.
        """
        return isinstance(other, type(self)) and \
               self.serialize(include_context=False) == other.serialize(include_context=False)

    def __len__(self) -> int:
        """
        Returns number of attributes that are not *empty*. 
        """
        return (sum([named in self and not self.is_empty(self[named]) for named in self._named_attributes()]) 
                + (len(self._unnamed_attributes) if self._unnamed_attributes else 0))

    def __setitem__(self, key, value) -> None:
        if key in self.reserved_names:
            raise KeyError("can't set item on a reserved name")
        if key in self._named_attributes():
            if self._attribute_classes and key in self._attribute_classes \
                    and not isinstance(value, (self._attribute_classes[key])):
                self.__dict__[key] = self._attribute_classes[key](value, self)
            else:
                self.__dict__[key] = value
        else:
            if self._attribute_classes and key in self._attribute_classes \
                    and not isinstance(value, (self._attribute_classes[key])):
                self.set_additional_property(key, self._attribute_classes[key](value, self))
            else:
                self.set_additional_property(key, value)

    def __contains__(self, key: str) -> bool:
        try:
            self.__getitem__(key)
            return True
        except (TypeError, KeyError):
            return False

    def __getitem__(self, key) -> Any:
        if key in self._named_attributes():
            value = self.__dict__[key]
        elif self._unnamed_attributes is None:
            raise KeyError(f"Additional properties are disallowed by {self.__class__}: {key}")
        else: 
            value = self._unnamed_attributes[key]
        if key not in self._required_attributes and self.is_empty(value):
            raise KeyError(f"Property not found: {key} (is it set?)")
        else: 
            return value

    def get(self, obj_id, default=None):
        """
        High-level safe getter that returns a default value instead of raising KeyError.

        This method wraps ``__getitem__()`` with exception handling, making it safe
        to query for objects that might not exist. Available on all MmifObject subclasses.

        :param obj_id: An attribute name or object identifier (document ID, view ID,
                       annotation ID, or property name depending on the object type).
                       For Mmif objects: when annotation ID is given as a "short" ID
                       (without view ID prefix), searches from the first view.
        :param default: The value to return if the key is not found (default: None)
        :return: The object/value searched for, or the default value if not found

        Examples
        --------
        Safe access pattern (works on all MmifObject subclasses):

        >>> # On Mmif objects:
        >>> view = mmif.get('v1', default=None)  # Returns None if not found
        >>> doc = mmif.get('doc1', default=None)
        >>>
        >>> # On Annotation/Document objects:
        >>> label = annotation.get('label', default='unknown')
        >>> author = document.get('author', default='anonymous')

        See Also
        --------
        __getitem__ : Direct access that raises KeyError when not found
        """
        try:
            return self.__getitem__(obj_id)
        except KeyError:
            return default


class MmifObjectEncoder(json.JSONEncoder):
    """
    Encoder class to define behaviors of de-/serialization
    """

    def default(self, obj: 'MmifObject'):
        """
        Overrides default encoding behavior to prioritize :func:`MmifObject.serialize()`.
        """
        if hasattr(obj, '_serialize'):
            return obj._serialize()
        elif hasattr(obj, 'isoformat'):         # for datetime objects
            return obj.isoformat()
        elif hasattr(obj, '__str__'):
            return str(obj)
        else:
            return json.JSONEncoder.default(self, obj)


class DataList(MmifObject, Generic[T]):
    """
    The DataList class is an abstraction that represents the
    various lists found in a MMIF file, such as documents, subdocuments,
    views, and annotations.

    :param Union[str, list] mmif_obj: the data that the list contains
    """
    def __init__(self, mmif_obj: Optional[Union[bytes, str, list]] = None, *_):
        self.reserved_names.add('_items')
        self._items: Dict[str, T] = dict()
        self.disallow_additional_properties()
        if mmif_obj is None:
            mmif_obj = []
        super().__init__(mmif_obj)

    def _serialize(self, *args, **kwargs) -> list:  # pytype: disable=signature-mismatch
        """
        Internal serialization method. Returns a list.

        :return: list of the values of the internal dictionary.
        """
        return list(super()._serialize(self._items, **kwargs).values())

    def deserialize(self, mmif_json: Union[str, list]) -> None:  # pytype: disable=signature-mismatch
        """
        Passes the input data into the internal deserializer.
        """
        super().deserialize(mmif_json)  

    @staticmethod
    def _load_json(json_list: Union[list, str]) -> list:
        if type(json_list) is str:
            json_list = json.loads(json_list)
        return [MmifObject._load_json(obj) for obj in json_list]
    
    def _deserialize(self, input_list: list) -> None:
        raise NotImplementedError()

    def get(self, key: str, default=None) -> Optional[T]:
        """
        .. deprecated:: 1.1.3
           Do not use in new code. Will be removed in 2.0.0.
           Use container-level access or positional indexing instead.

        Deprecated method for retrieving list elements by string ID.

        :param key: the key to search for
        :param default: the default value to return if the key is not found
                        (defaults to None)
        :return: the value matching that key, or the default value if not found

        Examples
        --------
        Old pattern (deprecated, do not use):

        >>> view = mmif.views.get('v1')  # DeprecationWarning!

        New patterns to use instead:

        >>> # For ID-based access, use container:
        >>> view = mmif['v1']
        >>> # Or with safe access:
        >>> view = mmif.get('v1', default=None)
        >>> # For positional access:
        >>> view = mmif.views[0]

        See Also
        --------
        __getitem__ : List-style positional access with integers
        """
        warnings.warn(
            "The 'get' method on list-like collections is deprecated and "
            "will be removed in 2.0.0. Use container-level access "
            "(e.g., mmif['v1']) or positional indexing (e.g., views[0]).",
            DeprecationWarning,
            stacklevel=2
        )
        return self._items.get(key, default)

    def _append_with_key(self, key: str, value: T, overwrite=False) -> None:
        """
        Internal method for appending a key-value pair. Subclasses should
        implement an append() method that extracts a key from the list data
        or generates a key programmatically (such as an index), depending
        on the data type.

        :param key: the desired key to append
        :param value: the value associated with the key
        :param overwrite: if set to True, will overwrite an existing K-V pair
         if the key already exists. Otherwise, raises a KeyError.
        :raise KeyError: if ``overwrite`` is False and the ``key`` is already
         present in the DataList.
        :return: None
        """
        if not overwrite and key in self._items:
            raise KeyError(f"Key {key} already exists")
        else:
            self[key] = value

    def append(self, value, overwrite):
        raise NotImplementedError()

    def __getitem__(self, key: Union[int, slice]) -> Union[T, List[T]]:
        """
        List-style positional access using integers or slices.

        This method provides pythonic list behavior - it only accepts integers
        for positional access or slices for range access. For string-based ID
        access, use container-level indexing instead (e.g., ``mmif['v1']``).

        :param key: An integer index or slice object
        :return: The element at the index, or a list of elements for slices
        :raises TypeError: If key is not an integer or slice (e.g., if a
                          string is passed)

        Examples
        --------
        Positional access (pythonic list behavior):

        >>> # Get first view:
        >>> first_view = mmif.views[0]
        >>>
        >>> # Get last document:
        >>> last_doc = mmif.documents[-1]
        >>>
        >>> # Slice to get multiple elements:
        >>> first_three_views = mmif.views[0:3]
        >>>
        >>> # This will raise TypeError:
        >>> view = mmif.views['v1']  # TypeError!
        >>>
        >>> # For ID-based access, use container:
        >>> view = mmif['v1']  # Correct way
        """
        if isinstance(key, (int, slice)):
            # Python's dicts preserve insertion order since 3.7.
            # We can convert values to a list and index it.
            return list(self._items.values())[key]
        else:
            raise TypeError(f"list indices must be integers or slices, not {type(key).__name__}")

    def __setitem__(self, key: str, value: T):
        if key not in self.reserved_names:
            self._items.__setitem__(key, value)
        else:
            super().__setitem__(key, value)

    def __iter__(self) -> Iterator[T]:
        return self._items.values().__iter__()

    def __len__(self) -> int:
        return self._items.__len__()

    def __reversed__(self) -> Iterator[T]:
        return reversed(self._items.values())

    def __contains__(self, item) -> bool:
        return item in self._items

    def empty(self):
        self._items = {}


class DataDict(MmifObject, Generic[T, S]):
    def __init__(self, mmif_obj: Optional[Union[bytes, str, dict]] = None, *_):
        self.reserved_names.add('_items')
        self._items: Dict[T, S] = dict()
        self.disallow_additional_properties()
        if mmif_obj is None:
            mmif_obj = {}
        super().__init__(mmif_obj)

    def _serialize(self, *args, **kwargs) -> dict:
        return super()._serialize(self._items, **kwargs)

    def get(self, key: T, default=None) -> Optional[S]:
        """
        Dictionary-style safe access with optional default value.

        This method provides pythonic dict behavior - returns the value for
        the given key, or a default value if the key is not found.

        :param key: The key to look up
        :param default: The value to return if key is not found (default: None)
        :return: The value associated with the key, or the default value

        Examples
        --------
        >>> # Access contains metadata:
        >>> timeframe_meta = view.metadata.contains.get(AnnotationTypes.TimeFrame)
        >>> if timeframe_meta is None:
        ...     print("No TimeFrame annotations in this view")
        >>>
        >>> # With custom default:
        >>> value = some_dict.get('key', default={})
        """
        return self._items.get(key, default)

    def _append_with_key(self, key: T, value: S, overwrite=False) -> None:
        if not overwrite and key in self._items:
            raise KeyError(f"Key {key} already exists")
        else:
            self[key] = value

    def update(self, other, overwrite):
        raise NotImplementedError()

    def items(self):
        return self._items.items()

    def keys(self):
        return self._items.keys()

    def values(self):
        return self._items.values()

    def __getitem__(self, key: T) -> S:
        if key not in self.reserved_names:
            return self._items.__getitem__(key)
        else:
            raise KeyError("Don't use __getitem__ to access a reserved name")

    def __setitem__(self, key: T, value: S):
        if not isinstance(key, str) or key not in self.reserved_names:
            self._items.__setitem__(key, value)
        else:
            super().__setitem__(key, value)

    def __iter__(self):
        return self._items.__iter__()

    def __len__(self):
        return self._items.__len__()

    def __contains__(self, item):
        return item in self._items
    
    def empty(self):
        self._items = {}
