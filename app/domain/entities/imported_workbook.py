from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImportedWorkbook:
    id: int
    file_path: str
    file_name: str
    display_name: str
    imported_at: str
    total_rows: int
