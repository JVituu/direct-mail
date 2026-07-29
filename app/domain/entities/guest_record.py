from dataclasses import dataclass


@dataclass(slots=True)
class GuestRecord:
    id: int | None
    import_id: int
    sheet_name: str
    row_number: int
    data: dict[str, str]
    selected: bool = False
    selectable: bool = True
