from collections.abc import Iterable, Sequence
from datetime import datetime
import json
from pathlib import Path

from app.domain.entities.guest_record import GuestRecord
from app.domain.entities.spreadsheet_import import SpreadsheetImport
from app.domain.value_objects.spreadsheet_row import SpreadsheetRow
from app.infrastructure.database.connection import connect


class SqliteGuestRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)

    def initialize(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with connect(self._database_path) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    sheet_name TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    total_rows INTEGER NOT NULL DEFAULT 0,
                    columns_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS guests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    import_id INTEGER NOT NULL,
                    row_number INTEGER NOT NULL,
                    data_json TEXT NOT NULL,
                    selected INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (import_id) REFERENCES imports(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_guests_import_id
                    ON guests(import_id);

                CREATE INDEX IF NOT EXISTS idx_guests_import_selected
                    ON guests(import_id, selected);
                """
            )

    def create_import(
        self,
        file_path: str,
        sheet_name: str,
        columns: Sequence[str],
    ) -> int:
        path = Path(file_path)
        imported_at = datetime.now().astimezone().isoformat(timespec="seconds")

        with connect(self._database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO imports (
                    file_path,
                    file_name,
                    sheet_name,
                    imported_at,
                    columns_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(path),
                    path.name,
                    sheet_name,
                    imported_at,
                    json.dumps(list(columns), ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)

    def update_import_total_rows(self, import_id: int, total_rows: int) -> None:
        with connect(self._database_path) as connection:
            connection.execute(
                "UPDATE imports SET total_rows = ? WHERE id = ?",
                (total_rows, import_id),
            )

    def delete_import(self, import_id: int) -> None:
        with connect(self._database_path) as connection:
            connection.execute("DELETE FROM imports WHERE id = ?", (import_id,))

    def list_imports(self) -> list[SpreadsheetImport]:
        with connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT id, file_path, file_name, sheet_name, imported_at, total_rows, columns_json
                FROM imports
                ORDER BY id DESC
                """
            ).fetchall()

        return [self._to_import(row) for row in rows]

    def get_import(self, import_id: int) -> SpreadsheetImport | None:
        with connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT id, file_path, file_name, sheet_name, imported_at, total_rows, columns_json
                FROM imports
                WHERE id = ?
                """,
                (import_id,),
            ).fetchone()

        if row is None:
            return None
        return self._to_import(row)

    def insert_guests(
        self,
        import_id: int,
        rows: Sequence[SpreadsheetRow],
    ) -> None:
        if not rows:
            return

        payload = [
            (
                import_id,
                row.row_number,
                json.dumps(row.values, ensure_ascii=False),
            )
            for row in rows
        ]

        with connect(self._database_path) as connection:
            connection.executemany(
                """
                INSERT INTO guests (import_id, row_number, data_json)
                VALUES (?, ?, ?)
                """,
                payload,
            )

    def count_guests(self, import_id: int | None, search: str = "") -> int:
        query = "SELECT COUNT(*) FROM guests WHERE 1 = 1"
        params: list[object] = []
        query, params = self._apply_import_filter(query, params, import_id)
        query, params = self._apply_search(query, params, search)

        with connect(self._database_path) as connection:
            return int(connection.execute(query, params).fetchone()[0])

    def count_selected_guests(self, import_id: int | None = None, search: str = "") -> int:
        query = "SELECT COUNT(*) FROM guests WHERE selected = 1"
        params: list[object] = []
        query, params = self._apply_import_filter(query, params, import_id)
        query, params = self._apply_search(query, params, search)

        with connect(self._database_path) as connection:
            return int(connection.execute(query, params).fetchone()[0])

    def get_columns(self, import_id: int | None = None) -> tuple[str, ...]:
        if import_id is not None:
            imported_file = self.get_import(import_id)
            return imported_file.columns if imported_file is not None else tuple()

        columns: list[str] = []
        seen: set[str] = set()
        for imported_file in reversed(self.list_imports()):
            for column in imported_file.columns:
                if column not in seen:
                    columns.append(column)
                    seen.add(column)
        return tuple(columns)

    def list_guests(
        self,
        import_id: int | None,
        limit: int,
        offset: int,
        search: str = "",
        selected_only: bool = False,
    ) -> list[GuestRecord]:
        query = """
            SELECT
                guests.id,
                guests.import_id,
                imports.sheet_name,
                guests.row_number,
                guests.data_json,
                guests.selected
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            WHERE 1 = 1
        """
        params: list[object] = []
        query, params = self._apply_import_filter(query, params, import_id)
        if selected_only:
            query += " AND guests.selected = 1"
        query, params = self._apply_search(query, params, search)
        query += " ORDER BY imports.id, guests.row_number LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with connect(self._database_path) as connection:
            rows = connection.execute(query, params).fetchall()

        return [self._to_guest(row) for row in rows]

    def set_guest_selected(self, guest_id: int, selected: bool) -> None:
        with connect(self._database_path) as connection:
            connection.execute(
                "UPDATE guests SET selected = ? WHERE id = ?",
                (1 if selected else 0, guest_id),
            )

    def set_guests_selected(
        self,
        import_id: int | None,
        selected: bool,
        guest_ids: Sequence[int] | None = None,
        search: str = "",
    ) -> int:
        selected_value = 1 if selected else 0

        with connect(self._database_path) as connection:
            if guest_ids is not None:
                connection.executemany(
                    "UPDATE guests SET selected = ? WHERE id = ?",
                    [(selected_value, guest_id) for guest_id in guest_ids],
                )
                return len(guest_ids)

            query = "UPDATE guests SET selected = ? WHERE 1 = 1"
            params: list[object] = [selected_value]
            query, params = self._apply_import_filter(query, params, import_id)
            query, params = self._apply_search(query, params, search)
            cursor = connection.execute(query, params)
            return int(cursor.rowcount)

    def iter_selected_guests(self, import_id: int | None = None) -> Iterable[GuestRecord]:
        query = """
            SELECT
                guests.id,
                guests.import_id,
                imports.sheet_name,
                guests.row_number,
                guests.data_json,
                guests.selected
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            WHERE guests.selected = 1
        """
        params: list[object] = []
        query, params = self._apply_import_filter(query, params, import_id)
        query += " ORDER BY imports.id, guests.row_number"

        with connect(self._database_path) as connection:
            rows = connection.execute(query, params)
            for row in rows:
                yield self._to_guest(row)

    def _apply_import_filter(
        self,
        query: str,
        params: list[object],
        import_id: int | None,
    ) -> tuple[str, list[object]]:
        if import_id is not None:
            query += " AND guests.import_id = ?" if "guests" in query else " AND import_id = ?"
            params.append(import_id)
        return query, params

    def _apply_search(
        self,
        query: str,
        params: list[object],
        search: str,
    ) -> tuple[str, list[object]]:
        value = search.strip()
        if value:
            query += " AND data_json LIKE ?"
            params.append(f"%{value}%")
        return query, params

    def _to_import(self, row: object) -> SpreadsheetImport:
        return SpreadsheetImport(
            id=int(row["id"]),
            file_path=str(row["file_path"]),
            file_name=str(row["file_name"]),
            sheet_name=str(row["sheet_name"]),
            imported_at=str(row["imported_at"]),
            total_rows=int(row["total_rows"]),
            columns=tuple(json.loads(row["columns_json"])),
        )

    def _to_guest(self, row: object) -> GuestRecord:
        return GuestRecord(
            id=int(row["id"]),
            import_id=int(row["import_id"]),
            sheet_name=str(row["sheet_name"]),
            row_number=int(row["row_number"]),
            data=json.loads(row["data_json"]),
            selected=bool(row["selected"]),
        )
