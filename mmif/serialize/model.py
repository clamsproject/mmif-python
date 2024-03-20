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
"""

import json
from datetime import datetime
from typing import Union, Any, Dict, Optional, TypeVar, Generic, Generator, Iterator, Type, Set

from deepdiff import DeepDiff

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
       it means the class won't take any ``Additional Attributes`` in the JSON
       schema sense. If it's a dict, users can throw any k-v pairs to the
       class, EXCEPT for the reserved two key names.
    2. _attribute_classes:
       This is a dict from a key name to a specific python class to use for
       deserialize the value. Note that a key name in this dict does NOT
       have to be a *named* attribute, but is recommended to be one.
    3. _required_attributes:
       This is a simple list of names of attributes that are required in the object.
       When serialize, an object will skip its *empty* (e.g. zero-length, or None)
       attributes unless they are in this list. Otherwise, the serialized JSON
       string would have empty representations (e.g. ``""``, ``[]``).
    4. _exclude_from_diff:
       This is a simple list of names of attributes that should be excluded from
       the diff calculation in ``__eq__``. 

    # TODO (krim @ 8/17/20): this dict is however, a duplicate with the type hints in the class definition.
    Maybe there is a better way to utilize type hints (e.g. getting them as a programmatically), but for now
    developers should be careful to add types to hints as well as to this dict.

    Also note that those special attributes MUST be set in the __init__()
    before calling super method, otherwise deserialization will not work.

    And also, a subclass that has one or more *named* attributes, it must
    set those attributes in the __init__() before calling super method. When
    serializing a MmifObject, all *empty* attributes will be ignored, so for
    optional named attributes, you must leave the values empty (len == 0), but
    NOT None. Any None-valued named attributes will cause issues with current
    implementation.

    :param mmif_obj: JSON string or `dict` to initialize an object.
     If not given, an empty object will be initialized, sometimes with
     an ID value automatically generated, based on its parent object.
    """
    
    # these are the reserved names that cannot be used as attribute names, and 
    # they won't be serialized
    reserved_names: Set[str] = {
        'reserved_names',
        '_unnamed_attributes',
        '_attribute_classes',
        '_required_attributes',
        '_exclude_from_diff'
    }
    _unnamed_attributes: Optional[dict]
    _exclude_from_diff: Set[str]
    _attribute_classes: Dict[str, Type] = {}  # Mapping: str -> Type

    def __init__(self, mmif_obj: Optional[Union[bytes, str, dict]] = None) -> None:
        if isinstance(mmif_obj, bytes):
            mmif_obj = mmif_obj.decode('utf8')
        if not hasattr(self, '_required_attributes'):
            self._required_attributes = []
        if not hasattr(self, '_exclude_from_diff'):
            self._exclude_from_diff = set()
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

    def serialize(self, pretty: bool = False) -> str:
        """
        Generates JSON representation of an object.

        :param pretty: If True, returns string representation with indentation.
        :return: JSON string of the object.
        """
        return json.dumps(self._serialize(), indent=2 if pretty else None, cls=MmifObjectEncoder)

    def _serialize(self, alt_container: Optional[Dict] = None) -> dict:
        """
        Maps a MMIF object to a plain python dict object,
        rewriting internal keys that start with '_' to
        start with '@' per the JSON-LD schema.

        If a subclass needs special treatment during the mapping, it needs to
        override this method.

        :return: the prepared dictionary
        """
        container = alt_container if alt_container is not None else self._unnamed_attributes
        serializing_obj = {}
        try:
            for k, v in container.items():   # pytype: disable=attribute-error
                if v is None:
                    continue
                k = str(k)
                if k.startswith('_'):   # _ as a placeholder ``@`` in json-ld
                    k = f'@{k[1:]}'
                serializing_obj[k] = v
        except AttributeError as e:
            # means _unnamed_attributes is None, so nothing unnamed would be serialized
            pass
        for k, v in self.__dict__.items():
            if k in self.reserved_names:
                continue
            if k not in self._required_attributes and self.is_empty(v):
                continue
            if k.startswith('_'):       # _ as a placeholder ``@`` in json-ld
                k = f'@{k[1:]}'
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
                self[k] = self._attribute_classes[k](v)
            else:
                self[k] = v

    def __str__(self) -> str:
        return self.serialize(False)

    def __eq__(self, other) -> bool:
        return isinstance(other, type(self)) and \
               len(DeepDiff(self, other, report_repetition=True, exclude_types=[datetime],
                            # https://github.com/clamsproject/mmif-python/issues/214
                            exclude_paths=self._exclude_from_diff)
                   ) == 0

    def __len__(self) -> int:
        """
        Returns number of attributes that are not *empty*. 
        """
        return sum([named in self and not self.is_empty(self[named]) for named in self._named_attributes()]) \
               + (len(self._unnamed_attributes) if self._unnamed_attributes else 0)

    def __setitem__(self, key, value) -> None:
        if key in self.reserved_names:
            raise KeyError("can't set item on a reserved name")
        if key in self._named_attributes():
            if self._attribute_classes and key in self._attribute_classes \
                    and not isinstance(value, (self._attribute_classes[key])):
                self.__dict__[key] = self._attribute_classes[key](value)
            else:
                self.__dict__[key] = value
        else:
            if self._attribute_classes and key in self._attribute_classes \
                    and not isinstance(value, (self._attribute_classes[key])):
                self.set_additional_property(key, self._attribute_classes[key](value))
            else:
                self.set_additional_property(key, value)

    def __contains__(self, key: str) -> bool:
        try:
            self.__getitem__(key)
            return True
        except (TypeError, AttributeError, KeyError):
            return False

    def __getitem__(self, key) -> Union['MmifObject', str, datetime]:
        if key in self._named_attributes():
            value = self.__dict__[key]
        elif self._unnamed_attributes is None:
            raise AttributeError(f"Additional properties are disallowed by {self.__class__}: {key}")
        else: 
            value = self._unnamed_attributes[key]
        if key not in self._required_attributes and self.is_empty(value):
            raise KeyError(f"Property not found: {key} (is it set?)")
        else: 
            return value


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
    def __init__(self, mmif_obj: Optional[Union[bytes, str, list]] = None):
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
        return list(super()._serialize(self._items).values())

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

    def get(self, key: str) -> Optional[T]:
        """
        Standard dictionary-style get() method, albeit with no ``default``
        parameter. Relies on the implementation of __getitem__.

        Will return ``None`` if the key is not found.

        :param key: the key to search for
        :return: the value matching that key
        """
        try:
            return self[key]
        except KeyError:
            return None

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

    def __getitem__(self, key: str) -> T:
        if key not in self.reserved_names:
            return self._items.__getitem__(key)
        else:
            raise KeyError("Don't use __getitem__ to access a reserved name")

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
    def __init__(self, mmif_obj: Optional[Union[bytes, str, dict]] = None):
        self.reserved_names.add('_items')
        self._items: Dict[T, S] = dict()
        self.disallow_additional_properties()
        if mmif_obj is None:
            mmif_obj = {}
        super().__init__(mmif_obj)

    def _serialize(self, *args, **kwargs) -> dict:
        return super()._serialize(self._items)

    def get(self, key: T, default=None) -> Optional[S]:
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
