# FileName: tests.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError
from django.test import SimpleTestCase, override_settings

from console_project.config import load_config, read_secret_file

_PATH_EXAMPLE = Path(__file__).resolve().parents[1] / "Console.example.jsonc"


class ConfigTests(SimpleTestCase):
    def setUp(self) -> None:
        self.tempDirectory = TemporaryDirectory()
        self.addCleanup(self.tempDirectory.cleanup)
        self.pathConfig = Path(self.tempDirectory.name) / "Console.jsonc"
        self.strExample = _PATH_EXAMPLE.read_text(encoding="utf-8")

    def test_commented_config_and_trailing_commas_are_accepted(self) -> None:
        self.pathConfig.write_text(
            self.strExample.replace(
                '"passwordFile": "secrets/database-password.txt"',
                '"passwordFile": "secrets/database-password.txt",',
            ),
            encoding="utf-8-sig",
        )
        config = load_config(self.pathConfig)
        self.assertEqual(config.database.port, 5432)
        self.assertFalse(config.debug)

    def test_invalid_config_is_rejected_at_the_file_boundary(self) -> None:
        listInvalidConfig = [
            self.strExample.replace('"port": 5432', '"port": "5432"'),
            self.strExample.replace('"port": 5432', '"port": true'),
            self.strExample.replace('"port": 5432', '"port": 70000'),
            self.strExample.replace('"debug": false', '"debug": "false"'),
            self.strExample.replace('"debug": false', '"debug": false, "debug": true'),
            self.strExample.replace('"debug": false', '"deubg": false'),
            self.strExample.replace('["localhost", "127.0.0.1", "[::1]"]', "[]"),
            self.strExample.replace('"name": "liberrpa_console"', '"name": " "'),
            '{"database":',
        ]
        for strConfig in listInvalidConfig:
            with self.subTest(config=strConfig):
                self.pathConfig.write_text(strConfig, encoding="utf-8")
                with self.assertRaises(ImproperlyConfigured):
                    load_config(self.pathConfig)

    def test_missing_config_does_not_create_a_replacement(self) -> None:
        with self.assertRaises(ImproperlyConfigured):
            load_config(self.pathConfig)
        self.assertFalse(self.pathConfig.exists())

    def test_missing_or_empty_secret_is_rejected(self) -> None:
        pathSecret = Path(self.tempDirectory.name) / "secret.txt"
        with self.assertRaises(ImproperlyConfigured):
            read_secret_file(pathSecret)
        pathSecret.write_text("\n", encoding="utf-8")
        with self.assertRaises(ImproperlyConfigured):
            read_secret_file(pathSecret)

    def test_secret_spaces_are_preserved(self) -> None:
        pathSecret = Path(self.tempDirectory.name) / "secret.txt"
        pathSecret.write_text(" password with spaces \n", encoding="utf-8-sig")
        self.assertEqual(read_secret_file(pathSecret), " password with spaces ")


@override_settings(ALLOWED_HOSTS=["testserver"])
class HealthTests(SimpleTestCase):
    def test_liveness_does_not_require_a_database(self) -> None:
        # SimpleTestCase rejects unmocked database access.
        response = self.client.get("/api/health/live/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertIn("no-store", response["Cache-Control"])

    def test_database_outage_does_not_expose_internal_details(self) -> None:
        with patch("console_project.health.connection") as connectionMock:
            connectionMock.cursor.side_effect = OperationalError(
                "private connection data"
            )
            response = self.client.get("/api/health/database/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotContains(response, "private", status_code=503)
        self.assertIn("no-store", response["Cache-Control"])

    def test_successful_database_probe(self) -> None:
        with patch("console_project.health.connection") as connectionMock:
            connectionMock.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                1,
            )
            response = self.client.get("/api/health/database/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_routes_only_allow_get_and_head(self) -> None:
        for strRoute in ["/api/health/live/", "/api/health/database/"]:
            with self.subTest(route=strRoute):
                self.assertEqual(self.client.post(strRoute).status_code, 405)

    def test_untrusted_host_is_rejected(self) -> None:
        response = self.client.get("/api/health/live/", HTTP_HOST="untrusted.example")
        self.assertEqual(response.status_code, 400)
