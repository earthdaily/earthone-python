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

import sys
import warnings

if sys.version_info < (3, 10):
    msg = "Python version {}.{} not supported by the EarthOne client".format(
        sys.version_info.major, sys.version_info.minor
    )
    raise ImportError(msg)

if sys.version_info >= (3, 14):
    msg = "Python version {}.{} is not supported yet. You may encounter unexpected errors.".format(
        sys.version_info.major, sys.version_info.minor
    )
    warnings.warn(msg, FutureWarning)


def clear_client_state():
    """Clear all cached client state."""
    from earthdaily.earthone.auth import Auth
    from ..common.http.service import DefaultClientMixin
    from ..catalog.helpers import (
        BANDS_BY_PRODUCT_CACHE as catalog_bands_by_product_cache,
    )

    Auth.set_default_auth(None)
    DefaultClientMixin.clear_all_default_clients()
    catalog_bands_by_product_cache.clear()


__all__ = ["clear_client_state"]
