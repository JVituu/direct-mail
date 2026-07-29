from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImportSummaryDTO:
    id: int
    file_name: str
    sheet_name: str
    imported_at: str
    total_rows: int
    columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ImportResultDTO:
    import_id: int
    file_name: str
    sheet_name: str
    total_rows: int
    columns: tuple[str, ...]


@dataclass(slots=True)
class GuestRowDTO:
    id: int
    row_number: int
    data: dict[str, str]
    selected: bool


@dataclass(frozen=True, slots=True)
class GuestPageDTO:
    rows: list[GuestRowDTO]
    columns: tuple[str, ...]
    total_rows: int
    selected_rows: int
    page: int
    page_size: int
