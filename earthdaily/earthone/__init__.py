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

"""EarthOne Python Client

.. code-block:: bash

    pip install earthdaily-earthone[complete]

Documentation is available at https://earthone.earthdaily.com/docs.

Source code and version information is at
https://github.com/earthdaily/earthone-python.

The EarthOne Platform simplifies analysis of **global-scale raster data**
by providing:

    * Access to a catalog of petabytes of disparate geospatial data,
      all normalized and interoperable through one **common interface**
    * A Python client library to access these systems
"""

# This is required in order to support namespace packages
# PEP420 is not sufficient because of legacy usage patterns
# and the three levels of earthdaily, earthdaily.earthone,
# and earthdaily.earthone.dynamic_compute all being packaged
# separately.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # noqa: F821

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("earthdaily-earthone")
except PackageNotFoundError:
    from earthdaily.earthone.core.client import __version__

from earthdaily.earthone import auth
from earthdaily.earthone import config
from earthdaily.earthone import exceptions
from earthdaily.earthone import geo
from earthdaily.earthone import utils
from earthdaily.earthone import catalog
from earthdaily.earthone import compute
from earthdaily.earthone import vector

select_env = config.select_env
get_settings = config.get_settings

__author__ = "EarthDaily"

__all__ = [
    "__author__",
    "__version__",
    "auth",
    "catalog",
    "compute",
    "config",
    "exceptions",
    "geo",
    "get_settings",
    "select_env",
    "utils",
    "vector",
]
