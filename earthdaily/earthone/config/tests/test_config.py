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

import os
import unittest
from copy import deepcopy
from unittest.mock import patch

from earthdaily.earthone.auth import Auth
from earthdaily.earthone.exceptions import ConfigError

from .. import Settings


class TestSettings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Save settings and environment
        cls.settings = Settings._settings
        cls.environ = deepcopy(os.environ)

    def setUp(self):
        # Clear existing settings from test environment
        Settings._settings = None

    def tearDown(self):
        # Restore settings and environment
        Settings._settings = self.settings
        os.environ.clear()
        os.environ.update(self.environ)

    def test_select_env_default(self):
        settings = Settings.select_env()
        self.assertEqual(settings.current_env, os.environ.get("EARTHONE_ENV"))
        self.assertEqual(id(settings), id(Settings._settings))
        self.assertEqual(id(settings), id(Settings.get_settings()))

    @patch.dict(os.environ, {"EARTHONE_ENV": "production"})
    def test_select_env_from_env(self):
        settings = Settings.select_env()
        self.assertEqual(settings.current_env, "production")
        self.assertEqual(id(settings), id(Settings._settings))
        self.assertEqual(id(settings), id(Settings.get_settings()))

    # environment must be patched because select_env will alter it
    @patch.dict(os.environ, clear=True)
    def test_select_env_from_string(self):
        settings = Settings.select_env("production")
        self.assertEqual(settings.current_env, "production")
        self.assertEqual(id(settings), id(Settings._settings))
        self.assertEqual(id(settings), id(Settings.get_settings()))

    def test_select_env_from_settings_file(self):
        settings = Settings.select_env(
            settings_file=os.path.join(os.path.dirname(__file__), "settings.toml"),
        )
        self.assertEqual(settings.current_env, os.environ.get("EARTHONE_ENV"))
        self.assertEqual(settings.testing, "hello")

    @patch.dict(os.environ, {"EARTHONE_TESTING": "hello"})
    def test_select_env_override_from_env(self):
        settings = Settings.select_env()
        self.assertEqual(settings.current_env, os.environ.get("EARTHONE_ENV"))
        self.assertEqual(settings.testing, "hello")

    @patch.dict(os.environ, {"DL_ENV": "testing", "DL_TESTING": "hello"})
    def test_select_env_prefix(self):
        settings = Settings.select_env(envvar_prefix="DL")
        self.assertEqual(settings.current_env, "testing")
        self.assertEqual(settings.testing, "hello")

    def test_get_settings(self):
        settings = Settings.get_settings()
        self.assertEqual(settings.current_env, os.environ.get("EARTHONE_ENV"))
        self.assertEqual(id(settings), id(Settings._settings))
        self.assertEqual(id(settings), id(Settings.get_settings()))

    def test_peek_settings(self):
        current_env = os.environ["EARTHONE_ENV"]
        env = "production"
        settings = Settings.peek_settings(env)
        assert os.environ["EARTHONE_ENV"] == current_env
        assert settings.env == env
        assert Settings._settings is None

    def test_bad_env(self):
        env = "non-existent"

        with self.assertRaises(ConfigError):
            Settings.peek_settings(env)

        with self.assertRaises(ConfigError):
            Settings.select_env(env)

    def test_default_auth(self):
        a = Auth()
        assert a.domain == "https://iam.dev.earthone.earthdaily.com"

    def test_auth_with_env(self):
        with patch.dict(os.environ, {"EARTHONE_ENV": "production"}):
            a = Auth()
            assert a.domain == "https://iam.production.earthone.earthdaily.com"

    def test_auth_with_test_config(self):
        Settings.select_env("production")
        a = Auth()
        assert a.domain == "https://iam.production.earthone.earthdaily.com"

    def test_env(self):
        peek1_env = "dev"
        env = "staging"

        assert Settings.env is None
        s1 = Settings.peek_settings(peek1_env)
        assert s1.env == peek1_env
        assert Settings.env is None

        s2 = Settings.select_env(env)
        assert s2.env == env
        assert s1.env == peek1_env
        assert Settings.env == env


