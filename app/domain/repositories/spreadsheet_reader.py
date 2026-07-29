from collections.abc import Iterable
from typing import Protocol

from app.domain.value_objects.spreadsheet_row import SpreadsheetRow


class SpreadsheetReader(Protocol):
    def list_sheets(self, file_path: str) -> list[str]:
        raise NotImplementedError

    def read_headers(self, file_path: str, sheet_name: str) -> list[str]:
        raise NotImplementedError

    def has_table(self, file_path: str, sheet_name: str) -> bool:
        raise NotImplementedError

    def iter_rows(self, file_path: str, sheet_name: str) -> Iterable[SpreadsheetRow]:
        raise NotImplementedError
