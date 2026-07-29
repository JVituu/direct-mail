from collections.abc import Callable
from pathlib import Path

from app.application.dtos.guest_dto import ImportResultDTO, WorkbookImportResultDTO
from app.domain.repositories.guest_repository import GuestRepository
from app.domain.repositories.spreadsheet_reader import SpreadsheetReader
from app.domain.value_objects.spreadsheet_row import SpreadsheetRow

ProgressCallback = Callable[[str, int], None]


class ImportSpreadsheetUseCase:
    _CONTACT_HEADER_WORDS = {
        "nome",
        "name",
        "email",
        "e-mail",
        "telefone",
        "phone",
        "celular",
        "whatsapp",
        "endereco",
        "endereço",
        "contato",
        "contact",
    }

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
        path = self._validate_file(file_path)
        available_sheets = self._spreadsheet_reader.list_sheets(str(path))
        if not available_sheets:
            raise ValueError("A planilha não possui abas.")

        selected_sheet = sheet_name or available_sheets[0]
        if selected_sheet not in available_sheets:
            raise ValueError(f"A aba '{selected_sheet}' não existe na planilha.")

        result = self._import_sheet(path, selected_sheet, progress_callback)
        if result.total_rows == 0:
            raise ValueError(f"A aba '{selected_sheet}' não possui registros para importar.")
        return result

    def execute_workbook(
        self,
        file_path: str,
        sheet_names: list[str] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> WorkbookImportResultDTO:
        path = self._validate_file(file_path)
        available_sheets = self._spreadsheet_reader.list_sheets(str(path))
        if not available_sheets:
            raise ValueError("A planilha não possui abas.")

        selected_sheets = sheet_names or available_sheets
        imported_sheets: list[ImportResultDTO] = []
        skipped_sheets: list[str] = []

        for selected_sheet in selected_sheets:
            if selected_sheet not in available_sheets:
                skipped_sheets.append(selected_sheet)
                continue

            try:
                result = self._import_sheet(path, selected_sheet, progress_callback)
            except ValueError:
                skipped_sheets.append(selected_sheet)
                continue

            if result.total_rows == 0:
                skipped_sheets.append(selected_sheet)
                continue
            imported_sheets.append(result)

        if not imported_sheets:
            raise ValueError("Nenhuma aba com tabela de contatos foi encontrada.")

        return WorkbookImportResultDTO(
            file_name=path.name,
            total_rows=sum(result.total_rows for result in imported_sheets),
            imported_sheets=tuple(imported_sheets),
            skipped_sheets=tuple(skipped_sheets),
        )

    def _validate_file(self, file_path: str) -> Path:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")
        if path.suffix.lower() != ".xlsx":
            raise ValueError("Selecione um arquivo .xlsx.")
        return path

    def _import_sheet(
        self,
        path: Path,
        selected_sheet: str,
        progress_callback: ProgressCallback | None = None,
    ) -> ImportResultDTO:
        columns = self._spreadsheet_reader.read_headers(str(path), selected_sheet)
        if not columns:
            raise ValueError("A planilha precisa ter uma linha de cabeçalho.")
        if not self._looks_like_contact_table(columns):
            raise ValueError(f"A aba '{selected_sheet}' não parece uma lista de contatos.")

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
                        progress_callback(selected_sheet, total_rows)

            if batch:
                self._guest_repository.insert_guests(import_id, batch)
                total_rows += len(batch)
                if progress_callback is not None:
                    progress_callback(selected_sheet, total_rows)

            self._guest_repository.update_import_total_rows(import_id, total_rows)
        except Exception:
            self._guest_repository.delete_import(import_id)
            raise

        if total_rows == 0:
            self._guest_repository.delete_import(import_id)

        return ImportResultDTO(
            import_id=import_id,
            file_name=path.name,
            sheet_name=selected_sheet,
            total_rows=total_rows,
            columns=tuple(columns),
        )

    def _looks_like_contact_table(self, columns: list[str]) -> bool:
        normalized_columns = {column.casefold() for column in columns}
        return bool(normalized_columns.intersection(self._CONTACT_HEADER_WORDS))