class VerifyValues(unittest.TestCase):
    configs = {
        "dev": {
            "APP_URL": "https://app.earthone.earthdaily.com",
            "CATALOG_V2_URL": "https://platform.dev.earthone.earthdaily.com/metadata/v1/catalog/v2",
            "COMPUTE_URL": "https://platform.dev.earthone.earthdaily.com/compute/v1",
            "IAM_URL": "https://iam.dev.earthone.earthdaily.com",
            "LOG_LEVEL": "WARNING",
            "METADATA_URL": "https://platform.dev.earthone.earthdaily.com/metadata/v1",
            "PLATFORM_URL": "https://platform.dev.earthone.earthdaily.com",
            "RASTER_URL": "https://platform.dev.earthone.earthdaily.com/raster/v2",
            "USAGE_URL": "https://platform.dev.earthone.earthdaily.com/usage/v1",
            "USERLIMIT_URL": "https://platform.dev.earthone.earthdaily.com/userlimit/v1",
            "VECTOR_URL": "https://platform.dev.earthone.earthdaily.com/vector/v1",
            "YAAS_URL": "https://platform.dev.earthone.earthdaily.com/yaas/v1",
        },
        "freemium": {
            "APP_URL": "https://app.earthone.earthdaily.com",
            "CATALOG_V2_URL": "https://platform.freemium.earthone.earthdaily.com/metadata/v1/catalog/v2",
            "IAM_URL": "https://iam.freemium.earthone.earthdaily.com",
            "LOG_LEVEL": "WARNING",
            "METADATA_URL": "https://platform.freemium.earthone.earthdaily.com/metadata/v1",
            "PLATFORM_URL": "https://platform.freemium.earthone.earthdaily.com",
            "RASTER_URL": "https://platform.freemium.earthone.earthdaily.com/raster/v2",
            "USAGE_URL": "https://platform.freemium.earthone.earthdaily.com/usage/v1",
            "USERLIMIT_URL": "https://platform.freemium.earthone.earthdaily.com/userlimit/v1",
        },
        "production": {
            "APP_URL": "https://app.earthone.earthdaily.com",
            "CATALOG_V2_URL": "https://platform.production.earthone.earthdaily.com/metadata/v1/catalog/v2",
            "COMPUTE_URL": "https://platform.production.earthone.earthdaily.com/compute/v1",
            "IAM_URL": "https://iam.production.earthone.earthdaily.com",
            "LOG_LEVEL": "WARNING",
            "METADATA_URL": "https://platform.production.earthone.earthdaily.com/metadata/v1",
            "PLATFORM_URL": "https://platform.production.earthone.earthdaily.com",
            "RASTER_URL": "https://platform.production.earthone.earthdaily.com/raster/v2",
            "USAGE_URL": "https://platform.production.earthone.earthdaily.com/usage/v1",
            "USERLIMIT_URL": "https://platform.production.earthone.earthdaily.com/userlimit/v1",
            "VECTOR_URL": "https://platform.production.earthone.earthdaily.com/vector/v1",
            "YAAS_URL": "https://platform.production.earthone.earthdaily.com/yaas/v1",
        },
        "staging": {
            "APP_URL": "https://app.earthone.earthdaily.com",
            "CATALOG_V2_URL": "https://platform.staging.earthone.earthdaily.com/metadata/v1/catalog/v2",
            "COMPUTE_URL": "https://platform.staging.earthone.earthdaily.com/compute/v1",
            "IAM_URL": "https://iam.staging.earthone.earthdaily.com",
            "LOG_LEVEL": "WARNING",
            "METADATA_URL": "https://platform.staging.earthone.earthdaily.com/metadata/v1",
            "PLATFORM_URL": "https://platform.staging.earthone.earthdaily.com",
            "RASTER_URL": "https://platform.staging.earthone.earthdaily.com/raster/v2",
            "USAGE_URL": "https://platform.staging.earthone.earthdaily.com/usage/v1",
            "USERLIMIT_URL": "https://platform.staging.earthone.earthdaily.com/userlimit/v1",
            "VECTOR_URL": "https://platform.staging.earthone.earthdaily.com/vector/v1",
            "YAAS_URL": "https://platform.staging.earthone.earthdaily.com/yaas/v1",
        },
        "testing": {
            "APP_URL": "https://app.earthone.earthdaily.com",
            "CATALOG_V2_URL": "https://platform.dev.earthone.earthdaily.com/metadata/v1/catalog/v2",
            "COMPUTE_URL": "https://platform.dev.earthone.earthdaily.com/compute/v1",
            "IAM_URL": "https://iam.dev.earthone.earthdaily.com",
            "LOG_LEVEL": "WARNING",
            "METADATA_URL": "https://platform.dev.earthone.earthdaily.com/metadata/v1",
            "PLATFORM_URL": "https://platform.dev.earthone.earthdaily.com",
            "RASTER_URL": "https://platform.dev.earthone.earthdaily.com/raster/v2",
            "TESTING": True,
            "USAGE_URL": "https://platform.dev.earthone.earthdaily.com/usage/v1",
            "USERLIMIT_URL": "https://platform.dev.earthone.earthdaily.com/userlimit/v1",
            "VECTOR_URL": "https://platform.dev.earthone.earthdaily.com/vector/v1",
            "YAAS_URL": "https://platform.dev.earthone.earthdaily.com/yaas/v1",
        },
    }

    def test_verify_configs(self):
        for config_name, config in self.configs.items():
            settings = Settings.peek_settings(config_name)

            for key in config.keys():
                assert (
                    config[key] == settings[key]
                ), f"{config_name}: {key}: {config[key]} != {settings[key]}"

    def test_verify_as_dict(self):
        for config_name, config in self.configs.items():
            settings = Settings.peek_settings(config_name)
            settings = settings.as_dict()

            for key in config.keys():
                assert (
                    config[key] == settings[key]
                ), f"{config_name}: {key}: {config[key]} != {settings[key]}"

    def test_verify_get(self):
        for config_name, config in self.configs.items():
            settings = Settings.peek_settings(config_name)

            for key in config.keys():
                value = settings.get(key)

                assert (
                    config[key] == value
                ), f"{config_name}: {key}: {config[key]} != {value}"

    def test_remaining_keys(self):
        for config_name, config in self.configs.items():
            settings = Settings.peek_settings(config_name)
            settings = settings.as_dict()

            for key in config.keys():
                settings.pop(key)

            settings.pop("DEFAULT_DOMAIN", None)
            settings.pop("DOMAIN", None)
            settings.pop("TOKEN_INFO_PATH", None)  # picked up from test environment

            assert settings.pop("ENV") == config_name
            assert len(settings) == 0, f"{config_name}: {settings}"
