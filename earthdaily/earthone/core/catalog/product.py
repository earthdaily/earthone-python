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

from ..common.collection import Collection
from ..common.property_filtering import Properties
from .attributes import (
    BooleanAttribute,
    ListAttribute,
    Resolution,
    Timestamp,
    TypedAttribute,
)
from .catalog_base import (
    AuthCatalogObject,
    CatalogClient,
    check_deleted,
)
from .task import TaskStatus


properties = Properties()


class Product(AuthCatalogObject):
    """A raster product that connects band information to imagery.

    Instantiating a product indicates that you want to create a *new* EarthOne
    catalog product.  If you instead want to retrieve an existing catalog product use
    `Product.get() <earthdaily.earthone.catalog.Product.get>`, or if you're not sure
    use `Product.get_or_create() <earthdaily.earthone.catalog.Product.get_or_create>`.
    You can also use `Product.search() <earthdaily.earthone.catalog.Product.search>`.
    Also see the example for :py:meth:`~earthdaily.earthone.catalog.Product.save`.


    Parameters
    ----------
    client : CatalogClient, optional
        A `CatalogClient` instance to use for requests to the EarthOne catalog.
        The :py:meth:`~earthdaily.earthone.catalog.CatalogClient.get_default_client` will
        be used if not set.
    kwargs : dict
        With the exception of readonly attributes (`created`, `modified`,
        `resolution_min`, and `resolution_max`) and with the exception of properties
        (`ATTRIBUTES`, `is_modified`, and `state`), any attribute listed below can
        also be used as a keyword argument.  Also see
        `~Product.ATTRIBUTES`.
    """

    _doc_type = "product"
    _url = "/products"
    # _collection_type set below due to circular problems

    # Product Attributes
    name = TypedAttribute(
        str,
        doc="""str: The name of this product.

        This should not be confused with a band name or image name.  Unlike the band
        name and image name, this name is not unique and purely for display purposes
        and is used by :py:meth:`Search.find_text`.  It can contain a string with up
        to 2000 arbitrary characters.

        *Searchable, sortable*.
        """,
    )
    description = TypedAttribute(
        str,
        doc="""str, optional: A description with further details on this product.

        The description can be up to 80,000 characters and is used by
        :py:meth:`Search.find_text`.

        *Searchable*
        """,
    )
    is_core = BooleanAttribute(
        doc="""bool, optional: Whether this is a EarthOne catalog core product.

        A core product is a product that is fully supported by EarthOne.  By
        default this value is ``False`` and you must have a special permission
        (``internal:core:create``) to set it to ``True``.

        *Filterable, sortable*.
        """
    )
    revisit_period_minutes_min = TypedAttribute(
        float,
        coerce=True,
        doc="""float, optional: Minimum length of the time interval between observations.

        The minimum length of the time interval between observations of any given area
        in minutes.

        *Filterable, sortable*.
        """,
    )
    revisit_period_minutes_max = TypedAttribute(
        float,
        coerce=True,
        doc="""float, optional: Maximum length of the time interval between observations.

        The maximum length of the time interval between observations of any given area
        in minutes.

        *Filterable, sortable*.
        """,
    )
    start_datetime = Timestamp(
        doc="""str or datetime, optional: The beginning of the mission for this product.

        *Filterable, sortable*.
        """
    )
    end_datetime = Timestamp(
        doc="""str or datetime, optional: The end of the mission for this product.

        *Filterable, sortable*.
        """
    )
    resolution_min = Resolution(
        readonly=True,
        doc="""Resolution, readonly: Minimum resolution of the bands for this product.

        If applying a filter with a plain unitless number the value is assumed to be
        in meters.

        *Filterable, sortable*.
        """,
    )
    resolution_max = Resolution(
        readonly=True,
        doc="""Resolution, readonly: Maximum resolution of the bands for this product.

        If applying a filter with a plain unitless number the value is assumed to be
        in meters.

        *Filterable, sortable*.
        """,
    )
    default_display_bands = ListAttribute(
        TypedAttribute(str),
        doc="""list(str) or iterable: Which bands to use for RGBA display.

        This field defines the default bands that are used for display purposes.  There are
        four supported formats: ``["greyscale-or-class"]``, ``["greyscale-or-class", "alpha"]``,
        ``["red", "green", "blue"]``, and ``["red", "green", "blue", "alpha"]``.
        """,
    )
    image_index_name = TypedAttribute(
        str,
        doc="""str: The name of the image index for this product.

        This is an internal field, accessible to privileged users only.

        *Filterable, sortable*.
        """,
    )
    product_tier = TypedAttribute(
        str,
        doc="""str: Product tier for this product.

        This field can be set by privileged users only.

        *Filterable, sortable*.
        """,
    )

    def named_id(self, name):
        """Return the ~earthdaily.earthone.catalog.NamedCatalogObject.id` for the given named catalog object.

        Parameters
        ----------
        name : str
            The name of the catalog object within this product, see
            :py:attr:`~earthdaily.earthone.catalog.NamedCatalogObject.name`.

        Returns
        -------
        str
            The named catalog object id within this product.
        """
        return "{}:{}".format(self.id, name)

    @check_deleted
    def get_band(self, name, client=None, request_params=None, headers=None):
        """Retrieve the request band associated with this product by name.

        Parameters
        ----------
        name : str
            The name of the band to retrieve.
        client : CatalogClient, optional
            A `CatalogClient` instance to use for requests to the EarthOne
            catalog.  The
            :py:meth:`~earthdaily.earthone.catalog.CatalogClient.get_default_client` will
            be used if not set.

        Returns
        -------
        Band or None
            A derived class of `Band` that represents the requested band object if
            found, ``None`` if not found.

        """
        from .band import Band

        return Band.get(
            self.named_id(name),
            client=client,
            request_params=request_params,
            headers=headers,
        )

    @check_deleted
    def get_image(self, name, client=None, request_params=None, headers=None):
        """Retrieve the request image associated with this product by name.

        Parameters
        ----------
        name : str
            The name of the image to retrieve.
        client : CatalogClient, optional
            A `CatalogClient` instance to use for requests to the EarthOne
            catalog.  The
            :py:meth:`~earthdaily.earthone.catalog.CatalogClient.get_default_client` will
            be used if not set.

        Returns
        -------
        ~earthdaily.earthone.catalog.Image or None
            The requested image if found, or ``None`` if not found.

        """
        from .image import Image

        return Image.get(
            self.named_id(name),
            client=client,
            request_params=request_params,
            headers=headers,
        )

    @check_deleted
    def delete_related_objects(self):
        """Delete all related bands and images for this product.

        Starts an asynchronous operation that deletes all bands and images associated
        with this product. If the product has a large number of associated images, this
        operation could take several minutes, or even hours.

        Returns
        -------
        DeletionTaskStatus
            Returns :py:class:`DeletionTaskStatus` if deletion task was successfully
            started and ``None`` if there were no related objects to delete.


        Raises
        ------
        ConflictError
            If a deletion process is already in progress.
        DeletedObjectError
            If this product was deleted.
        ~earthdaily.earthone.exceptions.ClientError or ~earthdaily.earthone.exceptions.ServerError
            :ref:`Spurious exception <network_exceptions>` that can occur during a
            network request.
        """
        r = self._client.session.post(
            "/products/{}/delete_related_objects".format(self.id),
            json={"data": {"type": "product_delete_task"}},
        )
        if r.status_code == 201:
            response = r.json()
            return DeletionTaskStatus(
                id=self.id, _client=self._client, **response["data"]["attributes"]
            )
        else:
            return None

    @check_deleted
    def get_delete_status(self):
        """Fetches the status of a deletion task.

        Fetches the status of a deletion task started using
        :py:meth:`delete_related_objects`.

        Returns
        -------
        DeletionTaskStatus

        Raises
        ------
        DeletedObjectError
            If this product was deleted.
        ~earthdaily.earthone.exceptions.ClientError or ~earthdaily.earthone.exceptions.ServerError
            :ref:`Spurious exception <network_exceptions>` that can occur during a
            network request.
        """
        r = self._client.session.get(
            "/products/{}/delete_related_objects".format(self.id)
        )
        response = r.json()
        return DeletionTaskStatus(
            id=self.id, _client=self._client, **response["data"]["attributes"]
        )

    @check_deleted
    def bands(self, request_params=None, headers=None):
        """A search query for all bands for this product, sorted by default band
        ``sort_order``.

        Returns
        -------
        :py:class:`~earthdaily.earthone.catalog.Search`
            A :py:class:`~earthdaily.earthone.catalog.Search` instance configured to
            find all bands for this product.

        Raises
        ------
        DeletedObjectError
            If this product was deleted.

        """
        from .band import Band

        return (
            Band.search(
                client=self._client, request_params=request_params, headers=headers
            )
            .filter(properties.product_id == self.id)
            .sort("sort_order")
        )

    @check_deleted
    def images(self, request_params=None, headers=None):
        """A search query for all images in this product.

        Returns
        -------
        :py:class:`~earthdaily.earthone.catalog.Search`
            A :py:class:`~earthdaily.earthone.catalog.Search` instance configured to
            find all images in this product.

        Raises
        ------
        DeletedObjectError
            If this product was deleted.

        """
        from .image import Image

        return Image.search(
            client=self._client, request_params=request_params, headers=headers
        ).filter(properties.product_id == self.id)

    @check_deleted
    def image_uploads(self):
        """A search query for all uploads in this product created by this user.

        Returns
        -------
        :py:class:`~earthdaily.earthone.catalog.Search`
            A :py:class:`~earthdaily.earthone.catalog.Search` instance configured to
            find all uploads in this product.

        Raises
        ------
        DeletedObjectError
            If this product was deleted.

        """
        from .image_upload import ImageUpload

        return ImageUpload.search(client=self._client).filter(
            properties.product_id == self.id
        )

    @classmethod
    def namespace_id(cls, id_, client=None):
        """Generate a fully namespaced id.

        Parameters
        ----------
        id_ : str
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
        >>> product_id = Product.namespace_id("my-product")
        """
        if client is None:
            client = CatalogClient.get_default_client()
        org = client.auth.payload.get("org")
        if org is None:
            org = client.auth.namespace  # defaults to the user namespace

        prefix = "{}:".format(org)
        if id_.startswith(prefix):
            return id_

        return "{}{}".format(prefix, id_)


class ProductCollection(Collection):
    _item_type = Product


# handle circular references
Product._collection_type = ProductCollection


class DeletionTaskStatus(TaskStatus):
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
    errors: list
        In case the status is ``FAILED`` this will contain a list of errors
        that were encountered.  In all other states this will not be set.
    """

    _task_name = "delete task"
    _url = "/products/{}/delete_related_objects"

    def __init__(self, objects_deleted=None, **kwargs):
        super(DeletionTaskStatus, self).__init__(**kwargs)
        self.objects_deleted = objects_deleted

    def __repr__(self):
        text = super(DeletionTaskStatus, self).__repr__()

        if self.objects_deleted:
            text += "\n  - {:,} objects deleted".format(self.objects_deleted)

        return text
