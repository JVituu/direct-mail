from dataclasses import dataclass, field


@dataclass(slots=True)
class GuestRecord:
    id: int | None
    import_id: int
    sheet_name: str
    row_number: int
    verification_code: str
    data: dict[str, str]
    selected: bool = False
    selectable: bool = True
    duplicate_reason: str = ""
    duplicate_count: int = 0
    invitation_status: str = "pending"
    contact_statuses: dict[str, str] = field(default_factory=dict)
