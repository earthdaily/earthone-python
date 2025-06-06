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

import base64
import json
import json as jsonlib
import os
import time
import urllib.parse
import uuid
from datetime import datetime, timezone
from unittest import TestCase

import responses
from requests import PreparedRequest

from earthdaily.earthone.auth import Auth
from earthdaily.earthone.config import get_settings


from ..compute_client import ComputeClient
from ..function import FunctionStatus
from ..job import JobStatus


def make_uuid():
    return str(uuid.uuid4())


class BaseTestCase(TestCase):
    compute_url = get_settings().compute_url

    def setUp(self):
        # make sure all of these are gone, so our Auth is only a JWT
        for envvar in (
            "CLIENT_ID",
            "EARTHONE_CLIENT_ID",
            "CLIENT_SECRET",
            "EARTHONE_CLIENT_SECRET",
            "EARTHONE_REFRESH_TOKEN",
            "EARTHONE_TOKEN",
        ):
            if envvar in os.environ:
                del os.environ[envvar]

        responses.mock.assert_all_requests_are_fired = True
        self.now = datetime.now(timezone.utc).replace(tzinfo=None)

        payload = (
            base64.b64encode(
                json.dumps(
                    {
                        "aud": "client-id",
                        "exp": time.time() + 3600,
                    }
                ).encode()
            )
            .decode()
            .strip("=")
        )
        token = f"header.{payload}.signature"
        auth = Auth(jwt_token=token, token_info_path=None)
        ComputeClient.set_default_client(ComputeClient(auth=auth))

    def tearDown(self):
        responses.mock.assert_all_requests_are_fired = False

    def mock_credentials(self):
        responses.add(responses.GET, f"{self.compute_url}/credentials")

    def mock_response(self, method, uri, json=None, status=200, **kwargs):
        if json is not None:
            kwargs["json"] = json

        responses.add(
            method,
            f"{self.compute_url}{uri}",
            status=status,
            **kwargs,
        )

    def mock_job_create(self, data: dict):
        job = self.make_job(**data)
        self.mock_response(responses.POST, "/jobs", json=job)

    def make_page(
        self,
        data: list,
        page: int = 1,
        page_size: int = 100,
        page_cursor: str = None,
        last_page: int = None,
    ):
        return {
            "meta": {
                "current_page": page,
                "last_page": last_page or page,
                "page_size": page_size,
                "next_page": page + 1,
                "page_cursor": page_cursor,
            },
            "data": data,
        }

    def make_job(self, **data):
        job = {
            "id": make_uuid(),
            "function_id": make_uuid(),
            "args": None,
            "kwargs": None,
            "creation_date": self.now.isoformat(),
            "status": JobStatus.PENDING,
        }
        job.update(data)

        return job

    def make_function(self, **data):
        if "cpus" in data:
            data["cpus"] = float(data["cpus"])

        if "memory" in data:
            data["memory"] = int(data["memory"])

        function = {
            "id": make_uuid(),
            "creation_date": self.now.isoformat(),
            "status": FunctionStatus.AWAITING_BUNDLE,
        }
        function.update(data)

        return function

    def assert_url_called(self, uri, times=1, json=None, body=None, params=None):
        if json and body:
            raise ValueError("Using json and body together does not make sense")

        url = f"{self.compute_url}{uri}"
        calls = [call for call in responses.calls if call.request.url.startswith(url)]
        assert calls, f"No requests were made to uri: {uri}"

        data = json or body
        matches = []
        calls_with_data = []
        calls_with_params = set()

        for call in calls:
            request: PreparedRequest = call.request

            if json is not None:
                request_data = jsonlib.loads(request.body)
            else:
                request_data = request.body

            if request_data:
                calls_with_data.append(request.body.decode())

            if params is not None:
                request_params = {}

                for key, value in urllib.parse.parse_qsl(
                    urllib.parse.urlsplit(request.url).query
                ):
                    try:
                        value = jsonlib.loads(value)
                    except jsonlib.JSONDecodeError:
                        value = value

                    if key in request_params:
                        values = request_params[key]

                        if not isinstance(values, list):
                            values = [values]

                        values.append(value)
                    else:
                        values = value

                    request_params[key] = values

                if request_params:
                    calls_with_params.add(jsonlib.dumps(request_params))
            else:
                request_params = None

            if (data is None or request_data == data) and (
                params is None or request_params == params
            ):
                matches.append(call)

        count = len(matches)
        msg = f"Expected {times} calls found {count} for {uri}"

        if data is not None:
            msg += f" with data: {data}"

            if calls_with_data:
                msg += "\n\nData:\n" + "\n".join(calls_with_data)

        if params is not None:
            msg += f" with params: {params}"

            if calls_with_params:
                msg += "\n\nParams:\n" + "\n".join(calls_with_params)

        assert count == times, msg

    # this was removed from python 3.12 unittest.TestCase
    def assertDictContainsSubset(self, subset, dictionary):
        for key, value in subset.items():
            assert key in dictionary and dictionary[key] == value
