# © 2025 EarthDaily Analytics Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import urllib.parse
from functools import wraps
from types import MethodType

from earthdaily.earthone.exceptions import NotFoundError

from ..client.deprecation import deprecate
from ..common.collection import Collection
from .attributes import (
    AttributeEqualityMixin,
    AttributeMeta,
    AttributeValidationError,
    CatalogObjectReference,
    DocumentState,
    ExtraPropertiesAttribute,
    ListAttribute,
    Timestamp,
    TypedAttribute,
)
from .catalog_client import CatalogClient, HttpRequestMethod
from .search import Search


class DeletedObjectError(Exception):
    """Indicates that an action cannot be performed.

    Raised when some action cannot be performed because the catalog object
    has been deleted from the EarthOne catalog using the delete method
    (e.g. :py:meth:`Product.delete`).
    """

    pass


class UnsavedObjectError(Exception):
    """Indicate that an action cannot be performed.

    Raised when trying to delete an object that hasn't been saved.
    """

    pass


def check_deleted(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        if self.state == DocumentState.DELETED:
            raise DeletedObjectError("This catalog object has been deleted.")
        try:
            return f(self, *args, **kwargs)
        except NotFoundError as e:
            self._deleted = True
            raise DeletedObjectError(
                "{} instance with id {} has been deleted".format(
                    self.__class__.__name__, self.id
                )
            ).with_traceback(e.__traceback__) from None

    return wrapper


def check_derived(f):
    @wraps(f)
    def wrapper(cls, *args, **kwargs):
        if cls._url is None:
            raise TypeError(
                "This method is only available for a derived class of 'CatalogObject'"
            )
        return f(cls, *args, **kwargs)

    return wrapper


def _new_abstract_class(cls, abstract_cls):
    if cls is abstract_cls:
        raise TypeError(
            "You can only instantiate a derived class of '{}'".format(
                abstract_cls.__name__
            )
        )

    return super(abstract_cls, cls).__new__(cls)


# This lets us have a class method and an instance method with the same name, but
# different signatures and implementation.
# see https://stackoverflow.com/questions/28237955/same-name-for-classmethod-and-instancemethod
class hybridmethod:
    def __init__(self, fclass, finstance=None, doc=None):
        self.fclass = fclass
        self.finstance = finstance
        self.__doc__ = doc or fclass.__doc__
        # support use on abstract base classes
        self.__isabstractmethod__ = bool(getattr(fclass, "__isabstractmethod__", False))

    def classmethod(self, fclass):
        return type(self)(fclass, self.finstance, None)

    def instancemethod(self, finstance):
        return type(self)(self.fclass, finstance, self.__doc__)

    def __get__(self, instance, cls):
        if instance is None or self.finstance is None:
            # either bound to the class, or no instance method available
            return self.fclass.__get__(cls, None)
        return self.finstance.__get__(instance, cls)


class CatalogObjectMeta(AttributeMeta):
    def __new__(cls, name, bases, attrs):
        new_cls = super(CatalogObjectMeta, cls).__new__(cls, name, bases, attrs)

        if new_cls._doc_type:
            new_cls._model_classes_by_type_and_derived_type[
                (new_cls._doc_type, new_cls._derived_type)
            ] = new_cls

        return new_cls


class CatalogObjectBase(AttributeEqualityMixin, metaclass=CatalogObjectMeta):
    """A base class for all representations of top level objects in the Catalog API."""

    # The following can be overridden by subclasses to customize behavior:

    # JSONAPI type for this model (required)
    _doc_type = None

    # Path added to the base URL for a list request of this model (required)
    _url = None

    # List of related objects to include in read requests
    _default_includes = []

    # The derived type of this class
    _derived_type = None

    # Attribute to use to determine the derived type of an instance
    _derived_type_switch = None

    _model_classes_by_type_and_derived_type = {}

    # Type returned by collect() on the corresponding Search object
    _collection_type = Collection

    id = TypedAttribute(
        str,
        mutable=False,
        serializable=False,
        doc="""str, immutable: A unique identifier for this object.

        Note that if you pass a string that does not begin with your EarthOne
        user organization ID, it will be prepended to your `id` with a ``:`` as
        separator.  If you are not part of an organization, your user ID is used.  Once
        set, it cannot be changed.
        """,
    )
    created = Timestamp(
        readonly=True,
        doc="""datetime, readonly: The point in time this object was created.

        *Filterable, sortable*.
        """,
    )
    modified = Timestamp(
        readonly=True,
        doc="""datetime, readonly: The point in time this object was last modified.

        *Filterable, sortable*.
        """,
    )
    v1_properties = TypedAttribute(
        dict,
        mutable=False,
        serializable=False,
        readonly=True,
    )

    def __new__(cls, *args, **kwargs):
        return _new_abstract_class(cls, CatalogObjectBase)

    def __init__(self, **kwargs):
        self._client = kwargs.pop("client", None) or CatalogClient.get_default_client()

        self._attributes = {}
        self._modified = set()
        self._deleted = False

        self._initialize(
            id=kwargs.pop("id", None),
            saved=kwargs.pop("_saved", False),
            relationships=kwargs.pop("_relationships", None),
            related_objects=kwargs.pop("_related_objects", None),
            **kwargs,
        )

    def __del__(self):
        for attr_type in self._attribute_types.values():
            attr_type.__delete__(self, validate=False)

    def _clear_attributes(self):
        self._mapping_attribute_instances = {}
        self._clear_modified_attributes()

        # This only applies to top-level attributes
        sticky_attributes = {}
        for name, value in self._attributes.items():
            attribute_type = self._attribute_types.get(name)
            if attribute_type._sticky:
                sticky_attributes[name] = value
        self._attributes = sticky_attributes

    def _initialize(
        self,
        id=None,
        saved=False,
        relationships=None,
        related_objects=None,
        deleted=False,
        **kwargs,
    ):
        self._clear_attributes()
        self._saved = saved
        self._deleted = deleted

        # This is an immutable attribute; can only be set once
        if id:
            self.id = id

        for name, val in kwargs.items():
            # Only silently ignore unknown attributes if data came from service
            attribute_definition = (
                self._attribute_types.get(name)
                if saved
                else self._get_attribute_type(name)
            )
            if attribute_definition is not None:
                attribute_definition.__set__(self, val, validate=not saved)

        for name, t in self._reference_attribute_types.items():
            id_value = kwargs.get(t.id_field)
            if id_value is not None:
                object_value = kwargs.get(name)
                if object_value and object_value.id != id_value:
                    message = (
                        "Conflicting related object reference: '{}' was '{}' "
                        "but '{}' was '{}'"
                    ).format(t.id_field, id_value, name, object_value.id)
                    raise AttributeValidationError(message)

                if related_objects:
                    related_object = related_objects.get(
                        (t.reference_class._doc_type, id_value)
                    )
                    if related_object is not None:
                        t.__set__(self, related_object, validate=not saved)

        if saved:
            self._clear_modified_attributes()

    def __repr__(self):
        name = getattr(self, "name", None)
        if name is None:
            name = ""
        elif isinstance(name, bytes):
            name = name.decode()

        sections = [
            # Document type and ID
            "{}: {}\n  id: {}".format(self.__class__.__name__, name, self.id)
        ]
        # related objects and their ids
        for name in sorted(self._reference_attribute_types):
            t = self._reference_attribute_types[name]
            # as a temporary hack for image upload, handle missing image_id field
            sections.append("  {}: {}".format(name, getattr(self, t.id_field, None)))

        if self.created:
            sections.append("  created: {:%c}".format(self.created))

        if self.state == DocumentState.DELETED:
            sections.append("* Deleted from the EarthOne catalog.")
        elif self.state != DocumentState.SAVED:
            sections.append(
                "* Not up-to-date in the EarthOne catalog. Call `.save()` to save or update this record."
            )

        return "\n".join(sections)

    def __eq__(self, other):
        if (
            not isinstance(other, self.__class__)
            or self.id != other.id
            or self.state != other.state
        ):
            return False

        return super(CatalogObjectBase, self).__eq__(other)

    def __setattr__(self, name, value):
        if not (name.startswith("_") or isinstance(value, MethodType)):
            # Make sure it's a proper attribute
            self._get_attribute_type(name)
        super(CatalogObjectBase, self).__setattr__(name, value)

    @property
    def is_modified(self):
        """bool: Whether any attributes were changed (see `state`).

        ``True`` if any of the attribute values changed since the last time this
        catalog object was retrieved or saved.  ``False`` otherwise.

        Note that assigning an identical value does not affect the state.
        """
        return bool(self._modified)

    @classmethod
    def _get_attribute_type(cls, name):
        try:
            return cls._attribute_types[name]
        except KeyError:
            raise AttributeError("{} has no attribute {}".format(cls.__name__, name))

    @classmethod
    def _get_model_class(cls, serialized_object):
        class_type = serialized_object["type"]
        klass = cls._model_classes_by_type_and_derived_type.get((class_type, None))

        if klass._derived_type_switch:
            derived_type = serialized_object["attributes"][klass._derived_type_switch]
            klass = cls._model_classes_by_type_and_derived_type.get(
                (class_type, derived_type)
            )

        return klass

    @classmethod
    def _serialize_filter_attribute(cls, name, value):
        """Serialize a single value for a filter.

        Allow the given value to be serialized using the serialization logic
        of the given attribute.  This method should only be used to serialize
        a filter value.

        Parameters
        ----------
        name : str
            The name of the attribute used for serialization logic.
        value : object
            The value to be serialized.

        Returns
        -------
        name : str
            The name to use in the serialized filter
        value : str
            The serialized value

        Raises
        ------
        AttributeValidationError
            If the attribute is not serializable.
        """
        attribute_type = cls._get_attribute_type(name)

        if isinstance(attribute_type, ListAttribute):
            # The type is contained in the list
            attribute_type = attribute_type._attribute_type

        if isinstance(attribute_type, CatalogObjectReference):
            # This is a little tricky... If the value is an instance containing
            # `id`, the name was already updated by the Expression to have `_id`
            # appended to it, and the value will be converted to a string below.
            # But if the value is a string, this hasn't happened yet and we need
            # to update the name...
            if value is None or isinstance(value, str):
                return (attribute_type.id_field, value)

        return (name, attribute_type.serialize(value))

    def _set_modified(self, attr_name, changed=True, validate=True):
        # Verify it is allowed to to be set
        attr = self._get_attribute_type(attr_name)
        if validate:
            if attr._readonly:
                raise AttributeValidationError(
                    "Can't set '{}' because it is a readonly attribute".format(
                        attr_name
                    )
                )
            if not attr._mutable and attr_name in self._attributes:
                raise AttributeValidationError(
                    "Can't set '{}' because it is an immutable attribute".format(
                        attr_name
                    )
                )

        if changed:
            self._modified.add(attr_name)

    def _serialize(self, attrs, jsonapi_format=False):
        serialized = {}
        for name in attrs:
            value = self._attributes[name]
            attribute_type = self._get_attribute_type(name)
            if attribute_type._serializable:
                serialized[name] = attribute_type.serialize(
                    value, jsonapi_format=jsonapi_format
                )

        return serialized

    @check_deleted
    def update(self, ignore_errors=False, **kwargs):
        """Update multiple attributes at once using the given keyword arguments.

        Parameters
        ----------
        ignore_errors : bool, optional
            ``False`` by default.  When set to ``True``, it will suppress
            `AttributeValidationError` and `AttributeError`.  Any given attribute that
            causes one of these two exceptions will be ignored, all other attributes
            will be set to the given values.

        Raises
        ------
        AttributeValidationError
            If one or more of the attributes being updated are immutable.
        AttributeError
            If one or more of the attributes are not part of this catalog object.
        DeletedObjectError
            If this catalog object was deleted.
        """
        original_values = dict(self._attributes)
        original_modified = set(self._modified)

        for name, val in kwargs.items():
            try:
                # A non-existent attribute will raise an AttributeError
                attribute_definition = self._get_attribute_type(name)

                # A bad value will raise an AttributeValidationError
                attribute_definition.__set__(self, val)
            except (AttributeError, AttributeValidationError):
                if ignore_errors:
                    pass
                else:
                    self._attributes = original_values
                    self._modified = original_modified
                    raise

    def serialize(self, modified_only=False, jsonapi_format=False):
        """Serialize the catalog object into json.

        Parameters
        ----------
        modified_only : bool, optional
            Whether only modified attributes should be serialized.  ``False`` by
            default. If set to ``True``, only those attributes that were modified since
            the last time the catalog object was retrieved or saved will be included.
        jsonapi_format : bool, optional
            Whether to use the ``data`` element for catalog objects.  ``False`` by
            default.  When set to ``False``, the serialized data will directly contain
            the attributes of the catalog object.  If set to ``True``, the serialized
            data will follow the exact JSONAPI with a top-level ``data`` element which
            contains ``id``, ``type``, and ``attributes``.  The latter will contain
            the attributes of the catalog object.
        """
        keys = self._modified if modified_only else self._attributes.keys()
        attributes = self._serialize(keys, jsonapi_format=jsonapi_format)

        if jsonapi_format:
            return self._client.jsonapi_document(self._doc_type, attributes, self.id)
        else:
            return attributes

    def _clear_modified_attributes(self):
        self._modified = set()

    @property
    def state(self):
        """DocumentState: The state of this catalog object."""
        if self._deleted:
            return DocumentState.DELETED

        if self._saved is False:
            return DocumentState.UNSAVED
        elif self.is_modified:
            return DocumentState.MODIFIED
        else:
            return DocumentState.SAVED

    @classmethod
    def get(cls, id, client=None, request_params=None, headers=None):
        """Get an existing object from the EarthOne catalog.

        If the EarthOne catalog object is found, it will be returned in the
        `~earthdaily.earthone.catalog.DocumentState.SAVED` state.  Subsequent changes will
        put the instance in the `~earthdaily.earthone.catalog.DocumentState.MODIFIED` state,
        and you can use :py:meth:`save` to commit those changes and update the EarthOne
        catalog object.  Also see the example for :py:meth:`save`.

        For bands, if you request a specific band type, for example
        :meth:`SpectralBand.get`, you will only receive that type.  Use :meth:`Band.get`
        to receive any type.

        Parameters
        ----------
        id : str
            The id of the object you are requesting.
        client : CatalogClient, optional
            A `CatalogClient` instance to use for requests to the EarthOne
            catalog.  The
            :py:meth:`~earthdaily.earthone.catalog.CatalogClient.get_default_client` will
            be used if not set.

        Returns
        -------
        :py:class:`~earthdaily.earthone.catalog.CatalogObject` or None
            The object you requested, or ``None`` if an object with the given `id`
            does not exist in the EarthOne catalog.

        Raises
        ------
        ~earthdaily.earthone.exceptions.ClientError or ~earthdaily.earthone.exceptions.ServerError
            :ref:`Spurious exception <network_exceptions>` that can occur during a
            network request.
        """
        try:
            data, related_objects = cls._send_data(
                method=HttpRequestMethod.GET,
                id=id,
                client=client,
                request_params=request_params,
                headers=headers,
            )
        except NotFoundError:
            return None

        model_class = cls._get_model_class(data)
        if not issubclass(model_class, cls):
            return None

        return model_class(
            id=data["id"],
            client=client,
            _saved=True,
            _relationships=data.get("relationships"),
            _related_objects=related_objects,
            **data["attributes"],
        )

    @classmethod
    def get_or_create(
        cls, id, client=None, request_params=None, headers=None, **kwargs
    ):
        """Get an existing object from the EarthOne catalog or create a new object.

        If the EarthOne catalog object is found, and the remainder of the
        arguments do not differ from the values in the retrieved instance, it will be
        returned in the `~earthdaily.earthone.catalog.DocumentState.SAVED` state.

        If the EarthOne catalog object is found, and the remainder of the
        arguments update one or more values in the instance, it will be returned in
        the `~earthdaily.earthone.catalog.DocumentState.MODIFIED` state.

        If the EarthOne catalog object is not found, it will be created and the
        state will be `~earthdaily.earthone.catalog.DocumentState.UNSAVED`.  Also see the
        example for :py:meth:`save`.

        Parameters
        ----------
        id : str
            The id of the object you are requesting.
        client : CatalogClient, optional
            A `CatalogClient` instance to use for requests to the EarthOne
            catalog.  The
            :py:meth:`~earthdaily.earthone.catalog.CatalogClient.get_default_client` will
            be used if not set.
        kwargs : dict, optional
            With the exception of readonly attributes (`created`, `modified`), any
            attribute of a catalog object can be set as a keyword argument (Also see
            `ATTRIBUTES`).

        Returns
        -------
        :py:class:`~earthdaily.earthone.catalog.CatalogObject`
            The requested catalog object that was retrieved or created.

        """
        obj = cls.get(id, client=client, request_params=request_params, headers=headers)

        if obj is None:
            obj = cls(id=id, client=client, **kwargs)
        else:
            obj.update(**kwargs)

        return obj

    @classmethod
    def get_many(
        cls, ids, ignore_missing=False, client=None, request_params=None, headers=None
    ):
        """Get existing objects from the EarthOne catalog.

        All returned EarthOne catalog objects will be in the
        `~earthdaily.earthone.catalog.DocumentState.SAVED` state.  Also see :py:meth:`get`.

        For bands, if you request a specific band type, for example
        :meth:`SpectralBand.get_many`, you will only receive that type.  Use
        :meth:`Band.get_many` to receive any type.

        Parameters
        ----------
        ids : list(str)
            A list of identifiers for the objects you are requesting.
        ignore_missing : bool, optional
            Whether to raise a `~earthdaily.earthone.exceptions.NotFoundError`
            exception if any of the requested objects are not found in the EarthOne
            catalog.  ``False`` by default which raises the exception.
        client : CatalogClient, optional
            A `CatalogClient` instance to use for requests to the EarthOne
            catalog.  The
            :py:meth:`~earthdaily.earthone.catalog.CatalogClient.get_default_client` will
            be used if not set.

        Returns
        -------
        list(:py:class:`~earthdaily.earthone.catalog.CatalogObject`)
            List of the objects you requested in the same order.

        Raises
        ------
        NotFoundError
            If any of the requested objects do not exist in the EarthOne catalog
            and `ignore_missing` is ``False``.
        ~earthdaily.earthone.exceptions.ClientError or ~earthdaily.earthone.exceptions.ServerError
            :ref:`Spurious exception <network_exceptions>` that can occur during a
            network request.
        """

        if not isinstance(ids, list) or any(not isinstance(id_, str) for id_ in ids):
            raise TypeError("ids must be a list of strings")

        id_filter = {"name": "id", "op": "eq", "val": ids}

        raw_objects, related_objects = cls._send_data(
            method=HttpRequestMethod.PUT,
            client=client,
            json={"filter": json.dumps([id_filter], separators=(",", ":"))},
            request_params=request_params,
            headers=headers,
        )

        if not ignore_missing:
            received_ids = set(obj["id"] for obj in raw_objects)
            missing_ids = set(ids) - received_ids

            if len(missing_ids) > 0:
                raise NotFoundError(
                    "Objects not found for ids: {}".format(", ".join(missing_ids))
                )

        objects = [
            model_class(
                id=obj["id"],
                client=client,
                _saved=True,
                _relationships=obj.get("relationships"),
                _related_objects=related_objects,
                **obj["attributes"],
            )
            for obj in raw_objects
            for model_class in (cls._get_model_class(obj),)
            if issubclass(model_class, cls)
        ]

        return objects

    @classmethod
    @check_derived
    def exists(cls, id, client=None, headers=None):
        """Checks if an object exists in the EarthOne catalog.

        Parameters
        ----------
        id : str
            The id of the object.
        client : CatalogClient, optional
            A `CatalogClient` instance to use for requests to the EarthOne
            catalog.  The
            :py:meth:`~earthdaily.earthone.catalog.CatalogClient.get_default_client` will
            be used if not set.

        Returns
        -------
        bool
            Returns ``True`` if the given ``id`` represents an existing object in
            the EarthOne catalog and ``False`` if not.

        Raises
        ------
        ~earthdaily.earthone.exceptions.ClientError or ~earthdaily.earthone.exceptions.ServerError
            :ref:`Spurious exception <network_exceptions>` that can occur during a
            network request.
        """
        client = client or CatalogClient.get_default_client()
        r = None
        try:
            r = client.session.head(cls._url + "/" + id, headers=headers)
        except NotFoundError:
            return False

        return r and r.ok

    @classmethod
    @check_derived
    def search(cls, client=None, request_params=None, headers=None):
        """A search query for all objects of the type this class represents.

        Parameters
        ----------
        client : CatalogClient, optional
            A `CatalogClient` instance to use for requests to the EarthOne
            catalog.  The
            :py:meth:`~earthdaily.earthone.catalog.CatalogClient.get_default_client` will
            be used if not set.

        Returns
        -------
        Search
            An instance of the :py:class:`~earthdaily.earthone.catalog.Search`
            class.

        Example
        -------
        >>> search = Product.search().limit(10) # doctest: +SKIP
        >>> for result in search: # doctest: +SKIP
                print(result.name) # doctest: +SKIP
        """
        return Search(
            cls, client=client, request_params=request_params, headers=headers
        )

    @check_deleted
    @deprecate(renamed={"extra_attributes": "request_params"})
    def save(self, request_params=None, headers=None):
        """Saves this object to the EarthOne catalog.

        If this instance was created using the constructor, it will be in the
        `~earthdaily.earthone.catalog.DocumentState.UNSAVED` state and is considered a new
        EarthOne catalog object that must be created.  If the catalog object
        already exists in this case, this method will raise a
        `~earthdaily.earthone.exceptions.BadRequestError`.

        If this instance was retrieved using :py:meth:`get`, :py:meth:`get_or_create`
        or any other way (for example as part of a :py:meth:`search`), and any of its
        values were changed, it will be in the
        `~earthdaily.earthone.catalog.DocumentState.MODIFIED` state and the existing catalog
        object will be updated.

        If this instance was retrieved using :py:meth:`get`, :py:meth:`get_or_create`
        or any other way (for example as part of a :py:meth:`search`), and none of its
        values were changed, it will be in the
        `~earthdaily.earthone.catalog.DocumentState.SAVED` state, and if no `request_params`
        parameter is given, nothing will happen.

        Parameters
        ----------
        request_params : dict, optional
            A dictionary of attributes that should be sent to the catalog along with
            attributes already set on this object.  Empty by default.  If not empty,
            and the object is in the `~earthdaily.earthone.catalog.DocumentState.SAVED`
            state, it is updated in the EarthOne catalog even though no attributes
            were modified.
        headers : dict, optional
            A dictionary of header keys and values to be sent with the request.

        Raises
        ------
        ConflictError
            If you're trying to create a new object and the object with given ``id``
            already exists in the EarthOne catalog.
        BadRequestError
            If any of the attribute values are invalid.
        DeletedObjectError
            If this catalog object was deleted.
        ~earthdaily.earthone.exceptions.ClientError or ~earthdaily.earthone.exceptions.ServerError
            :ref:`Spurious exception <network_exceptions>` that can occur during a
            network request.
        """
        if self.state == DocumentState.SAVED and not request_params:
            # Noop, already saved in the catalog
            return

        if self.state == DocumentState.UNSAVED:
            method = HttpRequestMethod.POST
            json = self.serialize(modified_only=False, jsonapi_format=True)
        else:
            method = HttpRequestMethod.PATCH
            json = self.serialize(modified_only=True, jsonapi_format=True)

        if request_params:
            json["data"]["attributes"].update(request_params)

        data, related_objects = self._send_data(
            method=method, id=self.id, json=json, client=self._client, headers=headers
        )

        self._initialize(
            id=data["id"],
            saved=True,
            relationships=data.get("relationships"),
            related_objects=related_objects,
            **data["attributes"],
        )

    @check_deleted
    def reload(self, request_params=None, headers=None):
        """Reload all attributes from the EarthOne catalog.

        Refresh the state of this catalog object from the object in the EarthOne
        catalog.  This may be necessary if there are concurrent updates and the object
        in the EarthOne catalog was updated from another client.  The instance
        state must be in the `~earthdaily.earthone.catalog.DocumentState.SAVED` state.

        If you want to revert a modified object to its original one, you should use
        :py:meth:`get` on the object class with the object's `id`.

        Raises
        ------
        ValueError
            If the catalog object is not in the ``SAVED`` state.
        DeletedObjectError
            If this catalog object was deleted.
        ~earthdaily.earthone.exceptions.ClientError or ~earthdaily.earthone.exceptions.ServerError
            :ref:`Spurious exception <network_exceptions>` that can occur during a
            network request.
        """

        if self.state != DocumentState.SAVED:
            raise ValueError(
                "{} instance with id {} has not been saved".format(
                    self.__class__.__name__, self.id
                )
            )

        data, related_objects = self._send_data(
            method=HttpRequestMethod.GET,
            id=self.id,
            client=self._client,
            request_params=request_params,
            headers=headers,
        )

        # this will effectively wipe all current state & caching
        self._initialize(
            id=data["id"],
            saved=True,
            relationships=data.get("relationships"),
            related_objects=related_objects,
            **data["attributes"],
        )

    @hybridmethod
    @check_derived
    def delete(cls, id, client=None):
        """Delete the catalog object with the given `id`.

        Parameters
        ----------
        id : str
            The id of the object to be deleted.
        client : CatalogClient, optional
            A `CatalogClient` instance to use for requests to the EarthOne
            catalog.  The
            :py:meth:`~earthdaily.earthone.catalog.CatalogClient.get_default_client` will
            be used if not set.

        Returns
        -------
        bool
            ``True`` if this object was successfully deleted. ``False`` if the
            object was not found.

        Raises
        ------
        ConflictError
            If the object has related objects (bands, images) that exist.
        ~earthdaily.earthone.exceptions.ClientError or ~earthdaily.earthone.exceptions.ServerError
            :ref:`Spurious exception <network_exceptions>` that can occur during a
            network request.

        Example
        -------
        >>> Image.delete('my-image-id') # doctest: +SKIP

        There is also an instance ``delete`` method that can be used to delete an object.
        It accepts no parameters and does not return anything. Once deleted, you cannot
        use the catalog object and should release any references.
        """
        if client is None:
            client = CatalogClient.get_default_client()

        try:
            client.session.delete(cls._url + "/" + id)
            return True  # non-200 will raise an exception
        except NotFoundError:
            return False

    @delete.instancemethod
    @check_deleted
    def delete(self):
        """Delete this catalog object from the EarthOne catalog.

        Once deleted, you cannot use the catalog object and should release any
        references.

        Raises
        ------
        DeletedObjectError
            If this catalog object was already deleted.
        UnsavedObjectError
            If this catalog object is being deleted without having been saved.
        ~earthdaily.earthone.exceptions.ClientError or ~earthdaily.earthone.exceptions.ServerError
            :ref:`Spurious exception <network_exceptions>` that can occur during a
            network request.
        """
        if self.state == DocumentState.UNSAVED:
            raise UnsavedObjectError("You cannot delete an unsaved object.")

        self._client.session.delete(self._url + "/" + self.id)
        self._deleted = True  # non-200 will raise an exception

    # This unused method must remain here to support unpickling any
    # pickled objects generated prior to v3.2.0.
    def _instance_delete(self):
        """Obsolete, do not use"""
        self.delete()

    @classmethod
    @check_derived
    def _send_data(
        cls, method, id=None, json=None, client=None, request_params=None, headers=None
    ):
        client = client or CatalogClient.get_default_client()
        session_method = getattr(client.session, method.lower())
        url = cls._url

        query_params = {}
        if method not in (HttpRequestMethod.POST, HttpRequestMethod.PUT):
            url += "/" + urllib.parse.quote(id)
            if request_params:
                query_params.update(**request_params)
        elif request_params:
            if json:
                json = dict(**json, **request_params)
            else:
                json = dict(**request_params)

        if cls._default_includes:
            query_params["include"] = ",".join(cls._default_includes)

        if query_params:
            url += "?" + urllib.parse.urlencode(query_params)

        r = session_method(url, json=json, headers=headers).json()
        data = r["data"]
        related_objects = cls._load_related_objects(r, client)

        return data, related_objects

    @classmethod
    def _load_related_objects(cls, response, client):
        related_objects = {}
        related_objects_serialized = response.get("included")
        if related_objects_serialized:
            for serialized in related_objects_serialized:
                model_class = cls._get_model_class(serialized)
                if model_class:
                    related = model_class(
                        id=serialized["id"],
                        client=client,
                        _saved=True,
                        **serialized["attributes"],
                    )
                    related_objects[(serialized["type"], serialized["id"])] = related

        return related_objects


class CatalogObject(CatalogObjectBase):
    """A base class for all representations of objects in the EarthOne catalog."""

    extra_properties = ExtraPropertiesAttribute(
        doc="""dict, optional: A dictionary of up to 50 key/value pairs.

        The keys of this dictionary must be strings, and the values of this dictionary
        can be strings or numbers.  This allows for more structured custom metadata
        to be associated with objects.
        """
    )
    tags = ListAttribute(
        TypedAttribute(str),
        doc="""list, optional: A list of up to 32 tags, each up to 1000 bytes long.

        The tags may support the classification and custom filtering of objects.

        *Filterable*.
        """,
    )

    def __new__(cls, *args, **kwargs):
        return _new_abstract_class(cls, CatalogObject)


class AuthCatalogObject(CatalogObject):
    """A base class for all representations of objects in the EarthOne catalog
    that support ACLs.

    .. _auth_note:

    Note
    ----
    The `readers` and `writers` IDs must be prefixed with ``email:``, ``user:``,
    ``group:`` or ``org:``.  The `owners` IDs must be prefixed with ``org:`` or ``user:``.
    Using ``org:`` as an owner will assign those privileges only to administrators
    for that organization; using ``org:`` as a reader or writer assigns those
    privileges to everyone in that organization.  The `readers` and `writers` attributes
    are only visible in full to an owner. If you are a reader or a writer those
    attributes will only display the elements of those lists by which you are gaining
    read or write access.

    Any user with owner privileges is able to read the object attributes and data,
    modify the object attributes, and delete the object, including reading and modifying the
    `owners`, `writers`, and `readers` attributes.

    Any user with writer privileges is able to read the object attributes and data,
    modify the object attributes except for `owners`, `writers`, and `readers`.
    A writer cannot delete the object. A writer can read the `owners` attribute but
    can only read the elements of `writers` and `readers` by which they gain access
    to the object.

    Any user with reader privileges is able to read the objects attributes and data.
    A reader can read the `owners` attribute but can only read the elements of
    `writers` and `readers` by which they gain access to the object.

    Also see :doc:`Sharing Resources </guides/sharing>`.
    """

    owners = ListAttribute(
        TypedAttribute(str),
        doc="""list(str), optional: User, group, or organization IDs that own this object.

        Defaults to [``user:current_user``, ``org:current_org``].  The owner can edit,
        delete, and change access to this object.  :ref:`See this note <auth_note>`.

        *Filterable*.
        """,
    )
    readers = ListAttribute(
        TypedAttribute(str),
        doc="""list(str), optional: User, email, group, or organization IDs that can read this object.

        Will be empty by default.  This attribute is only available in full to the `owners`
        of the object.  :ref:`See this note <auth_note>`.
        """,
    )
    writers = ListAttribute(
        TypedAttribute(str),
        doc="""list(str), optional: User, group, or organization IDs that can edit this object.

        Writers will also have read permission.  Writers will be empty by default.
        See note below.  This attribute is only available in full to the `owners` of the object.
        :ref:`See this note <auth_note>`.
        """,
    )

    def __new__(cls, *args, **kwargs):
        return _new_abstract_class(cls, AuthCatalogObject)

    def user_is_owner(self, auth=None):
        """Check if the authenticated user is an owner, and can
        perform actions such as changing ACLs or deleting this object.

        Parameters
        ----------
        auth : Auth, optional
            The auth object to use for the check. If not provided, the default auth object
            will be used.

        Returns
        -------
        bool
            True if the user is an owner of the object, False otherwise.
        """
        if auth is None:
            auth = self._client.auth

        return "internal:platform-admin" in auth.payload.get("groups", []) or bool(
            set(self.owners) & auth.all_owner_acl_subjects_as_set
        )

    def user_can_write(self, auth=None):
        """Check if the authenticated user is an owner or a writer and has permissions
        to modify this object.

        Parameters
        ----------
        auth : Auth, optional
            The auth object to use for the check. If not provided, the default auth object
            will be used.

        Returns
        -------
        bool
            True if the user can modify the object, False otherwise.
        """
        if auth is None:
            auth = self._client.auth

        return self.user_is_owner(auth) or bool(
            set(self.writers) & auth.all_acl_subjects_as_set
        )

    def user_can_read(self, auth=None):
        """Check if the authenticated user is an owner, a writer, or a reader
        and has permissions to read this object.

        Note it is kind of silly to call this method unless a non-default auth
        object is provided, because the default authorized user must have read
        permission in order to even retrieve this object.

        Parameters
        ----------
        auth : Auth, optional
            The auth object to use for the check. If not provided, the default auth object
            will be used.

        Returns
        -------
        bool
            True if the user can read the object, False otherwise.
        """
        if auth is None:
            auth = self._client.auth

        return (
            "internal:platform-ro" in auth.payload.get("groups", [])
            or self.user_can_write(auth)
            or bool(set(self.readers) & auth.all_acl_subjects_as_set)
        )
