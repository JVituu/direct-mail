from collections.abc import Iterable
from pathlib import Path

from app.application.dtos.guest_dto import ImportResultDTO
from app.application.services.contact_data_cleaner import ContactDataCleaner
from app.domain.entities.guest_record import GuestRecord
from app.domain.repositories.guest_repository import GuestRepository
from app.domain.repositories.selected_guests_exporter import SelectedGuestsExporter


class ExportSelectedGuestsUseCase:
    def __init__(
        self,
        guest_repository: GuestRepository,
        exporter: SelectedGuestsExporter,
    ) -> None:
        self._guest_repository = guest_repository
        self._exporter = exporter

    def execute(
        self,
        import_id: int | None,
        output_path: str,
        workbook_id: int | None = None,
    ) -> ImportResultDTO:
        imported_file = self._guest_repository.get_import(import_id) if import_id is not None else None
        if import_id is not None and imported_file is None:
            raise ValueError("Importação não encontrada.")

        selected_count = self._guest_repository.count_automatic_guests(import_id, workbook_id)
        if selected_count == 0:
            raise ValueError("Nenhum convidado selecionado para exportar.")

        path = Path(output_path)
        if path.suffix.lower() != ".xlsx":
            path = path.with_suffix(".xlsx")

        columns = self._guest_repository.get_columns(import_id, workbook_id)
        export_columns = columns if import_id is not None else ("Lista", *columns)
        guests = self._guest_repository.iter_automatic_guests(import_id, workbook_id)
        guests = self._clean_guests(guests, columns)

        if import_id is None:
            guests = self._with_list_column(guests)

        exported_count = self._exporter.export(str(path), export_columns, guests)

        return ImportResultDTO(
            import_id=imported_file.id if imported_file is not None else 0,
            workbook_id=imported_file.workbook_id if imported_file is not None else workbook_id or 0,
            file_name=path.name,
            sheet_name=imported_file.sheet_name if imported_file is not None else "Selecionados",
            total_rows=exported_count,
            columns=export_columns,
            is_selectable=True,
        )

    def _with_list_column(self, guests: Iterable[GuestRecord]) -> Iterable[GuestRecord]:
        for guest in guests:
            yield GuestRecord(
                id=guest.id,
                import_id=guest.import_id,
                sheet_name=guest.sheet_name,
                row_number=guest.row_number,
                verification_code=guest.verification_code,
                data={"Lista": guest.sheet_name, **guest.data},
                selected=guest.selected,
            )

    def _clean_guests(
        self,
        guests: Iterable[GuestRecord],
        columns: tuple[str, ...],
    ) -> Iterable[GuestRecord]:
        cleaner = ContactDataCleaner(columns)
        for guest in guests:
            yield GuestRecord(
                id=guest.id,
                import_id=guest.import_id,
                sheet_name=guest.sheet_name,
                row_number=guest.row_number,
                verification_code=guest.verification_code,
                data=cleaner.clean_values(guest.data),
                selected=guest.selected,
            )
