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

import io

from strenum import StrEnum

from earthdaily.earthone.exceptions import NotFoundError

from ..client.services.service import ThirdPartyService
from ..common.collection import Collection
from ..common.property_filtering import Properties
from .attributes import (
    DocumentState,
    EnumAttribute,
    GeometryAttribute,
    StorageState,
    Timestamp,
    TypedAttribute,
    parse_iso_datetime,
)
from .blob_download import BlobDownload
from .catalog_base import (
    AuthCatalogObject,
    CatalogClient,
    check_deleted,
    check_derived,
    hybridmethod,
    UnsavedObjectError,
)
from .search import AggregateDateField, GeoSearch, SummarySearchMixin
from .task import TaskStatus

properties = Properties()


class StorageType(StrEnum):
    """The storage type for a blob.

    Attributes
    ----------
    COMPUTE : enum
        Compute service job results.
    DATA : enum
        Arbitrary user-managed data. This type may be uploaded by users.
    DYNCOMP : enum
        Saved Dynamic Compute objects. This type may be uploaded by users.
    LOGS : enum
        Compute service job log output (text files).
    """

    COMPUTE = "compute"
    DATA = "data"
    DYNCOMP = "dyncomp"
    LOGS = "logs"


class BlobSummaryResult(object):
    """
    The readonly data returned by :py:meth:`SummaySearch.summary` or
    :py:meth:`SummaySearch.summary_interval`.

    Attributes
    ----------
    count : int
        Number of blobs in the summary.
    bytes : int
        Total number of bytes of data across all blobs in the summary.
    namespaces : list(str)
        List of namespace IDs for the blobs included in the summary.
    interval_start: datetime
        For interval summaries only, a datetime representing the start of the interval period.

    """

    def __init__(
        self, count=None, bytes=None, namespaces=None, interval_start=None, **kwargs
    ):
        self.count = count
        self.bytes = bytes
        self.namespaces = namespaces
        self.interval_start = (
            parse_iso_datetime(interval_start) if interval_start else None
        )

    def __repr__(self):
        text = [
            "\nSummary for {} blobs:".format(self.count),
            " - Total bytes: {:,}".format(self.bytes),
        ]
        if self.namespaces:
            text.append(" - Namespaces: {}".format(", ".join(self.namespaces)))
        if self.interval_start:
            text.append(" - Interval start: {}".format(self.interval_start))
        return "\n".join(text)


class BlobSearch(SummarySearchMixin, GeoSearch):
    # Be aware that the `|` characters below add whitespace.  The first one is needed
    # avoid the `Inheritance` section from appearing before the auto summary.
    """A search request that iterates over its search results for blobs.

    The `BlobSearch` is identical to `Search` but with a couple of summary methods:
    :py:meth:`summary` and :py:meth:`summary_interval`.
    """

    SummaryResult = BlobSummaryResult
    DEFAULT_AGGREGATE_DATE_FIELD = AggregateDateField.CREATED


