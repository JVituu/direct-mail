import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.infrastructure.database.connection import default_database_path
from app.main import smoke_test


class DatabasePathTest(unittest.TestCase):
    def test_frozen_app_uses_local_app_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.dict(os.environ, {"LOCALAPPDATA": temp_dir}, clear=True),
                patch.object(sys, "frozen", True, create=True),
            ):
                database_path = default_database_path()

            self.assertEqual(database_path, Path(temp_dir) / "MalaDireta" / "mala_direta.sqlite3")
            self.assertTrue(database_path.parent.exists())

    def test_database_path_environment_override_has_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_path = Path(temp_dir) / "custom" / "database.sqlite3"
            with (
                patch.dict(os.environ, {"MALA_DIRETA_DATABASE_PATH": str(custom_path)}, clear=True),
                patch.object(sys, "frozen", True, create=True),
            ):
                database_path = default_database_path()

            self.assertEqual(database_path, custom_path)
            self.assertTrue(database_path.parent.exists())

    def test_smoke_test_initializes_app_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"MALA_DIRETA_DATA_DIR": temp_dir}, clear=False):
                self.assertEqual(smoke_test(), 0)

            self.assertTrue((Path(temp_dir) / "mala_direta.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
