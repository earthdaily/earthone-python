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

"""
The Catalog Service provides access to products, bands, and images
available from EarthOne.
"""

from .task import TaskState
from .product import (
    DeletionTaskStatus,
    Product,
    ProductCollection,
)
from .band import (
    Band,
    BandCollection,
    BandType,
    ClassBand,
    Colormap,
    DataType,
    DerivedParamsAttribute,
    GenericBand,
    MaskBand,
    MicrowaveBand,
    ProcessingLevelsAttribute,
    ProcessingStepAttribute,
    SpectralBand,
)
from .blob import (
    Blob,
    BlobCollection,
    BlobDeletionTaskStatus,
    BlobSearch,
    BlobSummaryResult,
    StorageType,
)
from .event_api_destination import (
    EventApiDestination,
    EventApiDestinationCollection,
    EventApiDestinationSearch,
    EventConnectionParameter,
)
from .event_rule import EventRule, EventRuleCollection, EventRuleSearch, EventRuleTarget
from .event_schedule import EventSchedule, EventScheduleCollection, EventScheduleSearch
from .event_subscription import (
    ComputeFunctionCompletedEventSubscription,
    EventSubscription,
    EventSubscriptionCollection,
    EventSubscriptionComputeTarget,
    EventSubscriptionSearch,
    EventSubscriptionSqsTarget,
    EventSubscriptionTarget,
    EventType,
    NewImageEventSubscription,
    NewStorageEventSubscription,
    NewVectorEventSubscription,
    Placeholder,
    ScheduledEventSubscription,
)
from .image import Image, ImageSearch, ImageSummaryResult
from .image_types import ResampleAlgorithm, DownloadFileFormat
from .image_upload import (
    ImageUpload,
    ImageUploadEvent,
    ImageUploadEventSeverity,
    ImageUploadEventType,
    ImageUploadOptions,
    ImageUploadStatus,
    ImageUploadType,
    OverviewResampler,
)
from .image_collection import ImageCollection
from .search import (
    AggregateDateField,
    GeoSearch,
    Interval,
    Search,
    SummarySearchMixin,
)
from .catalog_base import (
    AuthCatalogObject,
    CatalogClient,
    CatalogObject,
    DeletedObjectError,
    UnsavedObjectError,
)
from .named_catalog_base import NamedCatalogObject
from .attributes import (
    AttributeValidationError,
    DocumentState,
    File,
    Resolution,
    ResolutionUnit,
    StorageState,
)

from ..common.property_filtering import Properties

properties = Properties()

__all__ = [
    "AggregateDateField",
    "AttributeValidationError",
    "AuthCatalogObject",
    "Band",
    "BandCollection",
    "BandType",
    "Blob",
    "BlobCollection",
    "BlobDeletionTaskStatus",
    "BlobSearch",
    "BlobSummaryResult",
    "CatalogClient",
    "CatalogObject",
    "ClassBand",
    "Colormap",
    "ComputeFunctionCompletedEventSubscription",
    "DataType",
    "DeletedObjectError",
    "DeletionTaskStatus",
    "DerivedParamsAttribute",
    "DocumentState",
    "DownloadFileFormat",
    "EventApiDestination",
    "EventApiDestinationCollection",
    "EventApiDestinationSearch",
    "EventConnectionParameter",
    "EventRule",
    "EventRuleCollection",
    "EventRuleSearch",
    "EventRuleTarget",
    "EventSchedule",
    "EventScheduleCollection",
    "EventScheduleSearch",
    "EventSubscription",
    "EventSubscriptionCollection",
    "EventSubscriptionComputeTarget",
    "EventSubscriptionSearch",
    "EventSubscriptionSqsTarget",
    "EventSubscriptionTarget",
    "EventType",
    "File",
    "GenericBand",
    "GeoSearch",
    "Image",
    "ImageCollection",
    "ImageSearch",
    "ImageUpload",
    "ImageUploadEvent",
    "ImageUploadEventSeverity",
    "ImageUploadEventType",
    "ImageUploadOptions",
    "ImageUploadStatus",
    "ImageUploadType",
    "ImageSummaryResult",
    "Interval",
    "MaskBand",
    "MicrowaveBand",
    "NamedCatalogObject",
    "NewImageEventSubscription",
    "NewStorageEventSubscription",
    "NewVectorEventSubscription",
    "OverviewResampler",
    "Placeholder",
    "ProcessingLevelsAttribute",
    "ProcessingStepAttribute",
    "Product",
    "ProductCollection",
    "properties",
    "ResampleAlgorithm",
    "Resolution",
    "ResolutionUnit",
    "ScheduledEventSubscription",
    "Search",
    "SpectralBand",
    "StorageState",
    "StorageType",
    "SummarySearchMixin",
    "TaskState",
    "UnsavedObjectError",
]
