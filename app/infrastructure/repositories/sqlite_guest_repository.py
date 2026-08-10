from collections.abc import Iterable, Sequence
from datetime import datetime
import json
from pathlib import Path
import re
import secrets
from unicodedata import combining, normalize

from app.domain.entities.guest_record import GuestRecord
from app.domain.entities.imported_workbook import ImportedWorkbook
from app.domain.entities.spreadsheet_import import SpreadsheetImport
from app.domain.value_objects.spreadsheet_row import SpreadsheetRow
from app.infrastructure.database.connection import connect


AUTOMATIC_SHEET_NAME_KEY = "automatic_sheet_name"
DEFAULT_AUTOMATIC_SHEET_NAME = "Planilha automática"
MIN_VERIFICATION_CODE = 10_000_000
MAX_VERIFICATION_CODE = 99_999_999
NAME_HEADER_WORDS = {
    "nome",
    "name",
    "convidado",
    "convidados",
    "pessoa",
    "pessoas",
    "cliente",
    "clientes",
    "participante",
    "participantes",
    "destinatario",
    "destinatário",
}
EMAIL_HEADER_WORDS = {"email", "e-mail", "mail"}
PHONE_HEADER_WORDS = {"telefone", "phone", "celular", "whatsapp", "fone", "tel"}
CEP_HEADER_WORDS = {"cep", "codigo postal", "postal code", "zip"}
ADDRESS_HEADER_WORDS = {"endereco", "address", "logradouro", "rua", "avenida", "av"}
NAME_PARTICLES = {"da", "de", "do", "das", "dos", "e"}
WEAK_NAME_KEYS = {
    "acompanhante",
    "casal",
    "convidada",
    "convidado",
    "esposa",
    "esposo",
    "filha",
    "filho",
    "filhas",
    "filhos",
    "marido",
    "mulher",
    "nao",
    "sim",
    "senhor",
    "senhora",
    "sr",
    "sr sra",
    "sra",
    "sra sr",
}


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
                    verification_code TEXT NOT NULL UNIQUE,
                    data_json TEXT NOT NULL,
                    selected INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (import_id) REFERENCES imports(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS automatic_guests (
                    source_guest_id INTEGER PRIMARY KEY,
                    source_import_id INTEGER,
                    source_workbook_id INTEGER,
                    sheet_name TEXT NOT NULL,
                    row_number INTEGER NOT NULL,
                    verification_code TEXT NOT NULL,
                    columns_json TEXT NOT NULL DEFAULT '[]',
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS guest_identities (
                    guest_id INTEGER PRIMARY KEY,
                    name_key TEXT NOT NULL DEFAULT '',
                    phone_key TEXT NOT NULL DEFAULT '',
                    email_key TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY (guest_id) REFERENCES guests(id) ON DELETE CASCADE
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

                CREATE UNIQUE INDEX IF NOT EXISTS idx_guests_verification_code
                    ON guests(verification_code);

                CREATE INDEX IF NOT EXISTS idx_automatic_guests_import_id
                    ON automatic_guests(source_import_id);

                CREATE INDEX IF NOT EXISTS idx_automatic_guests_workbook_id
                    ON automatic_guests(source_workbook_id);

                CREATE INDEX IF NOT EXISTS idx_automatic_guests_verification_code
                    ON automatic_guests(verification_code);

                CREATE INDEX IF NOT EXISTS idx_guest_identities_name
                    ON guest_identities(name_key);

                CREATE INDEX IF NOT EXISTS idx_guest_identities_phone
                    ON guest_identities(phone_key);

                CREATE INDEX IF NOT EXISTS idx_guest_identities_email
                    ON guest_identities(email_key);
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

    def merge_workbooks(
        self,
        source_workbook_id: int,
        target_workbook_id: int,
    ) -> tuple[int, int, int]:
        if source_workbook_id == target_workbook_id:
            raise ValueError("Escolha duas planilhas diferentes para unificar.")

        with connect(self._database_path) as connection:
            source_workbook = connection.execute(
                """
                SELECT id, display_name
                FROM workbooks
                WHERE id = ?
                """,
                (source_workbook_id,),
            ).fetchone()
            if source_workbook is None:
                raise ValueError("Planilha de origem não encontrada.")

            target_workbook = connection.execute(
                """
                SELECT id
                FROM workbooks
                WHERE id = ?
                """,
                (target_workbook_id,),
            ).fetchone()
            if target_workbook is None:
                raise ValueError("Planilha de destino não encontrada.")

            source_imports = connection.execute(
                """
                SELECT id, sheet_name, total_rows
                FROM imports
                WHERE workbook_id = ?
                ORDER BY id ASC
                """,
                (source_workbook_id,),
            ).fetchall()
            if not source_imports:
                raise ValueError("A planilha de origem não possui abas para unificar.")

            existing_sheet_names = {
                str(row["sheet_name"])
                for row in connection.execute(
                    """
                    SELECT sheet_name
                    FROM imports
                    WHERE workbook_id = ?
                    """,
                    (target_workbook_id,),
                ).fetchall()
            }

            source_display_name = str(source_workbook["display_name"])
            for imported_sheet in source_imports:
                original_sheet_name = str(imported_sheet["sheet_name"])
                merged_sheet_name = self._unique_merged_sheet_name(
                    original_sheet_name,
                    existing_sheet_names,
                    source_display_name,
                )
                existing_sheet_names.add(merged_sheet_name)
                if merged_sheet_name == original_sheet_name:
                    continue
                connection.execute(
                    """
                    UPDATE imports
                    SET sheet_name = ?
                    WHERE id = ?
                    """,
                    (merged_sheet_name, imported_sheet["id"]),
                )
                connection.execute(
                    """
                    UPDATE automatic_guests
                    SET sheet_name = ?
                    WHERE source_import_id = ?
                    """,
                    (merged_sheet_name, imported_sheet["id"]),
                )

            connection.execute(
                """
                UPDATE imports
                SET workbook_id = ?
                WHERE workbook_id = ?
                """,
                (target_workbook_id, source_workbook_id),
            )
            connection.execute(
                """
                UPDATE automatic_guests
                SET source_workbook_id = ?
                WHERE source_workbook_id = ?
                """,
                (target_workbook_id, source_workbook_id),
            )

            target_total_rows = int(
                connection.execute(
                    """
                    SELECT COALESCE(SUM(total_rows), 0)
                    FROM imports
                    WHERE workbook_id = ?
                    """,
                    (target_workbook_id,),
                ).fetchone()[0]
            )
            connection.execute(
                """
                UPDATE workbooks
                SET total_rows = ?
                WHERE id = ?
                """,
                (target_total_rows, target_workbook_id),
            )
            connection.execute("DELETE FROM workbooks WHERE id = ?", (source_workbook_id,))

            moved_sheets = len(source_imports)
            moved_rows = sum(int(row["total_rows"]) for row in source_imports)
            return moved_sheets, moved_rows, target_total_rows

    def deduplicate_guests(self, workbook_id: int | None = None) -> int:
        query = """
            SELECT
                guests.id,
                guests.import_id,
                imports.workbook_id,
                guests.row_number,
                guests.data_json,
                guests.selected,
                identities.name_key,
                identities.phone_key,
                identities.email_key
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            JOIN guest_identities identities ON identities.guest_id = guests.id
            WHERE imports.is_selectable = 1
        """
        params: list[object] = []
        if workbook_id is not None:
            query += " AND imports.workbook_id = ?"
            params.append(workbook_id)
        query += " ORDER BY imports.workbook_id, imports.id, guests.row_number, guests.id"

        with connect(self._database_path) as connection:
            rows = connection.execute(query, params).fetchall()
            duplicate_groups = self._duplicate_guest_groups(rows)

            removed_total = 0
            affected_import_ids: set[int] = set()
            affected_workbook_ids: set[int] = set()

            for group in duplicate_groups:
                winner = self._duplicate_group_winner(group)
                winner_id = int(winner["id"])
                winner_data = self._merge_duplicate_group_data(group, winner_id)
                winner_selected = any(bool(row["selected"]) for row in group)
                removed_ids = [int(row["id"]) for row in group if int(row["id"]) != winner_id]
                if not removed_ids:
                    continue

                affected_import_ids.update(int(row["import_id"]) for row in group)
                affected_workbook_ids.update(int(row["workbook_id"]) for row in group)

                connection.execute(
                    """
                    UPDATE guests
                    SET data_json = ?, selected = ?
                    WHERE id = ?
                    """,
                    (
                        json.dumps(winner_data, ensure_ascii=False),
                        1 if winner_selected else int(winner["selected"]),
                        winner_id,
                    ),
                )

                placeholders = ", ".join("?" for _ in removed_ids)
                connection.execute(
                    f"DELETE FROM automatic_guests WHERE source_guest_id IN ({placeholders})",
                    removed_ids,
                )
                connection.execute(
                    f"DELETE FROM guests WHERE id IN ({placeholders})",
                    removed_ids,
                )
                removed_total += len(removed_ids)

                if winner_selected:
                    connection.execute(
                        "DELETE FROM automatic_guests WHERE source_guest_id = ?",
                        (winner_id,),
                    )
                    self._insert_automatic_guest_copy(connection, winner_id)
                    connection.execute(
                        """
                        UPDATE automatic_guests
                        SET columns_json = ?, data_json = ?
                        WHERE source_guest_id = ?
                        """,
                        (
                            json.dumps(list(winner_data.keys()), ensure_ascii=False),
                            json.dumps(winner_data, ensure_ascii=False),
                            winner_id,
                        ),
                    )
                self._upsert_guest_identity(connection, winner_id)

            if removed_total:
                self._recalculate_import_totals(connection, affected_import_ids)
                self._recalculate_workbook_totals(connection, affected_workbook_ids)

            return removed_total

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

    def _unique_merged_sheet_name(
        self,
        sheet_name: str,
        existing_sheet_names: set[str],
        source_display_name: str,
    ) -> str:
        if sheet_name not in existing_sheet_names:
            return sheet_name

        source_label = self._compact_source_label(source_display_name)
        base_name = f"{sheet_name} - {source_label}" if source_label else f"{sheet_name} - origem"
        candidate = base_name
        counter = 2
        while candidate in existing_sheet_names:
            candidate = f"{base_name} {counter}"
            counter += 1
        return candidate

    def _compact_source_label(self, display_name: str) -> str:
        label = Path(display_name.strip()).stem.strip()
        if not label:
            return ""
        if len(label) <= 32:
            return label
        return label[:29].rstrip() + "..."

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

        with connect(self._database_path) as connection:
            verification_codes = self._generate_unique_verification_codes(connection, len(rows))
            payload = [
                (
                    import_id,
                    row.row_number,
                    verification_codes[index],
                    json.dumps(row.values, ensure_ascii=False),
                )
                for index, row in enumerate(rows)
            ]
            connection.executemany(
                """
                INSERT INTO guests (import_id, row_number, verification_code, data_json)
                VALUES (?, ?, ?, ?)
                """,
                payload,
            )
            self._upsert_guest_identities(connection, import_id)

    def count_guests(
        self,
        import_id: int | None,
        workbook_id: int | None = None,
        search: str = "",
        duplicates_only: bool = False,
    ) -> int:
        query = """
            SELECT COUNT(*)
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            WHERE 1 = 1
        """
        params: list[object] = []
        query, params = self._apply_guest_filters(query, params, import_id, workbook_id, search=search)
        if duplicates_only:
            query = self._apply_duplicate_filter(query, "guests.id")

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
        duplicates_only: bool = False,
    ) -> int:
        query = """
            SELECT COUNT(*)
            FROM automatic_guests
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
        if duplicates_only:
            query = self._apply_duplicate_filter(query, "automatic_guests.source_guest_id")

        with connect(self._database_path) as connection:
            return int(connection.execute(query, params).fetchone()[0])

    def clear_automatic_guests(self) -> int:
        with connect(self._database_path) as connection:
            cursor = connection.execute("DELETE FROM automatic_guests")
            connection.execute("UPDATE guests SET selected = 0 WHERE selected = 1")
            return int(cursor.rowcount)

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
        for column in self._automatic_columns(import_id, workbook_id):
            if column not in seen:
                columns.append(column)
                seen.add(column)
        return tuple(columns)

    def _automatic_columns(
        self,
        import_id: int | None = None,
        workbook_id: int | None = None,
    ) -> tuple[str, ...]:
        query = """
            SELECT columns_json, data_json
            FROM automatic_guests
            WHERE 1 = 1
        """
        params: list[object] = []
        query, params = self._apply_automatic_guest_filters(query, params, import_id, workbook_id)

        columns: list[str] = []
        seen: set[str] = set()
        with connect(self._database_path) as connection:
            rows = connection.execute(query, params).fetchall()

        for row in rows:
            try:
                row_columns = json.loads(row["columns_json"])
            except (TypeError, json.JSONDecodeError):
                row_columns = []
            if not row_columns:
                try:
                    row_columns = list(json.loads(row["data_json"]).keys())
                except (TypeError, json.JSONDecodeError):
                    row_columns = []

            for column in row_columns:
                column_name = str(column)
                if column_name not in seen:
                    columns.append(column_name)
                    seen.add(column_name)

        return tuple(columns)

    def list_guests(
        self,
        import_id: int | None,
        workbook_id: int | None,
        limit: int,
        offset: int,
        search: str = "",
        selected_only: bool = False,
        duplicates_only: bool = False,
    ) -> list[GuestRecord]:
        query = """
            SELECT
                guests.id,
                guests.import_id,
                imports.sheet_name,
                imports.is_selectable,
                guests.row_number,
                guests.verification_code,
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
        if duplicates_only:
            query = self._apply_duplicate_filter(query, "guests.id")
        query += " ORDER BY imports.id, guests.row_number LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with connect(self._database_path) as connection:
            rows = connection.execute(query, params).fetchall()
            guests = [self._to_guest(row) for row in rows]
            self._apply_duplicate_summaries(connection, guests)

        return guests

    def list_automatic_guests(
        self,
        import_id: int | None,
        workbook_id: int | None,
        limit: int,
        offset: int,
        search: str = "",
        duplicates_only: bool = False,
    ) -> list[GuestRecord]:
        query = """
            SELECT
                automatic_guests.source_guest_id AS id,
                automatic_guests.source_import_id AS import_id,
                automatic_guests.sheet_name,
                1 AS is_selectable,
                automatic_guests.row_number,
                automatic_guests.verification_code,
                automatic_guests.data_json,
                1 AS selected
            FROM automatic_guests
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
        if duplicates_only:
            query = self._apply_duplicate_filter(query, "automatic_guests.source_guest_id")
        query += " ORDER BY automatic_guests.created_at, automatic_guests.source_import_id, automatic_guests.row_number LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with connect(self._database_path) as connection:
            rows = connection.execute(query, params).fetchall()
            guests = [self._to_guest(row) for row in rows]
            self._apply_duplicate_summaries(connection, guests)

        return guests

    def list_duplicate_candidates(self, guest_id: int) -> list[GuestRecord]:
        with connect(self._database_path) as connection:
            identity = self._identity_for_guest_id(connection, guest_id)
            if identity is None or not any(identity.values()):
                return []

            rows = connection.execute(
                """
                SELECT
                    guests.id,
                    guests.import_id,
                    imports.sheet_name,
                    imports.is_selectable,
                    guests.row_number,
                    guests.verification_code,
                    guests.data_json,
                    guests.selected
                FROM guests
                JOIN imports ON imports.id = guests.import_id
                JOIN guest_identities identities ON identities.guest_id = guests.id
                WHERE imports.is_selectable = 1
                AND (
                    (? != '' AND identities.email_key = ?)
                    OR (? != '' AND identities.phone_key = ?)
                    OR (? != '' AND identities.name_key = ?)
                )
                ORDER BY
                    CASE WHEN guests.id = ? THEN 0 ELSE 1 END,
                    imports.id,
                    guests.row_number
                """,
                (
                    identity["email_key"],
                    identity["email_key"],
                    identity["phone_key"],
                    identity["phone_key"],
                    identity["name_key"],
                    identity["name_key"],
                    guest_id,
                ),
            ).fetchall()
            guests = [self._to_guest(row) for row in rows]
            self._apply_duplicate_summaries(connection, guests)

        return guests

    def list_automatic_conflicts(self, guest_id: int) -> list[GuestRecord]:
        with connect(self._database_path) as connection:
            identity = self._identity_for_guest_id(connection, guest_id)
            if identity is None or not any(identity.values()):
                return []

            rows = connection.execute(
                """
                SELECT
                    automatic_guests.source_guest_id AS id,
                    automatic_guests.source_import_id AS import_id,
                    automatic_guests.sheet_name,
                    1 AS is_selectable,
                    automatic_guests.row_number,
                    automatic_guests.verification_code,
                    automatic_guests.data_json,
                    1 AS selected
                FROM automatic_guests
                JOIN imports ON imports.id = automatic_guests.source_import_id
                JOIN guest_identities identities ON identities.guest_id = automatic_guests.source_guest_id
                WHERE automatic_guests.source_guest_id != ?
                AND (
                    (? != '' AND identities.email_key = ?)
                    OR (? != '' AND identities.phone_key = ?)
                    OR (? != '' AND identities.name_key = ?)
                )
                ORDER BY automatic_guests.source_import_id, automatic_guests.row_number
                """,
                (
                    guest_id,
                    identity["email_key"],
                    identity["email_key"],
                    identity["phone_key"],
                    identity["phone_key"],
                    identity["name_key"],
                    identity["name_key"],
                ),
            ).fetchall()
            guests = [self._to_guest(row) for row in rows]
            self._apply_duplicate_summaries(connection, guests)

        return guests

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
                "SELECT import_id, data_json FROM guests WHERE id = ?",
                (guest_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Registro não encontrado.")

            data = json.loads(row["data_json"])
            data[column_name] = value
            connection.execute(
                "UPDATE guests SET data_json = ? WHERE id = ?",
                (json.dumps(data, ensure_ascii=False), guest_id),
            )
            self._append_import_column(connection, int(row["import_id"]), column_name)
            self._upsert_guest_identity(connection, guest_id)

    def update_automatic_guest_data(self, source_guest_id: int, column_name: str, value: str) -> None:
        with connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT columns_json, data_json FROM automatic_guests WHERE source_guest_id = ?",
                (source_guest_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Registro não encontrado na Planilha automática.")

            data = json.loads(row["data_json"])
            data[column_name] = value
            columns = self._append_column_to_json(row["columns_json"], column_name)
            connection.execute(
                """
                UPDATE automatic_guests
                SET columns_json = ?, data_json = ?
                WHERE source_guest_id = ?
                """,
                (columns, json.dumps(data, ensure_ascii=False), source_guest_id),
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
            if guest_ids is None and not selected and import_id is None and workbook_id is None:
                return self._clear_automatic_filtered(connection, search)

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
                guests.verification_code,
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

    def iter_guests(
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
                guests.verification_code,
                guests.data_json,
                guests.selected
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            WHERE 1 = 1
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
                automatic_guests.verification_code,
                automatic_guests.data_json,
                1 AS selected
            FROM automatic_guests
            WHERE 1 = 1
        """
        params: list[object] = []
        query, params = self._apply_automatic_guest_filters(query, params, import_id, workbook_id)
        query += " ORDER BY automatic_guests.created_at, automatic_guests.source_import_id, automatic_guests.row_number"

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
                source_workbook_id,
                sheet_name,
                row_number,
                verification_code,
                columns_json,
                data_json,
                created_at
            )
            SELECT
                guests.id,
                guests.import_id,
                imports.workbook_id,
                imports.sheet_name,
                guests.row_number,
                guests.verification_code,
                imports.columns_json,
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
                source_workbook_id,
                sheet_name,
                row_number,
                verification_code,
                columns_json,
                data_json,
                created_at
            )
            SELECT
                guests.id,
                guests.import_id,
                imports.workbook_id,
                imports.sheet_name,
                guests.row_number,
                guests.verification_code,
                imports.columns_json,
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
                source_workbook_id,
                sheet_name,
                row_number,
                verification_code,
                columns_json,
                data_json,
                created_at
            )
            SELECT
                guests.id,
                guests.import_id,
                imports.workbook_id,
                imports.sheet_name,
                guests.row_number,
                guests.verification_code,
                imports.columns_json,
                guests.data_json,
                datetime('now')
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            WHERE guests.id IN ({subquery})
            AND imports.is_selectable = 1
            """,
            list(params),
        )

    def _clear_automatic_filtered(self, connection: object, search: str = "") -> int:
        query = """
            SELECT automatic_guests.source_guest_id
            FROM automatic_guests
            WHERE 1 = 1
        """
        params: list[object] = []
        query, params = self._apply_automatic_guest_filters(
            query,
            params,
            import_id=None,
            workbook_id=None,
            search=search,
        )
        rows = connection.execute(query, params).fetchall()
        guest_ids = [int(row["source_guest_id"]) for row in rows]
        if not guest_ids:
            return 0

        placeholders = ", ".join("?" for _ in guest_ids)
        connection.execute(
            f"DELETE FROM automatic_guests WHERE source_guest_id IN ({placeholders})",
            guest_ids,
        )
        connection.execute(
            f"UPDATE guests SET selected = 0 WHERE id IN ({placeholders})",
            guest_ids,
        )
        return len(guest_ids)

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
            query += " AND (guests.data_json LIKE ? OR guests.verification_code LIKE ?)"
            search_value = f"%{search.strip()}%"
            params.extend([search_value, search_value])
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
            query += " AND automatic_guests.source_workbook_id = ?"
            params.append(workbook_id)
        if search.strip():
            query += """
                AND (
                    automatic_guests.data_json LIKE ?
                    OR automatic_guests.sheet_name LIKE ?
                    OR automatic_guests.verification_code LIKE ?
                )
            """
            search_value = f"%{search.strip()}%"
            params.extend([search_value, search_value, search_value])
        return query, params

    def _apply_duplicate_filter(self, query: str, guest_id_expression: str) -> str:
        return (
            query
            + f"""
            AND EXISTS (
                SELECT 1
                FROM guest_identities current_identity
                WHERE current_identity.guest_id = {guest_id_expression}
                AND (
                    (
                        current_identity.email_key != ''
                        AND EXISTS (
                            SELECT 1
                            FROM guest_identities other_identity
                            JOIN guests other_guest ON other_guest.id = other_identity.guest_id
                            JOIN imports other_import ON other_import.id = other_guest.import_id
                            WHERE other_identity.guest_id != current_identity.guest_id
                            AND other_identity.email_key = current_identity.email_key
                            AND other_import.is_selectable = 1
                        )
                    )
                    OR (
                        current_identity.phone_key != ''
                        AND EXISTS (
                            SELECT 1
                            FROM guest_identities other_identity
                            JOIN guests other_guest ON other_guest.id = other_identity.guest_id
                            JOIN imports other_import ON other_import.id = other_guest.import_id
                            WHERE other_identity.guest_id != current_identity.guest_id
                            AND other_identity.phone_key = current_identity.phone_key
                            AND other_import.is_selectable = 1
                        )
                    )
                    OR (
                        current_identity.name_key != ''
                        AND EXISTS (
                            SELECT 1
                            FROM guest_identities other_identity
                            JOIN guests other_guest ON other_guest.id = other_identity.guest_id
                            JOIN imports other_import ON other_import.id = other_guest.import_id
                            WHERE other_identity.guest_id != current_identity.guest_id
                            AND other_identity.name_key = current_identity.name_key
                            AND other_import.is_selectable = 1
                        )
                    )
                )
            )
            """
        )

    def _apply_duplicate_summaries(
        self,
        connection: object,
        guests: list[GuestRecord],
    ) -> None:
        guest_ids = [guest.id for guest in guests if guest.id is not None]
        if not guest_ids:
            return

        identities = self._identities_for_guest_ids(connection, guest_ids)
        if not identities:
            return

        email_counts = self._identity_counts(connection, "email_key", {identity["email_key"] for identity in identities.values()})
        phone_counts = self._identity_counts(connection, "phone_key", {identity["phone_key"] for identity in identities.values()})
        name_counts = self._identity_counts(connection, "name_key", {identity["name_key"] for identity in identities.values()})

        for guest in guests:
            if guest.id is None or guest.id not in identities:
                continue

            identity = identities[guest.id]
            reason = ""
            duplicate_count = 0
            if identity["email_key"] and email_counts.get(identity["email_key"], 0) > 1:
                reason = "E-mail"
                duplicate_count = email_counts[identity["email_key"]]
            elif identity["phone_key"] and phone_counts.get(identity["phone_key"], 0) > 1:
                reason = "Telefone"
                duplicate_count = phone_counts[identity["phone_key"]]
            elif identity["name_key"] and name_counts.get(identity["name_key"], 0) > 1:
                reason = "Nome"
                duplicate_count = name_counts[identity["name_key"]]

            guest.duplicate_reason = reason
            guest.duplicate_count = duplicate_count

    def _identity_for_guest_id(self, connection: object, guest_id: int) -> dict[str, str] | None:
        row = connection.execute(
            """
            SELECT guest_id, name_key, phone_key, email_key
            FROM guest_identities
            WHERE guest_id = ?
            """,
            (guest_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "name_key": str(row["name_key"]),
            "phone_key": str(row["phone_key"]),
            "email_key": str(row["email_key"]),
        }

    def _identities_for_guest_ids(
        self,
        connection: object,
        guest_ids: Sequence[int],
    ) -> dict[int, dict[str, str]]:
        placeholders = ", ".join("?" for _ in guest_ids)
        rows = connection.execute(
            f"""
            SELECT guest_id, name_key, phone_key, email_key
            FROM guest_identities
            WHERE guest_id IN ({placeholders})
            """,
            list(guest_ids),
        ).fetchall()
        return {
            int(row["guest_id"]): {
                "name_key": str(row["name_key"]),
                "phone_key": str(row["phone_key"]),
                "email_key": str(row["email_key"]),
            }
            for row in rows
        }

    def _identity_counts(
        self,
        connection: object,
        column_name: str,
        keys: set[str],
    ) -> dict[str, int]:
        clean_keys = {key for key in keys if key}
        if not clean_keys:
            return {}

        placeholders = ", ".join("?" for _ in clean_keys)
        rows = connection.execute(
            f"""
            SELECT guest_identities.{column_name} AS identity_key, COUNT(*) AS total
            FROM guest_identities
            JOIN guests ON guests.id = guest_identities.guest_id
            JOIN imports ON imports.id = guests.import_id
            WHERE guest_identities.{column_name} IN ({placeholders})
            AND guest_identities.{column_name} != ''
            AND imports.is_selectable = 1
            GROUP BY guest_identities.{column_name}
            """,
            list(clean_keys),
        ).fetchall()
        return {str(row["identity_key"]): int(row["total"]) for row in rows}

    def _duplicate_guest_groups(self, rows: Sequence[object]) -> list[list[object]]:
        if not rows:
            return []

        parent = {int(row["id"]): int(row["id"]) for row in rows}

        def find(guest_id: int) -> int:
            while parent[guest_id] != guest_id:
                parent[guest_id] = parent[parent[guest_id]]
                guest_id = parent[guest_id]
            return guest_id

        def union(left_id: int, right_id: int) -> None:
            left_root = find(left_id)
            right_root = find(right_id)
            if left_root != right_root:
                parent[right_root] = left_root

        for identity_column in ("email_key", "phone_key", "name_key"):
            seen: dict[str, int] = {}
            for row in rows:
                identity_key = str(row[identity_column]).strip()
                if not identity_key:
                    continue
                guest_id = int(row["id"])
                if identity_key in seen:
                    union(seen[identity_key], guest_id)
                else:
                    seen[identity_key] = guest_id

        grouped_rows: dict[int, list[object]] = {}
        for row in rows:
            grouped_rows.setdefault(find(int(row["id"])), []).append(row)
        return [group for group in grouped_rows.values() if len(group) > 1]

    def _duplicate_group_winner(self, rows: Sequence[object]) -> object:
        return max(
            rows,
            key=lambda row: (
                self._duplicate_completeness_score(json.loads(row["data_json"])),
                -int(row["workbook_id"]),
                -int(row["import_id"]),
                -int(row["row_number"]),
                -int(row["id"]),
            ),
        )

    def _duplicate_completeness_score(self, data: dict[str, str]) -> int:
        score = 0
        for value in data.values():
            for item in self._split_merged_values(str(value)):
                score += 8
                score += min(len(item), 120) // 12

        if self._find_value_by_headers(data, NAME_HEADER_WORDS):
            score += 20
        if self._find_value_by_headers(data, EMAIL_HEADER_WORDS) or self._find_email_in_values(data):
            score += 50
        if self._find_value_by_headers(data, PHONE_HEADER_WORDS):
            score += 40
        if self._find_value_by_headers(data, CEP_HEADER_WORDS):
            score += 18
        if self._find_value_by_headers(data, ADDRESS_HEADER_WORDS):
            score += 18
        return score

    def _merge_duplicate_group_data(
        self,
        rows: Sequence[object],
        winner_id: int,
    ) -> dict[str, str]:
        ordered_rows = sorted(
            rows,
            key=lambda row: 0 if int(row["id"]) == winner_id else 1,
        )
        merged: dict[str, str] = {}
        for row in ordered_rows:
            data = json.loads(row["data_json"])
            for column_name, value in data.items():
                self._append_merged_value(merged, str(column_name), str(value))
        return merged

    def _append_merged_value(self, data: dict[str, str], column_name: str, value: str) -> None:
        values = self._split_merged_values(value)
        if not values:
            return

        current_values = self._split_merged_values(data.get(column_name, ""))
        normalized_column = self._normalize_match_text(column_name)
        normalized_name_words = {self._normalize_match_text(word) for word in NAME_HEADER_WORDS}
        if current_values and any(word and word in normalized_column for word in normalized_name_words):
            return

        for new_value in values:
            if any(self._same_merged_value(existing_value, new_value) for existing_value in current_values):
                continue
            current_values.append(new_value)
        data[column_name] = "\n".join(current_values)

    def _append_import_column(self, connection: object, import_id: int, column_name: str) -> None:
        row = connection.execute(
            "SELECT columns_json FROM imports WHERE id = ?",
            (import_id,),
        ).fetchone()
        if row is None:
            return

        columns_json = self._append_column_to_json(row["columns_json"], column_name)
        connection.execute(
            "UPDATE imports SET columns_json = ? WHERE id = ?",
            (columns_json, import_id),
        )

    def _append_column_to_json(self, columns_json: object, column_name: str) -> str:
        try:
            columns = json.loads(str(columns_json))
        except (TypeError, json.JSONDecodeError):
            columns = []

        clean_column_name = str(column_name).strip()
        output_columns = [str(column).strip() for column in columns if str(column).strip()]
        if clean_column_name and clean_column_name not in output_columns:
            output_columns.append(clean_column_name)
        return json.dumps(output_columns, ensure_ascii=False)

    def _split_merged_values(self, value: str) -> list[str]:
        return [
            item.strip()
            for item in re.split(r"[\n;]+", str(value))
            if item.strip()
        ]

    def _same_merged_value(self, left: str, right: str) -> bool:
        left_value = str(left).strip()
        right_value = str(right).strip()
        if not left_value or not right_value:
            return left_value == right_value
        if "@" in left_value or "@" in right_value:
            return left_value.casefold() == right_value.casefold()

        left_digits = re.sub(r"\D+", "", left_value)
        right_digits = re.sub(r"\D+", "", right_value)
        if left_digits and right_digits:
            return left_digits == right_digits
        return self._normalize_match_text(left_value) == self._normalize_match_text(right_value)

    def _recalculate_import_totals(self, connection: object, import_ids: set[int]) -> None:
        for import_id in import_ids:
            total_rows = int(
                connection.execute(
                    "SELECT COUNT(*) FROM guests WHERE import_id = ?",
                    (import_id,),
                ).fetchone()[0]
            )
            connection.execute(
                "UPDATE imports SET total_rows = ? WHERE id = ?",
                (total_rows, import_id),
            )

    def _recalculate_workbook_totals(self, connection: object, workbook_ids: set[int]) -> None:
        for workbook_id in workbook_ids:
            total_rows = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM guests
                    JOIN imports ON imports.id = guests.import_id
                    WHERE imports.workbook_id = ?
                    """,
                    (workbook_id,),
                ).fetchone()[0]
            )
            connection.execute(
                "UPDATE workbooks SET total_rows = ? WHERE id = ?",
                (total_rows, workbook_id),
            )

    def _migrate_schema(self, connection: object) -> None:
        import_columns = self._table_columns(connection, "imports")
        if "workbook_id" not in import_columns:
            connection.execute("ALTER TABLE imports ADD COLUMN workbook_id INTEGER")
        if "is_selectable" not in import_columns:
            connection.execute("ALTER TABLE imports ADD COLUMN is_selectable INTEGER NOT NULL DEFAULT 1")
        guest_columns = self._table_columns(connection, "guests")
        if "verification_code" not in guest_columns:
            connection.execute("ALTER TABLE guests ADD COLUMN verification_code TEXT")
        automatic_columns = self._table_columns(connection, "automatic_guests")
        if "verification_code" not in automatic_columns:
            connection.execute("ALTER TABLE automatic_guests ADD COLUMN verification_code TEXT")
        workbook_columns = self._table_columns(connection, "workbooks")
        if "display_name" not in workbook_columns:
            connection.execute("ALTER TABLE workbooks ADD COLUMN display_name TEXT")
            connection.execute("UPDATE workbooks SET display_name = file_name WHERE display_name IS NULL")
        self._migrate_existing_imports(connection)
        self._migrate_guest_verification_codes(connection)
        self._migrate_automatic_guests_storage(connection)
        self._upsert_guest_identities(connection)
        self._migrate_existing_automatic_guests(connection)
        self._migrate_automatic_verification_codes(connection)

    def _migrate_automatic_guests_storage(self, connection: object) -> None:
        columns = self._table_columns(connection, "automatic_guests")
        foreign_keys = connection.execute("PRAGMA foreign_key_list(automatic_guests)").fetchall()
        required_columns = {"source_workbook_id", "columns_json"}
        if required_columns.issubset(columns) and not foreign_keys:
            return

        source_import_expr = (
            "automatic_guests.source_import_id"
            if "source_import_id" in columns
            else "guests.import_id"
        )
        source_workbook_expr = (
            "automatic_guests.source_workbook_id"
            if "source_workbook_id" in columns
            else "imports.workbook_id"
        )
        sheet_name_expr = (
            "automatic_guests.sheet_name"
            if "sheet_name" in columns
            else "imports.sheet_name"
        )
        row_number_expr = (
            "automatic_guests.row_number"
            if "row_number" in columns
            else "guests.row_number"
        )
        verification_code_expr = (
            "automatic_guests.verification_code"
            if "verification_code" in columns
            else "guests.verification_code"
        )
        columns_json_expr = (
            "automatic_guests.columns_json"
            if "columns_json" in columns
            else "imports.columns_json"
        )
        data_json_expr = (
            "automatic_guests.data_json"
            if "data_json" in columns
            else "guests.data_json"
        )
        created_at_expr = (
            "automatic_guests.created_at"
            if "created_at" in columns
            else "datetime('now')"
        )

        connection.execute("DROP TABLE IF EXISTS automatic_guests_legacy")
        connection.execute("ALTER TABLE automatic_guests RENAME TO automatic_guests_legacy")
        connection.execute(
            """
            CREATE TABLE automatic_guests (
                source_guest_id INTEGER PRIMARY KEY,
                source_import_id INTEGER,
                source_workbook_id INTEGER,
                sheet_name TEXT NOT NULL,
                row_number INTEGER NOT NULL,
                verification_code TEXT NOT NULL,
                columns_json TEXT NOT NULL DEFAULT '[]',
                data_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            f"""
            INSERT OR IGNORE INTO automatic_guests (
                source_guest_id,
                source_import_id,
                source_workbook_id,
                sheet_name,
                row_number,
                verification_code,
                columns_json,
                data_json,
                created_at
            )
            SELECT
                automatic_guests.source_guest_id,
                COALESCE({source_import_expr}, guests.import_id),
                COALESCE({source_workbook_expr}, imports.workbook_id),
                COALESCE({sheet_name_expr}, imports.sheet_name, ''),
                COALESCE({row_number_expr}, guests.row_number, 0),
                COALESCE(NULLIF({verification_code_expr}, ''), guests.verification_code, ''),
                COALESCE(NULLIF({columns_json_expr}, ''), imports.columns_json, '[]'),
                COALESCE({data_json_expr}, guests.data_json, '{{}}'),
                COALESCE({created_at_expr}, datetime('now'))
            FROM automatic_guests_legacy AS automatic_guests
            LEFT JOIN guests ON guests.id = automatic_guests.source_guest_id
            LEFT JOIN imports ON imports.id = COALESCE({source_import_expr}, guests.import_id)
            """
        )
        connection.execute("DROP TABLE automatic_guests_legacy")

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

    def _migrate_guest_verification_codes(self, connection: object) -> None:
        rows = connection.execute(
            """
            SELECT id
            FROM guests
            WHERE verification_code IS NULL
            OR TRIM(verification_code) = ''
            ORDER BY id ASC
            """
        ).fetchall()
        if not rows:
            return

        verification_codes = self._generate_unique_verification_codes(connection, len(rows))
        connection.executemany(
            "UPDATE guests SET verification_code = ? WHERE id = ?",
            [
                (verification_codes[index], row["id"])
                for index, row in enumerate(rows)
            ],
        )

    def _migrate_existing_automatic_guests(self, connection: object) -> None:
        connection.execute(
            """
            INSERT OR IGNORE INTO automatic_guests (
                source_guest_id,
                source_import_id,
                source_workbook_id,
                sheet_name,
                row_number,
                verification_code,
                columns_json,
                data_json,
                created_at
            )
            SELECT
                guests.id,
                guests.import_id,
                imports.workbook_id,
                imports.sheet_name,
                guests.row_number,
                guests.verification_code,
                imports.columns_json,
                guests.data_json,
                datetime('now')
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            WHERE guests.selected = 1
            AND imports.is_selectable = 1
            """
        )

    def _migrate_automatic_verification_codes(self, connection: object) -> None:
        connection.execute(
            """
            UPDATE automatic_guests
            SET verification_code = (
                SELECT guests.verification_code
                FROM guests
                WHERE guests.id = automatic_guests.source_guest_id
            )
            WHERE verification_code IS NULL
            OR TRIM(verification_code) = ''
            """
        )

    def _upsert_guest_identities(self, connection: object, import_id: int | None = None) -> None:
        query = """
            SELECT guests.id, guests.data_json
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            WHERE imports.is_selectable = 1
        """
        params: list[object] = []
        if import_id is not None:
            query += " AND guests.import_id = ?"
            params.append(import_id)

        rows = connection.execute(query, params).fetchall()
        payload = []
        for row in rows:
            data = json.loads(row["data_json"])
            identity = self._extract_identity(data)
            payload.append(
                (
                    row["id"],
                    identity["name_key"],
                    identity["phone_key"],
                    identity["email_key"],
                )
            )

        if not payload:
            return

        connection.executemany(
            """
            INSERT INTO guest_identities (guest_id, name_key, phone_key, email_key)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guest_id) DO UPDATE SET
                name_key = excluded.name_key,
                phone_key = excluded.phone_key,
                email_key = excluded.email_key
            """,
            payload,
        )

    def _upsert_guest_identity(self, connection: object, guest_id: int) -> None:
        row = connection.execute(
            """
            SELECT guests.data_json
            FROM guests
            JOIN imports ON imports.id = guests.import_id
            WHERE guests.id = ?
            AND imports.is_selectable = 1
            """,
            (guest_id,),
        ).fetchone()
        if row is None:
            return

        identity = self._extract_identity(json.loads(row["data_json"]))
        connection.execute(
            """
            INSERT INTO guest_identities (guest_id, name_key, phone_key, email_key)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guest_id) DO UPDATE SET
                name_key = excluded.name_key,
                phone_key = excluded.phone_key,
                email_key = excluded.email_key
            """,
            (
                guest_id,
                identity["name_key"],
                identity["phone_key"],
                identity["email_key"],
            ),
        )

    def _extract_identity(self, data: dict[str, str]) -> dict[str, str]:
        name_value = self._find_value_by_headers(data, NAME_HEADER_WORDS)
        phone_value = self._find_value_by_headers(data, PHONE_HEADER_WORDS)
        email_value = self._find_value_by_headers(data, EMAIL_HEADER_WORDS) or self._find_email_in_values(data)

        return {
            "name_key": self._normalize_name_key(name_value),
            "phone_key": self._normalize_phone_key(phone_value),
            "email_key": self._normalize_email_key(email_value),
        }

    def _find_value_by_headers(self, data: dict[str, str], header_words: set[str]) -> str:
        normalized_words = {self._normalize_match_text(word) for word in header_words}
        for column_name, value in data.items():
            normalized_column = self._normalize_match_text(column_name)
            if any(word and word in normalized_column for word in normalized_words):
                return str(value)
        return ""

    def _find_email_in_values(self, data: dict[str, str]) -> str:
        for value in data.values():
            match = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", str(value))
            if match:
                return match.group(0)
        return ""

    def _normalize_name_key(self, value: str) -> str:
        normalized = self._normalize_match_text(value)
        tokens = [
            token
            for token in re.sub(r"[^a-z0-9 ]+", " ", normalized).split()
            if token not in NAME_PARTICLES
        ]
        key = " ".join(tokens)
        if len(tokens) < 2 or key in WEAK_NAME_KEYS:
            return ""
        return key

    def _normalize_phone_key(self, value: str) -> str:
        digits = re.sub(r"\D+", "", str(value))
        if len(digits) < 8:
            return ""
        return digits[-11:] if len(digits) > 11 else digits

    def _normalize_email_key(self, value: str) -> str:
        return str(value).strip().casefold()

    def _normalize_match_text(self, value: str) -> str:
        normalized = normalize("NFD", str(value).casefold())
        return "".join(character for character in normalized if not combining(character))

    def _generate_unique_verification_codes(self, connection: object, amount: int) -> list[str]:
        if amount <= 0:
            return []

        existing_codes = self._existing_verification_codes(connection)
        available_codes = MAX_VERIFICATION_CODE - MIN_VERIFICATION_CODE + 1 - len(existing_codes)
        if amount > available_codes:
            raise RuntimeError("Não há códigos de verificação disponíveis.")

        generated_codes: list[str] = []
        while len(generated_codes) < amount:
            candidate = self._generate_verification_code()
            if candidate in existing_codes:
                continue
            existing_codes.add(candidate)
            generated_codes.append(candidate)
        return generated_codes

    def _existing_verification_codes(self, connection: object) -> set[str]:
        rows = connection.execute(
            """
            SELECT verification_code
            FROM guests
            WHERE verification_code IS NOT NULL
            AND TRIM(verification_code) != ''
            UNION
            SELECT verification_code
            FROM automatic_guests
            WHERE verification_code IS NOT NULL
            AND TRIM(verification_code) != ''
            """
        ).fetchall()
        return {str(row["verification_code"]) for row in rows}

    def _generate_verification_code(self) -> str:
        code_range = MAX_VERIFICATION_CODE - MIN_VERIFICATION_CODE + 1
        return str(MIN_VERIFICATION_CODE + secrets.randbelow(code_range))

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
            verification_code=str(row["verification_code"]),
            data=json.loads(row["data_json"]),
            selected=bool(row["selected"]),
            selectable=bool(row["is_selectable"]),
        )
