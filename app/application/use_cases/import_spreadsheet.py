from collections.abc import Callable
from pathlib import Path

from app.application.dtos.guest_dto import ImportResultDTO
from app.domain.repositories.guest_repository import GuestRepository
from app.domain.repositories.spreadsheet_reader import SpreadsheetReader
from app.domain.value_objects.spreadsheet_row import SpreadsheetRow

ProgressCallback = Callable[[int], None]


class ImportSpreadsheetUseCase:
    def __init__(
        self,
        guest_repository: GuestRepository,
        spreadsheet_reader: SpreadsheetReader,
        batch_size: int = 500,
    ) -> None:
        self._guest_repository = guest_repository
        self._spreadsheet_reader = spreadsheet_reader
        self._batch_size = batch_size

    def execute(
        self,
        file_path: str,
        sheet_name: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ImportResultDTO:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")
        if path.suffix.lower() != ".xlsx":
            raise ValueError("Selecione um arquivo .xlsx.")

        available_sheets = self._spreadsheet_reader.list_sheets(str(path))
        if not available_sheets:
            raise ValueError("A planilha não possui abas.")

        selected_sheet = sheet_name or available_sheets[0]
        if selected_sheet not in available_sheets:
            raise ValueError(f"A aba '{selected_sheet}' não existe na planilha.")

        columns = self._spreadsheet_reader.read_headers(str(path), selected_sheet)
        if not columns:
            raise ValueError("A planilha precisa ter uma linha de cabeçalho.")

        import_id = self._guest_repository.create_import(
            file_path=str(path),
            sheet_name=selected_sheet,
            columns=columns,
        )

        total_rows = 0
        batch: list[SpreadsheetRow] = []

        try:
            for row in self._spreadsheet_reader.iter_rows(str(path), selected_sheet):
                batch.append(row)
                if len(batch) >= self._batch_size:
                    self._guest_repository.insert_guests(import_id, batch)
                    total_rows += len(batch)
                    batch.clear()
                    if progress_callback is not None:
                        progress_callback(total_rows)

            if batch:
                self._guest_repository.insert_guests(import_id, batch)
                total_rows += len(batch)
                if progress_callback is not None:
                    progress_callback(total_rows)

            self._guest_repository.update_import_total_rows(import_id, total_rows)
        except Exception:
            self._guest_repository.delete_import(import_id)
            raise

        return ImportResultDTO(
            import_id=import_id,
            file_name=path.name,
            sheet_name=selected_sheet,
            total_rows=total_rows,
            columns=tuple(columns),
        )
