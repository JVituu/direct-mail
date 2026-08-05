from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
import sys


APP_DATA_DIR_NAME = "MalaDireta"
DATABASE_FILE_NAME = "mala_direta.sqlite3"
DATABASE_PATH_ENV = "MALA_DIRETA_DATABASE_PATH"
DATA_DIR_ENV = "MALA_DIRETA_DATA_DIR"


def default_database_path() -> Path:
    override_path = os.getenv(DATABASE_PATH_ENV)
    if override_path:
        path = Path(override_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    override_dir = os.getenv(DATA_DIR_ENV)
    if override_dir:
        data_dir = Path(override_dir).expanduser()
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / DATABASE_FILE_NAME

    if getattr(sys, "frozen", False):
        data_dir = _installed_user_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / DATABASE_FILE_NAME

    project_root = Path(__file__).resolve().parents[3]
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / DATABASE_FILE_NAME


def _installed_user_data_dir() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_DATA_DIR_NAME

    app_data = os.getenv("APPDATA")
    if app_data:
        return Path(app_data) / APP_DATA_DIR_NAME

    return Path.home() / APP_DATA_DIR_NAME


@contextmanager
def connect(database_path: str | Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
