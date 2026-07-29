from collections.abc import Iterable, Sequence
from typing import Protocol

from app.domain.entities.guest_record import GuestRecord
from app.domain.entities.spreadsheet_import import SpreadsheetImport
from app.domain.value_objects.spreadsheet_row import SpreadsheetRow


class GuestRepository(Protocol):
    def initialize(self) -> None:
        raise NotImplementedError

    def create_import(
        self,
        file_path: str,
        sheet_name: str,
        columns: Sequence[str],
    ) -> int:
        raise NotImplementedError

    def update_import_total_rows(self, import_id: int, total_rows: int) -> None:
        raise NotImplementedError

    def delete_import(self, import_id: int) -> None:
        raise NotImplementedError

    def list_imports(self) -> list[SpreadsheetImport]:
        raise NotImplementedError

    def get_import(self, import_id: int) -> SpreadsheetImport | None:
        raise NotImplementedError

    def insert_guests(
        self,
        import_id: int,
        rows: Sequence[SpreadsheetRow],
    ) -> None:
        raise NotImplementedError

    def count_guests(self, import_id: int, search: str = "") -> int:
        raise NotImplementedError

    def count_selected_guests(self, import_id: int, search: str = "") -> int:
        raise NotImplementedError

    def list_guests(
        self,
        import_id: int,
        limit: int,
        offset: int,
        search: str = "",
    ) -> list[GuestRecord]:
        raise NotImplementedError

    def set_guest_selected(self, guest_id: int, selected: bool) -> None:
        raise NotImplementedError

    def set_guests_selected(
        self,
        import_id: int,
        selected: bool,
        guest_ids: Sequence[int] | None = None,
        search: str = "",
    ) -> int:
        raise NotImplementedError

    def iter_selected_guests(self, import_id: int) -> Iterable[GuestRecord]:
        raise NotImplementedError