class Blob(AuthCatalogObject):
    """A stored blob (arbitrary bytes) that can be searched and retrieved.

    Instantiating a blob indicates that you want to create a *new* EarthOne
    storage blob.  If you instead want to retrieve an existing blob use
    `Blob.get() <earthdaily.earthone.catalog.Blob.get>`.
    You can also use `Blob.search() <earthdaily.earthone.catalog.Blob.search>`.
    Also see the example for :py:meth:`~earthdaily.earthone.catalog.Blob.upload`.


    Parameters
    ----------
    client : CatalogClient, optional
        A `CatalogClient` instance to use for requests to the EarthOne catalog.
        The :py:meth:`~earthdaily.earthone.catalog.CatalogClient.get_default_client` will
        be used if not set.
    kwargs : dict
        With the exception of readonly attributes (`created`, `modified`) and with
        the exception of properties (`ATTRIBUTES`, `is_modified`, and `state`), any
        attribute listed below can also be used as a keyword argument.  Also see
        `~Blob.ATTRIBUTES`.
    """

    _doc_type = "storage"
    _url = "/storage"
    # _collection_type set below due to circular problems
    _url_client = ThirdPartyService()

    # Blob Attributes
    namespace = TypedAttribute(
        str,
        doc="""str: The namespace of this blob.

        All blobs are stored and indexed under a namespace. Namespaces are allowed
        a restricted alphabet (``a-zA-Z0-9:._-``), and must begin with the user's
        org name, or their unique user hash if the user has no org. The required
        prefix is seperated from the rest of the namespace name (if any) by a ``:``.
        If not provided, the namespace will default to the users org (if any) and
        the unique user hash. The combined length of the ``namespace`` and the
        ``name`` cannot exceed 979 bytes.

        *Searchable, sortable*.
        """,
    )
    name = TypedAttribute(
        str,
        doc="""str: The name of this blob.

        All blobs are stored and indexed by name. Names are allowed
        a restricted alphabet (``a-zA-Z0-9:._/-``), but may not begin or end with a
        ``/``. The combined length of the ``namespace`` and the ``name`` cannot exceed
        979 bytes.

        The ``/`` is intended to be used like a directory in a pathname to allow for
        prefix search operations, but otherwise has no special meaning.

        *Searchable, sortable*.
        """,
    )
    storage_state = EnumAttribute(
        StorageState,
        doc="""str or StorageState: Storage state of the blob.

        The state is `~StorageState.AVAILABLE` if the data is available and can be
        retrieved, `~StorageState.REMOTE` if the data is not currently available.

        *Filterable, sortable*.
        """,
    )
    storage_type = EnumAttribute(
        StorageType,
        doc="""str or StorageType: Storage type of the blob.

        `~StorageType.DATA` is managed by end users (e.g. via
        :py:meth:`earthdaily.earthone.catalog.Blob.upload`.
        Other types are generated and managed by various components of the platform.

        *Filterable, sortable*.
        """,
    )
    description = TypedAttribute(
        str,
        doc="""str, optional: A description with further details on this blob.

        The description can be up to 80,000 characters and is used by
        :py:meth:`Search.find_text`.

        *Searchable*
        """,
    )
    geometry = GeometryAttribute(
        doc="""str or shapely.geometry.base.BaseGeometry, optional: Geometry representing the location for the blob.

        *Filterable*

        (use :py:meth:`BlobSearch.intersects
        <earthdaily.earthone.catalog.BlobSearch.intersects>` to search based on geometry)
        """
    )
    expires = Timestamp(
        doc="""str or datetime, optional: Timestamp when the blob should be expired and deleted.

        *Filterable, sortable*.
        """
    )
    href = TypedAttribute(
        str,
        doc="""str, optional: Storage location for the blob.

        This attribute may not be set by the end user.
        """,
    )
    size_bytes = TypedAttribute(
        int,
        doc="""int, optional: Size of the blob in bytes.

        *Filterable, sortable*.
        """,
    )
    hash = TypedAttribute(
        str, doc="""str, optional: Content hash (MD5) for the blob."""
    )

    @classmethod
    def namespace_id(cls, namespace_id, client=None):
        """Generate a fully namespaced id.

        Parameters
        ----------
        namespace_id : str or None
            The unprefixed part of the id that you want prefixed.
        client : CatalogClient, optional
            A `CatalogClient` instance to use for requests to the EarthOne
            catalog.  The
            :py:meth:`~earthdaily.earthone.catalog.CatalogClient.get_default_client` will
            be used if not set.

        Returns
        -------
        str
            The fully namespaced id.

        Example
        -------
        >>> namespace = Blob.namespace_id("myproject") # doctest: +SKIP
        'myorg:myproject' # doctest: +SKIP
        """
        if client is None:
            client = CatalogClient.get_default_client()
        org = client.auth.payload.get("org")
        namespace = client.auth.namespace

        if not namespace_id:
            if org:
                return f"{org}:{namespace}"
            else:
                return namespace
        elif org:
            if namespace_id == org or namespace_id.startswith(org + ":"):
                return namespace_id
            else:
                return f"{org}:{namespace_id}"
        elif namespace_id == namespace or namespace_id.startswith(namespace + ":"):
            return namespace_id
        else:
            return f"{namespace}:{namespace_id}"

    @classmethod
    def get(
        cls,
        id=None,
        storage_type=StorageType.DATA,
        namespace=None,
        name=None,
        client=None,
        request_params=None,
        headers=None,
    ):
        """Get an existing Blob from the EarthOne catalog.

        If the Blob is found, it will be returned in the
        `~earthdaily.earthone.catalog.DocumentState.SAVED` state.  Subsequent changes will
        put the instance in the `~earthdaily.earthone.catalog.DocumentState.MODIFIED` state,
        and you can use :py:meth:`save` to commit those changes and update the EarthOne
        catalog object.  Also see the example for :py:meth:`save`.

        Exactly one of the ``id`` and ``name`` parameters must be specified. If ``name``
        is specified, it is used together with the ``storage_type`` and ``namespace``
        parameters to form the corresponding ``id``.

        Parameters
        ----------
        id : str, optional
            The id of the object you are requesting. Required unless ``name`` is supplied.
            May not be specified if ``name`` is specified.
        storage_type : StorageType, optional
            The storage type of the Blob you wish to retrieve. Defaults to ``data``. Ignored
            unless ``name`` is specified.
        namespace : str, optional
            The namespace of the Blob you wish to retrieve. Defaults to the user's org name
            (if any) plus the unique user hash. Ignored unless ``name`` is specified.
        name : str, optional
            The name of the Blob you wish to retrieve. Required if ``id`` is not specified.
            May not be specified if ``id`` is specified.
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
        if (not id and not name) or (id and name):
            raise TypeError("Must specify exactly one of id or name parameters")
        if not id:
            id = f"{storage_type}/{Blob.namespace_id(namespace)}/{name}"
        return super(cls, Blob).get(
            id, client=client, request_params=request_params, headers=headers
        )

    @classmethod
    def get_or_create(
        cls,
        id=None,
        storage_type=StorageType.DATA,
        namespace=None,
        name=None,
        client=None,
        **kwargs,
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
        id : str, optional
            The id of the object you are requesting. Required unless ``name`` is supplied.
            May not be specified if ``name`` is specified.
        storage_type : StorageType, optional
            The storage type of the Blob you wish to retrieve. Defaults to ``data``. Ignored
            unless ``name`` is specified.
        namespace : str, optional
            The namespace of the Blob you wish to retrieve. Defaults to the user's org name
            (if any) plus the unique user hash. Ignored unless ``name`` is specified.
        name : str, optional
            The name of the Blob you wish to retrieve. Required if ``id`` is not specified.
            May not be specified if ``id`` is specified.
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
        if (not id and not name) or (id and name):
            raise TypeError("Must specify exactly one of id or name parameters")
        if not id:
            namespace = cls.namespace_id(namespace)
            id = f"{storage_type}/{namespace}/{name}"
            kwargs["storage_type"] = storage_type
            kwargs["namespace"] = namespace
            kwargs["name"] = name

        return super(cls, Blob).get_or_create(id, client=client, **kwargs)

    @classmethod
    def search(cls, client=None, request_params=None, headers=None):
        """A search query for all blobs.

        Return an `~earthdaily.earthone.catalog.BlobSearch` instance for searching
        blobs in the EarthOne catalog.  This instance extends the
        :py:class:`~earthdaily.earthone.catalog.Search` class with the
        :py:meth:`~earthdaily.earthone.catalog.BlobSearch.summary` and
        :py:meth:`~earthdaily.earthone.catalog.BlobSearch.summary_interval` methods
        which return summary statistics about the blobs that match the search query.

        Parameters
        ----------
        client : :class:`CatalogClient`, optional
            A `CatalogClient` instance to use for requests to the EarthOne
            catalog.

        Returns
        -------
        :class:`~earthdaily.earthone.catalog.BlobSearch`
            An instance of the `~earthdaily.earthone.catalog.BlobSearch` class

        Example
        -------
        >>> from earthdaily.earthone.catalog import Blob
        >>> search = Blob.search().limit(10)
        >>> for result in search: # doctest: +SKIP
        ...     print(result.name) # doctest: +SKIP

        """
        return BlobSearch(
            cls, client=client, request_params=request_params, headers=headers
        )

    @check_deleted
    def upload(self, file):
        """Uploads storage blob from a file.

        Uploads data from a file and creates the Blob.

        The Blob must be in the state `~earthdaily.earthone.catalog.DocumentState.UNSAVED`.
        The `storage_state`, `storage_type`, `namespace`, and the `name` attributes,
        must all be set. If either the `size_bytes` and the `hash` attributes are set,
        they must agree with the actual file to be uploaded, and will be validated
        during the upload process.

        On return, the Blob object will be updated to reflect the full state of the
        new blob.

        Parameters
        ----------
        file : str or io.IOBase
            File or files to be uploaded.  Can be string with path to the file in the
            local filesystem, or a file-like object (``io.IOBase``). If a file like
            object and already open, must be binary mode and readable. Open file-like
            objects remain open on return and must be closed by the caller.

        Returns
        -------
        Blob
            The uploaded instance.

        Raises
        ------
        ValueError
            If any improper arguments are supplied.
        DeletedObjectError
            If this blob was deleted.
        """
        self.namespace = self.__class__.namespace_id(self.namespace)
        if not self.name:
            raise ValueError("name field required")
        if not self.storage_state:
            self.storage_state = StorageState.AVAILABLE
        if not self.storage_type:
            self.storage_type = StorageType.DATA

        if self.state != DocumentState.UNSAVED:
            raise ValueError(
                "Blob {} has been saved. Please use an unsaved blob for uploading".format(
                    self.id
                )
            )

        if isinstance(file, str):
            file = io.open(file, "rb")
            close = True
        elif isinstance(file, io.IOBase):
            close = file.closed
            if close:
                file = io.open(file.name, "rb")
            elif not file.readable() or "b" not in file.mode:
                raise ValueError("Invalid file is open but not readable or binary mode")
        else:
            raise ValueError("Invalid file value: must be string or IOBase")

        try:
            return self._do_upload(file)
        finally:
            if close:
                file.close()

    @check_deleted
    def upload_data(self, data):
        """Uploads storage blob from a bytes or str.

        Uploads data from a string or bytes and creates the Blob.

        The Blob must be in the state `~earthdaily.earthone.catalog.DocumentState.UNSAVED`.
        The `storage_state`, `storage_type`, `namespace`, and the `name` attributes,
        must all be set. If either the `size_bytes` and the `hash` attributes are set,
        they must agree with the actual data to be uploaded, and will be validated
        during the upload process.

        On return, the Blob object will be updated to reflect the full state of the
        new blob.

        Parameters
        ----------
        data : str or bytes
            Data to be uploaded. A str will be default encoded to bytes.

        Returns
        -------
        Blob
            The uploaded instance.

        Raises
        ------
        ValueError
            If any improper arguments are supplied.
        DeletedObjectError
            If this blob was deleted.
        """
        self.namespace = self.__class__.namespace_id(self.namespace)
        if not self.name:
            raise ValueError("name field required")
        if not self.storage_state:
            self.storage_state = StorageState.AVAILABLE
        if not self.storage_type:
            self.storage_type = StorageType.DATA

        if self.state != DocumentState.UNSAVED:
            raise ValueError(
                "Blob {} has been saved. Please use an unsaved blob for uploading".format(
                    self.id
                )
            )

        if isinstance(data, str):
            data = data.encode()
        elif not isinstance(data, bytes):
            raise ValueError("Invalid data value: must be string or bytes")

        return self._do_upload(data)

    # the upload implementation is broken out so it can be used from multiple methods
    def _do_upload(self, src):
        # import here for circular dependency
        from .blob_upload import BlobUpload

        # Request an upload url
        upload = BlobUpload(client=self._client, storage=self)

        upload.save()

        headers = {}
        headers["content-type"] = "application/octet-stream"
        if upload.storage.size_bytes:
            headers["content-length"] = str(upload.storage.size_bytes)

        # This should work but it doesn't. The header must be the base64
        # encoding of the 16 binary MD5 checksum bytes. But the value
        # that is is checked against by S3 is the hex-ified version of the
        # 16 binary bytes. So even though they mean the same thing,
        # they miscompare at S3 and the file upload fails.
        # if upload.storage.hash:
        #     headers["content-md5"] = upload.storage.hash

        # do the upload
        self._url_client.session.put(upload.resumable_url, data=src, headers=headers)

        # save the blob
        upload.storage.save(request_params={"upload_signature": upload.signature})

        # replenish our state, like reload but no need to go to server.
        # this will effectively wipe all current state & caching.
        self._initialize(
            saved=True,
            **upload.storage._attributes,
        )

        return self

    @check_deleted
    def download(self, file, range=None):
        """Downloads storage blob to a file.

        Downloads data from the blob to a file.

        The Blob must be in the state `~earthdaily.earthone.catalog.DocumentState.SAVED`.

        Parameters
        ----------
        file : str or io.IOBase
            Where to write the downloaded blob. Can be string with path to the file in the
            local filesystem, or an file opened for writing (``io.IOBase``). If a file like
            object and already open, must be binary mode and writable. Open file-like
            objects remain open on return and must be closed by the caller.
        range : str or list, optional
            Range(s) of blob to be downloaded. Can either be a string in the standard
            HTTP Range header format (e.g. "bytes=0-99"), or a list or tuple containing
            one or two integers (e.g. ``(0, 99)``), or a list or tuple of the same
            (e.g. ``((0, 99), (200-299))``). A list or tuple of one integer implies
            no upper bound; in this case the integer can be negative, indicating the
            count back from the end of the blob.

        Returns
        -------
        str
            The name of the downloaded file.

        Raises
        ------
        ValueError
            If any improper arguments are supplied.
        DeletedObjectError
            If this blob was deleted.
        """
        if self.state != DocumentState.SAVED:
            raise ValueError("Blob {} has not been saved".format(self.id))

        if isinstance(file, str):
            file = io.open(file, "wb")
        elif isinstance(file, io.IOBase):
            close = file.closed
            if close:
                file = io.open(file.name, "wb")
            elif not file.writable() or "b" not in file.mode:
                raise ValueError("Invalid file is open but not writable or binary mode")
        else:
            raise ValueError("Invalid file value: must be string or IOBase")

        return self._do_download(dest=file, range=range)

    @check_deleted
    def data(self, range=None):
        """Downloads storage blob data.

        Downloads data from the blob and returns as a bytes object.

        The Blob must be in the state `~earthdaily.earthone.catalog.DocumentState.SAVED`.

        Parameters
        ----------
        range : str or list, optional
            Range(s) of blob to be downloaded. Can either be a string in the standard
            HTTP Range header format (e.g. "bytes=0-99"), or a list or tuple containing
            one or two integers (e.g. ``(0, 99)``), or a list or tuple of the same
            (e.g. ``((0, 99), (200-299))``). A list or tuple of one integer implies
            no upper bound; in this case the integer can be negative, indicating the
            count back from the end of the blob.

        Returns
        -------
        bytes
            The data retrieved from the Blob.

        Raises
        ------
        ValueError
            If any improper arguments are supplied.
        DeletedObjectError
            If this blob was deleted.
        """
        if self.state != DocumentState.SAVED:
            raise ValueError("Blob {} has not been saved".format(self.id))

        return self._do_download(range=range)

    @check_deleted
    def iter_data(self, chunk_size=None, range=None):
        """Downloads storage blob data.

        Downloads data from the blob and returns as an iterator (generator)
        which will yield the data (as a bytes) in chunks. This enables the
        processing of very large files.

        The Blob must be in the state `~earthdaily.earthone.catalog.DocumentState.SAVED`.

        Parameters
        ----------
        chunk_size : int, optional
            Size of chunks over which to iterate. Default is whatever size chunks
            are received.
        range : str or list, optional
            Range(s) of blob to be downloaded. Can either be a string in the standard
            HTTP Range header format (e.g. "bytes=0-99"), or a list or tuple containing
            one or two integers (e.g. ``(0, 99)``), or a list or tuple of the same
            (e.g. ``((0, 99), (200-299))``). A list or tuple of one integer implies
            no upper bound; in this case the integer can be negative, indicating the
            count back from the end of the blob.

        Returns
        -------
        generator
            An iterator over the blob data.

        Raises
        ------
        ValueError
            If any improper arguments are supplied.
        DeletedObjectError
            If this blob was deleted.
        """
        if self.state != DocumentState.SAVED:
            raise ValueError("Blob {} has not been saved".format(self.id))

        def generator(response):
            try:
                yield from response.iter_content(chunk_size)
            finally:
                response.close()

        return self._do_download(dest=generator, range=range)

    @check_deleted
    def iter_lines(self, decode_unicode=False, delimiter=None):
        """Downloads storage blob data.

        Downloads data from the blob and returns as an iterator (generator)
        which will yield the data as text lines.  This enables the
        processing of very large files.

        The Blob must be in the state `~earthdaily.earthone.catalog.DocumentState.SAVED`.
        The data within the blob must represent encoded text.

        .. note:: This method is not reentrant safe.

        Parameters
        ----------
        decode_unicode : bool, optional
            If true, then decode unicode in the incoming data and return
            strings. Default is to return bytes.
        delimiter : str or byte, optional
            Delimiter for lines. Type depends on setting of `decode_unicode`.
            Default is to use default line break sequence.

        Returns
        -------
        generator
            An iterator over the blob byte or text lines, depending on
            value of `decode_unicode`.

        Raises
        ------
        ValueError
            If any improper arguments are supplied.
        DeletedObjectError
            If this blob was deleted.
        """
        if self.state != DocumentState.SAVED:
            raise ValueError("Blob {} has not been saved".format(self.id))

        def generator(response):
            if decode_unicode:
                # response will always claim to be application/octet-stream
                response.encoding = "utf-8"
            try:
                yield from response.iter_lines(
                    decode_unicode=decode_unicode, delimiter=delimiter
                )
            finally:
                response.close()

        return self._do_download(dest=generator)

    @classmethod
    def get_data(
        cls,
        id=None,
        storage_type=StorageType.DATA,
        namespace=None,
        name=None,
        client=None,
        range=None,
        stream=False,
        chunk_size=None,
    ):
        """Downloads storage blob data.

        Downloads data for a given blob id and returns as a bytes object.

        Parameters
        ----------
        id : str, optional
            The id of the object you are requesting. Required unless ``name`` is supplied.
            May not be specified if ``name`` is specified.
        storage_type : StorageType, optional
            The storage type of the Blob you wish to retrieve. Defaults to ``data``. Ignored
            unless ``name`` is specified.
        namespace : str, optional
            The namespace of the Blob you wish to retrieve. Defaults to the user's org name
            (if any) plus the unique user hash. Ignored unless ``name`` is specified.
        name : str, optional
            The name of the Blob you wish to retrieve. Required if ``id`` is not specified.
            May not be specified if ``id`` is specified.
        client : Client, optional
            Client instance. If not given, the default client will be used.
        range : str or list, optional
            Range(s) of blob to be downloaded. Can either be a string in the standard
            HTTP Range header format (e.g. "bytes=0-99"), or a list or tuple containing
            one or two integers (e.g. ``(0, 99)``), or a list or tuple of the same
            (e.g. ``((0, 99), (200-299))``). A list or tuple of one integer implies
            no upper bound; in this case the integer can be negative, indicating the
            count back from the end of the blob.
        stream : bool, optional
            If True, return a generator that will yield the data in chunks. Defaults to False.
        chunk_size : int, optional
            If stream is True, the size of chunks over which to stream. Default is whatever
            chunks are received on the wire.

        Returns
        -------
        bytes or generator
            The data retrieved from the Blob. If stream is True, returned as an iterator
            (generator) which will yeild the data in chunks.

        Raises
        ------
        ValueError
            If any improper arguments are supplied.
        NotFoundError
            If the Blob does not exist.
        DeletedObjectError
            If this blob was deleted.
        """
        if (not id and not name) or (id and name):
            raise TypeError("Must specify exactly one of id or name parameters")
        if not id:
            id = f"{storage_type}/{cls.namespace_id(namespace)}/{name}"

        dest = None
        if stream:

            def generator(response):
                try:
                    yield from response.iter_content(chunk_size)
                finally:
                    response.close()

            dest = generator

        return cls(id=id, client=client)._do_download(dest=dest, range=range)

    @classmethod
    def delete_many(
        cls, ids, raise_on_missing=False, wait_for_completion=False, client=None
    ):
        """Delete many blobs from the EarthOne catalog.

        Only those blobs that exist and are owned by the user will be deleted.
        No errors will be raised for blobs that do not exist or are visible but
        not owned by the user. If you need to know, compare the supplied list of
        ids with the returned list of deleted ids.

        All blobs to be deleted must belong to the same purchase.

        Parameters
        ----------
        ids : list(str)
            A list of blob ids to delete.
        raise_on_missing : bool, optional
            If True, raise an exception if any of the blobs are not found, otherwise ignore
            missing blobs. Defaults to False.
        wait_for_completion : bool, optional
            If True, wait for the deletion to complete before returning. Defaults to False.
        client : CatalogClient, optional
            A `CatalogClient` instance to use for requests to the EarthOne catalog.
            The :py:meth:`~earthdaily.earthone.catalog.CatalogClient.get_default_client` will
            be used if not set.

        Returns
        -------
        list(str)
            A list of the ids of the blobs that were successfully deleted.

        Raises
        ------
        ~earthdaily.earthone.exceptions.ClientError or ~earthdaily.earthone.exceptions.ServerError
            :ref:`Spurious exception <network_exceptions>` that can occur during a
            network request.
        """
        if client is None:
            client = CatalogClient.get_default_client()

        task_status = BlobDeletionTaskStatus.create(
            ids=ids, raise_on_missing=raise_on_missing, client=client
        )

        if wait_for_completion:
            task_status.wait_for_completion()

        return task_status.ids

    def _do_download(self, dest=None, range=None):
        download = BlobDownload.get(id=self.id, client=self._client)

        # BlobDownload.get() returns None if the blob does not exist
        # raise a NotFoundError in this case
        if not download:
            raise NotFoundError("Blob {} does not exist".format(self.id))

        headers = {}
        if self.hash:
            headers["if-match"] = self.hash
        if range:
            if isinstance(range, str):
                range_str = range
            elif isinstance(range, (list, tuple)) and all(
                map(lambda x: isinstance(x, int), range)
            ):
                if len(range) == 1:
                    range_str = f"bytes={range[0]}"
                elif len(range) == 2:
                    range_str = f"bytes={range[0]}-{range[1]}"
                else:
                    raise ValueError("invalid range value")
            else:
                raise ValueError("invalid range value")

            headers["range"] = range_str

        r = self._url_client.session.get(
            download.resumable_url, headers=headers, stream=True
        )
        r.raise_for_status()
        if callable(dest):
            # generator will close response
            return dest(r)
        else:
            try:
                if dest is None:
                    return r.raw.read()
                else:
                    for chunk in r.iter_content(1048576):
                        dest.write(chunk)
                    return dest.name
            finally:
                r.close()

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
        BlobDeletionTaskStatus
            The status of the deletion task which can be used to wait for completion. ``None`` if the
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

        There is also an instance ``delete`` method that can be used to delete a blob.
        It accepts no parameters and also returns a ``BlobDeletionTaskStatus``. Once
        deleted, you cannot use the blob and should release any references.
        """
        if client is None:
            client = CatalogClient.get_default_client()

        try:
            return BlobDeletionTaskStatus.create(
                ids=[id], raise_on_missing=True, client=client
            )
        except NotFoundError:
            return None

    @delete.instancemethod
    @check_deleted
    def delete(self):
        """Delete this catalog object from the EarthOne catalog.

        Once deleted, you cannot use the catalog object and should release any
        references.

        Returns
        -------
        BlobDeletionTaskStatus
            The status of the deletion task which can be used to wait for completion.

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

        task_status = BlobDeletionTaskStatus.create(
            ids=[self.id], raise_on_missing=True, client=self._client
        )
        self._deleted = True  # non-200 will raise an exception
        return task_status


class BlobCollection(Collection):
    _item_type = Blob


# handle circular references
Blob._collection_type = BlobCollection


class BlobDeletionTaskStatus(TaskStatus):
    """The asynchronous deletion task's status

    Attributes
    ----------
    id : str
        The id of the object for which this task is running.
    status : TaskState
        The state of the task as explained in `TaskState`.
    start_datetime : datetime
        The date and time at which the task started running.
    duration_in_seconds : float
        The duration of the task.
    objects_deleted : int
        The number of objects (a combination of bands or images) that were deleted.
    errors : list
        In case the status is ``FAILED`` this will contain a list of errors
        that were encountered.  In all other states this will not be set.
    ids : list
        The ids of the objects that were deleted.
    """

    _task_name = "delete task"
    _url = "/storage/delete/{}"

    def __init__(self, objects_deleted=None, ids=None, **kwargs):
        super(BlobDeletionTaskStatus, self).__init__(**kwargs)
        self.objects_deleted = objects_deleted
        self.ids = ids

    @classmethod
    def create(cls, ids, raise_on_missing, client):
        # TaskStatus objects are not catalog objects so we need to do this manually
        response = client.session.post(
            "/storage/delete",
            json={
                "data": {
                    "attributes": {
                        "ids": ids,
                        "raise_on_missing": raise_on_missing,
                    },
                    "type": "storage_delete",
                }
            },
        )

        if response.status_code == 201:
            data = response.json()["data"]
            return BlobDeletionTaskStatus(
                id=data["id"], _client=client, **data["attributes"]
            )
        else:
            return None

    def __repr__(self):
        text = super(BlobDeletionTaskStatus, self).__repr__()

        if self.objects_deleted:
            text += "\n  - {:,} objects deleted".format(self.objects_deleted)

        return text
