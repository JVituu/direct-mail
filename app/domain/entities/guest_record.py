from dataclasses import dataclass


@dataclass(slots=True)
class GuestRecord:
    id: int | None
    import_id: int
    row_number: int
    data: dict[str, str]
    selected: bool = False
