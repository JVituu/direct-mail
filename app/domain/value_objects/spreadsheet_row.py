from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpreadsheetRow:
    row_number: int
    values: dict[str, str]
