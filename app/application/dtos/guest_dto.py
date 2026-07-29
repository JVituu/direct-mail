from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkbookSummaryDTO:
    id: int
    file_name: str
    display_name: str
    file_path: str
    imported_at: str
    total_rows: int


@dataclass(frozen=True, slots=True)
class ImportSummaryDTO:
    id: int
    workbook_id: int
    file_name: str
    sheet_name: str
    imported_at: str
    total_rows: int
    columns: tuple[str, ...]
    is_selectable: bool


@dataclass(frozen=True, slots=True)
class ImportResultDTO:
    import_id: int
    workbook_id: int
    file_name: str
    sheet_name: str
    total_rows: int
    columns: tuple[str, ...]
    is_selectable: bool


@dataclass(frozen=True, slots=True)
class WorkbookImportResultDTO:
    workbook_id: int
    file_name: str
    total_rows: int
    imported_sheets: tuple[ImportResultDTO, ...]
    skipped_sheets: tuple[str, ...]


@dataclass(slots=True)
class GuestRowDTO:
    id: int
    import_id: int
    sheet_name: str
    row_number: int
    data: dict[str, str]
    selected: bool
    selectable: bool = True


@dataclass(frozen=True, slots=True)
class GuestPageDTO:
    rows: list[GuestRowDTO]
    columns: tuple[str, ...]
    editable_columns: tuple[str, ...]
    total_rows: int
    selected_rows: int
    page: int
    page_size: int
