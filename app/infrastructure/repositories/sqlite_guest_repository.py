from collections.abc import Iterable, Sequence
from datetime import datetime
import json
from pathlib import Path

from app.domain.entities.guest_record import GuestRecord
from app.domain.entities.imported_workbook import ImportedWorkbook
from app.domain.entities.spreadsheet_import import SpreadsheetImport
from app.domain.value_objects.spreadsheet_row import SpreadsheetRow
from app.infrastructure.database.connection import connect


AUTOMATIC_SHEET_NAME_KEY = "automatic_sheet_name"
DEFAULT_AUTOMATIC_SHEET_NAME = "Planilha automática"


class SqliteGuestRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)

    def initialize(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with connect(self._database_path) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workbooks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    total_rows INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workbook_id INTEGER,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    sheet_name TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    total_rows INTEGER NOT NULL DEFAULT 0,
                    columns_json TEXT NOT NULL,
                    is_selectable INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (workbook_id) REFERENCES workbooks(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS guests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    import_id INTEGER NOT NULL,
                    row_number INTEGER NOT NULL,
                    data_json TEXT NOT NULL,
                    selected INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (import_id) REFERENCES imports(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS automatic_guests (
                    source_guest_id INTEGER PRIMARY KEY,
                    source_import_id INTEGER NOT NULL,
                    sheet_name TEXT NOT NULL,
                    row_number INTEGER NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (source_guest_id) REFERENCES guests(id) ON DELETE CASCADE,
                    FOREIGN KEY (source_import_id) REFERENCES imports(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            self._migrate_schema(connection)
            connection.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_imports_workbook_id
                    ON imports(workbook_id);

                CREATE INDEX IF NOT EXISTS idx_guests_import_id
                    ON guests(import_id);

                CREATE INDEX IF NOT EXISTS idx_guests_import_selected
                    ON guests(import_id, selected);

                CREATE INDEX IF NOT EXISTS idx_automatic_guests_import_id
                    ON automatic_guests(source_import_id);
                """
            )

    def create_workbook(self, file_path: str) -> int:
        path = Path(file_path)
        imported_at = datetime.now().astimezone().isoformat(timespec="seconds")

        with connect(self._database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO workbooks (file_path, file_name, display_name, imported_at)
                VALUES (?, ?, ?, ?)
                """,
                (str(path), path.name, path.name, imported_at),
            )
            return int(cursor.lastrowid)

    def update_workbook_total_rows(self, workbook_id: int, total_rows: int) -> None:
        with connect(self._database_path) as connection:
            connection.execute(
                "UPDATE workbooks SET total_rows = ? WHERE id = ?",
                (total_rows, workbook_id),
            )

    def rename_workbook(self, workbook_id: int, display_name: str) -> None:
        with connect(self._database_path) as connection:
            connection.execute(
                "UPDATE workbooks SET display_name = ? WHERE id = ?",
                (display_name, workbook_id),
            )

    def delete_workbook(self, workbook_id: int) -> None:
        with connect(self._database_path) as connection:
            connection.execute(
                """
                DELETE FROM guests
                WHERE import_id IN (
                    SELECT id FROM imports WHERE workbook_id = ?
                )
                """,
                (workbook_id,),
            )
            connection.execute("DELETE FROM imports WHERE workbook_id = ?", (workbook_id,))
            connection.execute("DELETE FROM workbooks WHERE id = ?", (workbook_id,))

    def list_workbooks(self) -> list[ImportedWorkbook]:
        with connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT id, file_path, file_name, display_name, imported_at, total_rows
                FROM workbooks
                ORDER BY id DESC
                """
            ).fetchall()

        return [self._to_workbook(row) for row in rows]

    def get_automatic_sheet_name(self) -> str:
        with connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (AUTOMATIC_SHEET_NAME_KEY,),
            ).fetchone()

        if row is None or not str(row["value"]).strip():
            return DEFAULT_AUTOMATIC_SHEET_NAME
        return str(row["value"])

    def rename_automatic_sheet(self, display_name: str) -> None:
        with connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO app_settings (key, value)
                VALUES (?, ?)
                """,
                (AUTOMATIC_SHEET_NAME_KEY, display_name),
            )

    def create_import(
        self,
        workbook_id: int,
        file_path: str,
        sheet_name: str,
        columns: Sequence[str],
        is_selectable: bool,
    ) -> int:
        path = Path(file_path)
        imported_at = datetime.now().astimezone().isoformat(timespec="seconds")

        with connect(self._database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO imports (
                    workbook_id,
                    file_path,
                    file_name,
                    sheet_name,
                    imported_at,
                    columns_json,
                    is_selectable
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workbook_id,
                    str(path),
                    path.name,
                    sheet_name,
                    imported_at,
                    json.dumps(list(columns), ensure_ascii=False),
                    1 if is_selectable else 0,
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

    def list_imports(self, workbook_id: int | None = None) -> list[SpreadsheetImport]:
        query = """
            SELECT
                id,
                workbook_id,
                file_path,
                file_name,
                sheet_name,
                imported_at,
                total_rows,
                columns_json,
                is_selectable
            FROM imports
            WHERE 1 = 1
        """
        params: list[object] = []
        if workbook_id is not None:
            query += " AND workbook_id = ?"
            params.append(workbook_id)
        query += " ORDER BY workbook_id DESC, id ASC"

        with connect(self._database_path) as connection:
            rows = connection.execute(query, params).fetchall()

        return [self._to_import(row) for row in rows]

    def get_import(self, import_id: int) -> SpreadsheetImport | None:
        with connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    workbook_id,
                    file_path,
                    file_name,
                    sheet_name,
                    imported_at,
                    total_rows,
                    columns_json,
                    is_selectable
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

    def count_guests(
        self,
        import_id: int | None,
        workbook_id: int | None = None,
        search: str = "",
    ) -> int:
        query = """
            SELECT COUNT(*)
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            WHERE 1 = 1
        """
        params: list[object] = []
        query, params = self._apply_guest_filters(query, params, import_id, workbook_id, search=search)

        with connect(self._database_path) as connection:
            return int(connection.execute(query, params).fetchone()[0])

    def count_selected_guests(
        self,
        import_id: int | None = None,
        workbook_id: int | None = None,
        search: str = "",
    ) -> int:
        query = """
            SELECT COUNT(*)
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            WHERE guests.selected = 1
        """
        params: list[object] = []
        query, params = self._apply_guest_filters(query, params, import_id, workbook_id, search=search)

        with connect(self._database_path) as connection:
            return int(connection.execute(query, params).fetchone()[0])

    def count_automatic_guests(
        self,
        import_id: int | None = None,
        workbook_id: int | None = None,
        search: str = "",
    ) -> int:
        query = """
            SELECT COUNT(*)
            FROM automatic_guests
            JOIN imports ON imports.id = automatic_guests.source_import_id
            WHERE 1 = 1
        """
        params: list[object] = []
        query, params = self._apply_automatic_guest_filters(
            query,
            params,
            import_id,
            workbook_id,
            search=search,
        )

        with connect(self._database_path) as connection:
            return int(connection.execute(query, params).fetchone()[0])

    def get_columns(
        self,
        import_id: int | None = None,
        workbook_id: int | None = None,
    ) -> tuple[str, ...]:
        if import_id is not None:
            imported_file = self.get_import(import_id)
            return imported_file.columns if imported_file is not None else tuple()

        imports = self.list_imports(workbook_id)
        selectable_imports = [imported_file for imported_file in imports if imported_file.is_selectable]
        source_imports = selectable_imports or imports

        columns: list[str] = []
        seen: set[str] = set()
        for imported_file in source_imports:
            for column in imported_file.columns:
                if column not in seen:
                    columns.append(column)
                    seen.add(column)
        return tuple(columns)

    def list_guests(
        self,
        import_id: int | None,
        workbook_id: int | None,
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
                imports.is_selectable,
                guests.row_number,
                guests.data_json,
                guests.selected
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            WHERE 1 = 1
        """
        params: list[object] = []
        if selected_only:
            query += " AND guests.selected = 1"
        query, params = self._apply_guest_filters(query, params, import_id, workbook_id, search=search)
        query += " ORDER BY imports.id, guests.row_number LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with connect(self._database_path) as connection:
            rows = connection.execute(query, params).fetchall()

        return [self._to_guest(row) for row in rows]

    def list_automatic_guests(
        self,
        import_id: int | None,
        workbook_id: int | None,
        limit: int,
        offset: int,
        search: str = "",
    ) -> list[GuestRecord]:
        query = """
            SELECT
                automatic_guests.source_guest_id AS id,
                automatic_guests.source_import_id AS import_id,
                automatic_guests.sheet_name,
                1 AS is_selectable,
                automatic_guests.row_number,
                automatic_guests.data_json,
                1 AS selected
            FROM automatic_guests
            JOIN imports ON imports.id = automatic_guests.source_import_id
            WHERE 1 = 1
        """
        params: list[object] = []
        query, params = self._apply_automatic_guest_filters(
            query,
            params,
            import_id,
            workbook_id,
            search=search,
        )
        query += " ORDER BY automatic_guests.source_import_id, automatic_guests.row_number LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with connect(self._database_path) as connection:
            rows = connection.execute(query, params).fetchall()

        return [self._to_guest(row) for row in rows]

    def set_guest_selected(self, guest_id: int, selected: bool) -> None:
        with connect(self._database_path) as connection:
            connection.execute(
                """
                UPDATE guests
                SET selected = ?
                WHERE id = ?
                AND import_id IN (
                    SELECT id FROM imports WHERE is_selectable = 1
                )
                """,
                (1 if selected else 0, guest_id),
            )
            if selected:
                self._insert_automatic_guest_copy(connection, guest_id)
            else:
                connection.execute(
                    "DELETE FROM automatic_guests WHERE source_guest_id = ?",
                    (guest_id,),
                )

    def update_guest_data(self, guest_id: int, column_name: str, value: str) -> None:
        with connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT data_json FROM guests WHERE id = ?",
                (guest_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Registro não encontrado.")

            data = json.loads(row["data_json"])
            if column_name not in data:
                raise ValueError("Coluna não encontrada neste registro.")

            data[column_name] = value
            connection.execute(
                "UPDATE guests SET data_json = ? WHERE id = ?",
                (json.dumps(data, ensure_ascii=False), guest_id),
            )

    def update_automatic_guest_data(self, source_guest_id: int, column_name: str, value: str) -> None:
        with connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT data_json FROM automatic_guests WHERE source_guest_id = ?",
                (source_guest_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Registro não encontrado na Planilha automática.")

            data = json.loads(row["data_json"])
            if column_name not in data:
                raise ValueError("Coluna não encontrada neste registro.")

            data[column_name] = value
            connection.execute(
                "UPDATE automatic_guests SET data_json = ? WHERE source_guest_id = ?",
                (json.dumps(data, ensure_ascii=False), source_guest_id),
            )

    def set_guests_selected(
        self,
        import_id: int | None,
        workbook_id: int | None,
        selected: bool,
        guest_ids: Sequence[int] | None = None,
        search: str = "",
    ) -> int:
        selected_value = 1 if selected else 0

        with connect(self._database_path) as connection:
            if guest_ids is not None:
                connection.executemany(
                    """
                    UPDATE guests
                    SET selected = ?
                    WHERE id = ?
                    AND import_id IN (
                        SELECT id FROM imports WHERE is_selectable = 1
                    )
                    """,
                    [(selected_value, guest_id) for guest_id in guest_ids],
                )
                self._sync_automatic_guest_copies_for_ids(connection, guest_ids, selected)
                return len(guest_ids)

            subquery = """
                SELECT guests.id
                FROM guests
                JOIN imports ON imports.id = guests.import_id
                WHERE imports.is_selectable = 1
            """
            params: list[object] = []
            subquery, params = self._apply_guest_filters(
                subquery,
                params,
                import_id,
                workbook_id,
                search=search,
            )
            cursor = connection.execute(
                f"UPDATE guests SET selected = ? WHERE id IN ({subquery})",
                [selected_value, *params],
            )
            self._sync_automatic_guest_copies_for_subquery(
                connection,
                subquery,
                params,
                selected,
            )
            return int(cursor.rowcount)

    def iter_selected_guests(
        self,
        import_id: int | None = None,
        workbook_id: int | None = None,
    ) -> Iterable[GuestRecord]:
        query = """
            SELECT
                guests.id,
                guests.import_id,
                imports.sheet_name,
                imports.is_selectable,
                guests.row_number,
                guests.data_json,
                guests.selected
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            WHERE guests.selected = 1
        """
        params: list[object] = []
        query, params = self._apply_guest_filters(query, params, import_id, workbook_id)
        query += " ORDER BY imports.id, guests.row_number"

        with connect(self._database_path) as connection:
            rows = connection.execute(query, params)
            for row in rows:
                yield self._to_guest(row)

    def iter_automatic_guests(
        self,
        import_id: int | None = None,
        workbook_id: int | None = None,
    ) -> Iterable[GuestRecord]:
        query = """
            SELECT
                automatic_guests.source_guest_id AS id,
                automatic_guests.source_import_id AS import_id,
                automatic_guests.sheet_name,
                1 AS is_selectable,
                automatic_guests.row_number,
                automatic_guests.data_json,
                1 AS selected
            FROM automatic_guests
            JOIN imports ON imports.id = automatic_guests.source_import_id
            WHERE 1 = 1
        """
        params: list[object] = []
        query, params = self._apply_automatic_guest_filters(query, params, import_id, workbook_id)
        query += " ORDER BY automatic_guests.source_import_id, automatic_guests.row_number"

        with connect(self._database_path) as connection:
            rows = connection.execute(query, params)
            for row in rows:
                yield self._to_guest(row)

    def _insert_automatic_guest_copy(self, connection: object, guest_id: int) -> None:
        connection.execute(
            """
            INSERT OR IGNORE INTO automatic_guests (
                source_guest_id,
                source_import_id,
                sheet_name,
                row_number,
                data_json,
                created_at
            )
            SELECT
                guests.id,
                guests.import_id,
                imports.sheet_name,
                guests.row_number,
                guests.data_json,
                datetime('now')
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            WHERE guests.id = ?
            AND imports.is_selectable = 1
            """,
            (guest_id,),
        )

    def _sync_automatic_guest_copies_for_ids(
        self,
        connection: object,
        guest_ids: Sequence[int],
        selected: bool,
    ) -> None:
        if not guest_ids:
            return

        if not selected:
            connection.executemany(
                "DELETE FROM automatic_guests WHERE source_guest_id = ?",
                [(guest_id,) for guest_id in guest_ids],
            )
            return

        connection.executemany(
            """
            INSERT OR IGNORE INTO automatic_guests (
                source_guest_id,
                source_import_id,
                sheet_name,
                row_number,
                data_json,
                created_at
            )
            SELECT
                guests.id,
                guests.import_id,
                imports.sheet_name,
                guests.row_number,
                guests.data_json,
                datetime('now')
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            WHERE guests.id = ?
            AND imports.is_selectable = 1
            """,
            [(guest_id,) for guest_id in guest_ids],
        )

    def _sync_automatic_guest_copies_for_subquery(
        self,
        connection: object,
        subquery: str,
        params: Sequence[object],
        selected: bool,
    ) -> None:
        if not selected:
            connection.execute(
                f"DELETE FROM automatic_guests WHERE source_guest_id IN ({subquery})",
                list(params),
            )
            return

        connection.execute(
            f"""
            INSERT OR IGNORE INTO automatic_guests (
                source_guest_id,
                source_import_id,
                sheet_name,
                row_number,
                data_json,
                created_at
            )
            SELECT
                guests.id,
                guests.import_id,
                imports.sheet_name,
                guests.row_number,
                guests.data_json,
                datetime('now')
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            WHERE guests.id IN ({subquery})
            AND imports.is_selectable = 1
            """,
            list(params),
        )

    def _apply_guest_filters(
        self,
        query: str,
        params: list[object],
        import_id: int | None,
        workbook_id: int | None,
        search: str = "",
    ) -> tuple[str, list[object]]:
        if import_id is not None:
            query += " AND guests.import_id = ?"
            params.append(import_id)
        if workbook_id is not None:
            query += " AND imports.workbook_id = ?"
            params.append(workbook_id)
        if search.strip():
            query += " AND guests.data_json LIKE ?"
            params.append(f"%{search.strip()}%")
        return query, params

    def _apply_automatic_guest_filters(
        self,
        query: str,
        params: list[object],
        import_id: int | None,
        workbook_id: int | None,
        search: str = "",
    ) -> tuple[str, list[object]]:
        if import_id is not None:
            query += " AND automatic_guests.source_import_id = ?"
            params.append(import_id)
        if workbook_id is not None:
            query += " AND imports.workbook_id = ?"
            params.append(workbook_id)
        if search.strip():
            query += " AND (automatic_guests.data_json LIKE ? OR automatic_guests.sheet_name LIKE ?)"
            search_value = f"%{search.strip()}%"
            params.extend([search_value, search_value])
        return query, params

    def _migrate_schema(self, connection: object) -> None:
        import_columns = self._table_columns(connection, "imports")
        if "workbook_id" not in import_columns:
            connection.execute("ALTER TABLE imports ADD COLUMN workbook_id INTEGER")
        if "is_selectable" not in import_columns:
            connection.execute("ALTER TABLE imports ADD COLUMN is_selectable INTEGER NOT NULL DEFAULT 1")
        workbook_columns = self._table_columns(connection, "workbooks")
        if "display_name" not in workbook_columns:
            connection.execute("ALTER TABLE workbooks ADD COLUMN display_name TEXT")
            connection.execute("UPDATE workbooks SET display_name = file_name WHERE display_name IS NULL")
        self._migrate_existing_imports(connection)
        self._migrate_existing_automatic_guests(connection)

    def _migrate_existing_imports(self, connection: object) -> None:
        rows = connection.execute(
            """
            SELECT id, file_path, file_name, imported_at, total_rows
            FROM imports
            WHERE workbook_id IS NULL
            ORDER BY id ASC
            """
        ).fetchall()
        for row in rows:
            cursor = connection.execute(
                """
                INSERT INTO workbooks (file_path, file_name, display_name, imported_at, total_rows)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["file_path"],
                    row["file_name"],
                    row["file_name"],
                    row["imported_at"],
                    row["total_rows"],
                ),
            )
            connection.execute(
                "UPDATE imports SET workbook_id = ? WHERE id = ?",
                (cursor.lastrowid, row["id"]),
            )

    def _migrate_existing_automatic_guests(self, connection: object) -> None:
        connection.execute(
            """
            INSERT OR IGNORE INTO automatic_guests (
                source_guest_id,
                source_import_id,
                sheet_name,
                row_number,
                data_json,
                created_at
            )
            SELECT
                guests.id,
                guests.import_id,
                imports.sheet_name,
                guests.row_number,
                guests.data_json,
                datetime('now')
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            WHERE guests.selected = 1
            AND imports.is_selectable = 1
            """
        )

    def _table_columns(self, connection: object, table_name: str) -> set[str]:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row["name"]) for row in rows}

    def _to_workbook(self, row: object) -> ImportedWorkbook:
        return ImportedWorkbook(
            id=int(row["id"]),
            file_path=str(row["file_path"]),
            file_name=str(row["file_name"]),
            display_name=str(row["display_name"]),
            imported_at=str(row["imported_at"]),
            total_rows=int(row["total_rows"]),
        )

    def _to_import(self, row: object) -> SpreadsheetImport:
        return SpreadsheetImport(
            id=int(row["id"]),
            workbook_id=int(row["workbook_id"]),
            file_path=str(row["file_path"]),
            file_name=str(row["file_name"]),
            sheet_name=str(row["sheet_name"]),
            imported_at=str(row["imported_at"]),
            total_rows=int(row["total_rows"]),
            columns=tuple(json.loads(row["columns_json"])),
            is_selectable=bool(row["is_selectable"]),
        )

    def _to_guest(self, row: object) -> GuestRecord:
        return GuestRecord(
            id=int(row["id"]),
            import_id=int(row["import_id"]),
            sheet_name=str(row["sheet_name"]),
            row_number=int(row["row_number"]),
            data=json.loads(row["data_json"]),
            selected=bool(row["selected"]),
            selectable=bool(row["is_selectable"]),
        )
