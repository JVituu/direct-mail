from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3


def default_database_path() -> Path:
    project_root = Path(__file__).resolve().parents[3]
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "mala_direta.sqlite3"


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
