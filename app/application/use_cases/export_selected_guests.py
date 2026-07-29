from pathlib import Path

from app.application.dtos.guest_dto import ImportResultDTO
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

    def execute(self, import_id: int, output_path: str) -> ImportResultDTO:
        imported_file = self._guest_repository.get_import(import_id)
        if imported_file is None:
            raise ValueError("Importação não encontrada.")

        selected_count = self._guest_repository.count_selected_guests(import_id)
        if selected_count == 0:
            raise ValueError("Nenhum convidado selecionado para exportar.")

        path = Path(output_path)
        if path.suffix.lower() != ".xlsx":
            path = path.with_suffix(".xlsx")

        exported_count = self._exporter.export(
            str(path),
            imported_file.columns,
            self._guest_repository.iter_selected_guests(import_id),
        )

        return ImportResultDTO(
            import_id=imported_file.id,
            file_name=path.name,
            sheet_name=imported_file.sheet_name,
            total_rows=exported_count,
            columns=imported_file.columns,
        )
