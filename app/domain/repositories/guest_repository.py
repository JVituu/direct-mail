from collections.abc import Iterable, Sequence
from typing import Protocol

from app.domain.entities.guest_record import GuestRecord
from app.domain.entities.imported_workbook import ImportedWorkbook
from app.domain.entities.spreadsheet_import import SpreadsheetImport
from app.domain.value_objects.spreadsheet_row import SpreadsheetRow


class GuestRepository(Protocol):
    def initialize(self) -> None:
        raise NotImplementedError

    def create_workbook(self, file_path: str) -> int:
        raise NotImplementedError

    def update_workbook_total_rows(self, workbook_id: int, total_rows: int) -> None:
        raise NotImplementedError

    def rename_workbook(self, workbook_id: int, display_name: str) -> None:
        raise NotImplementedError

    def delete_workbook(self, workbook_id: int) -> None:
        raise NotImplementedError

    def list_workbooks(self) -> list[ImportedWorkbook]:
        raise NotImplementedError

    def get_automatic_sheet_name(self) -> str:
        raise NotImplementedError

    def rename_automatic_sheet(self, display_name: str) -> None:
        raise NotImplementedError

    def create_import(
        self,
        workbook_id: int,
        file_path: str,
        sheet_name: str,
        columns: Sequence[str],
        is_selectable: bool,
    ) -> int:
        raise NotImplementedError

    def update_import_total_rows(self, import_id: int, total_rows: int) -> None:
        raise NotImplementedError

    def delete_import(self, import_id: int) -> None:
        raise NotImplementedError

    def list_imports(self, workbook_id: int | None = None) -> list[SpreadsheetImport]:
        raise NotImplementedError

    def get_import(self, import_id: int) -> SpreadsheetImport | None:
        raise NotImplementedError

    def insert_guests(
        self,
        import_id: int,
        rows: Sequence[SpreadsheetRow],
    ) -> None:
        raise NotImplementedError

    def count_guests(
        self,
        import_id: int | None,
        workbook_id: int | None = None,
        search: str = "",
        duplicates_only: bool = False,
    ) -> int:
        raise NotImplementedError

    def count_selected_guests(
        self,
        import_id: int | None = None,
        workbook_id: int | None = None,
        search: str = "",
        duplicates_only: bool = False,
    ) -> int:
        raise NotImplementedError

    def count_automatic_guests(
        self,
        import_id: int | None = None,
        workbook_id: int | None = None,
        search: str = "",
    ) -> int:
        raise NotImplementedError

    def get_columns(
        self,
        import_id: int | None = None,
        workbook_id: int | None = None,
    ) -> tuple[str, ...]:
        raise NotImplementedError

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
        raise NotImplementedError

    def list_automatic_guests(
        self,
        import_id: int | None,
        workbook_id: int | None,
        limit: int,
        offset: int,
        search: str = "",
        duplicates_only: bool = False,
    ) -> list[GuestRecord]:
        raise NotImplementedError

    def list_duplicate_candidates(self, guest_id: int) -> list[GuestRecord]:
        raise NotImplementedError

    def list_automatic_conflicts(self, guest_id: int) -> list[GuestRecord]:
        raise NotImplementedError

    def set_guest_selected(self, guest_id: int, selected: bool) -> None:
        raise NotImplementedError

    def update_guest_data(self, guest_id: int, column_name: str, value: str) -> None:
        raise NotImplementedError

    def update_automatic_guest_data(self, source_guest_id: int, column_name: str, value: str) -> None:
        raise NotImplementedError

    def set_guests_selected(
        self,
        import_id: int | None,
        workbook_id: int | None,
        selected: bool,
        guest_ids: Sequence[int] | None = None,
        search: str = "",
    ) -> int:
        raise NotImplementedError

    def iter_selected_guests(
        self,
        import_id: int | None = None,
        workbook_id: int | None = None,
    ) -> Iterable[GuestRecord]:
        raise NotImplementedError

    def iter_automatic_guests(
        self,
        import_id: int | None = None,
        workbook_id: int | None = None,
    ) -> Iterable[GuestRecord]:
        raise NotImplementedError
