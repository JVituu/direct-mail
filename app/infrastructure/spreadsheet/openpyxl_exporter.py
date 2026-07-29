from collections.abc import Iterable, Sequence
from pathlib import Path

from openpyxl import Workbook

from app.domain.entities.guest_record import GuestRecord


class OpenpyxlSelectedGuestsExporter:
    def export(
        self,
        output_path: str,
        columns: Sequence[str],
        guests: Iterable[GuestRecord],
    ) -> int:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        workbook = Workbook(write_only=True)
        worksheet = workbook.create_sheet("Selecionados")
        worksheet.append(list(columns))

        count = 0
        for guest in guests:
            worksheet.append([guest.data.get(column, "") for column in columns])
            count += 1

        workbook.save(path)
        workbook.close()
        return count
