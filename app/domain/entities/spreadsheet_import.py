from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpreadsheetImport:
    id: int
    file_path: str
    file_name: str
    sheet_name: str
    imported_at: str
    total_rows: int
    columns: tuple[str, ...]
