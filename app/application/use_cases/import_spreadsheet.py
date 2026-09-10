from collections.abc import Callable
from pathlib import Path
import re
from unicodedata import combining, normalize

from app.application.dtos.guest_dto import ImportResultDTO, WorkbookImportResultDTO
from app.application.services.contact_data_cleaner import ContactDataCleaner
from app.domain.repositories.guest_repository import GuestRepository
from app.domain.repositories.spreadsheet_reader import SpreadsheetReader
from app.domain.value_objects.spreadsheet_row import SpreadsheetRow

ProgressCallback = Callable[[str, int], None]


class ImportSpreadsheetUseCase:
    _EMAIL_HEADER_WORDS = ("email", "e-mail", "mail")
    _PHONE_HEADER_WORDS = ("telefone", "phone", "fone", "tel")
    _MOBILE_HEADER_WORDS = ("celular", "whatsapp", "mobile", "cell")
    _CEP_HEADER_WORDS = ("cep", "codigo postal", "postal code", "zip")
    _CONTACT_COLUMN_WORDS = ("contato", "contact")
    _COUNT_HEADER_WORDS = ("quantidade", "qtd", "total")
    _EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
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
        "convidado",
        "convidados",
        "pessoa",
        "pessoas",
        "cliente",
        "clientes",
        "participante",
        "participantes",
        "destinatario",
        "destinatário",
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

        workbook_id = self._guest_repository.create_workbook(str(path))
        result = self._import_sheet(workbook_id, path, selected_sheet, progress_callback)
        if result.total_rows == 0:
            self._guest_repository.delete_workbook(workbook_id)
            raise ValueError(f"A aba '{selected_sheet}' não possui registros para importar.")
        self._guest_repository.update_workbook_total_rows(workbook_id, result.total_rows)
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

        workbook_id = self._guest_repository.create_workbook(str(path))
        selected_sheets = sheet_names or available_sheets
        imported_sheets: list[ImportResultDTO] = []
        skipped_sheets: list[str] = []

        for selected_sheet in selected_sheets:
            if selected_sheet not in available_sheets:
                skipped_sheets.append(selected_sheet)
                continue

            try:
                result = self._import_sheet(workbook_id, path, selected_sheet, progress_callback)
            except ValueError:
                skipped_sheets.append(selected_sheet)
                continue

            if result.total_rows == 0:
                skipped_sheets.append(selected_sheet)
                continue
            imported_sheets.append(result)

        if not imported_sheets:
            self._guest_repository.delete_workbook(workbook_id)
            raise ValueError("Nenhuma aba com tabela foi encontrada.")

        total_rows = sum(result.total_rows for result in imported_sheets)
        self._guest_repository.update_workbook_total_rows(workbook_id, total_rows)

        return WorkbookImportResultDTO(
            workbook_id=workbook_id,
            file_name=path.name,
            total_rows=total_rows,
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
        workbook_id: int,
        path: Path,
        selected_sheet: str,
        progress_callback: ProgressCallback | None = None,
    ) -> ImportResultDTO:
        columns = self._spreadsheet_reader.read_headers(str(path), selected_sheet)
        if not columns:
            raise ValueError("A planilha precisa ter uma linha de cabeçalho.")
        should_clean = self._looks_like_contact_table(columns)
        cleaner = ContactDataCleaner(columns) if should_clean else None
        active_columns = self._active_columns_for_sheet(path, selected_sheet, columns, cleaner)
        if not active_columns:
            raise ValueError(f"A aba '{selected_sheet}' não possui colunas com dados para importar.")
        is_selectable = self._looks_like_contact_table(active_columns)

        import_id = self._guest_repository.create_import(
            workbook_id=workbook_id,
            file_path=str(path),
            sheet_name=selected_sheet,
            columns=active_columns,
            is_selectable=is_selectable,
        )

        total_rows = 0
        batch: list[SpreadsheetRow] = []
        try:
            for row in self._spreadsheet_reader.iter_rows(str(path), selected_sheet):
                clean_row = self._clean_import_row(row, active_columns, cleaner)
                if clean_row is None:
                    continue
                batch.append(clean_row)
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
            workbook_id=workbook_id,
            file_name=path.name,
            sheet_name=selected_sheet,
            total_rows=total_rows,
            columns=tuple(active_columns),
            is_selectable=is_selectable,
        )

    def _active_columns_for_sheet(
        self,
        path: Path,
        selected_sheet: str,
        columns: list[str],
        cleaner: ContactDataCleaner | None,
    ) -> tuple[str, ...]:
        active_columns: set[str] = set()
        for row in self._spreadsheet_reader.iter_rows(str(path), selected_sheet):
            values = self._clean_values(row.values, cleaner)
            for column in columns:
                if column in active_columns:
                    continue
                if self._has_meaningful_value(column, values.get(column, "")):
                    active_columns.add(column)
            if len(active_columns) == len(columns):
                break
        return tuple(column for column in columns if column in active_columns)

    def _clean_import_row(
        self,
        row: SpreadsheetRow,
        active_columns: tuple[str, ...],
        cleaner: ContactDataCleaner | None,
    ) -> SpreadsheetRow | None:
        values = self._clean_values(row.values, cleaner)
        pruned_values = {
            column: value
            for column in active_columns
            if (value := self._clean_cell_value(column, values.get(column, "")))
        }
        if not pruned_values:
            return None
        return SpreadsheetRow(row_number=row.row_number, values=pruned_values)

    def _clean_values(
        self,
        values: dict[str, str],
        cleaner: ContactDataCleaner | None,
    ) -> dict[str, str]:
        if cleaner is not None:
            return cleaner.clean_values(values)
        return {column: str(value or "").strip() for column, value in values.items()}

    def _clean_cell_value(self, column_name: str, value: object) -> str:
        text = str(value or "").strip()
        if not self._has_meaningful_value(column_name, text):
            return ""
        return text

    def _has_meaningful_value(self, column_name: str, value: object) -> bool:
        text = str(value or "").strip()
        if not text:
            return False

        normalized_column = self._normalize_match_text(column_name)
        if self._column_matches(normalized_column, self._COUNT_HEADER_WORDS):
            return True
        if self._column_matches(normalized_column, self._EMAIL_HEADER_WORDS):
            return bool(self._EMAIL_PATTERN.search(text))
        if self._column_matches(normalized_column, self._CEP_HEADER_WORDS):
            return any(len(re.sub(r"\D+", "", item)) == 8 for item in self._split_cell_values(text))
        if self._column_matches(normalized_column, self._PHONE_HEADER_WORDS + self._MOBILE_HEADER_WORDS):
            return any(len(re.sub(r"\D+", "", item)) >= 8 for item in self._split_cell_values(text))
        if self._column_matches(normalized_column, self._CONTACT_COLUMN_WORDS):
            return bool(self._EMAIL_PATTERN.search(text)) or any(
                len(re.sub(r"\D+", "", item)) >= 8 for item in self._split_cell_values(text)
            )
        return True

    def _split_cell_values(self, value: str) -> list[str]:
        return [
            item.strip()
            for item in str(value or "").replace("\r", "\n").split("\n")
            if item.strip()
        ]

    def _column_matches(self, normalized_column: str, words: tuple[str, ...]) -> bool:
        return any(word and word in normalized_column for word in words)

    def _looks_like_contact_table(self, columns: tuple[str, ...] | list[str]) -> bool:
        normalized_words = {self._normalize_match_text(word) for word in self._CONTACT_HEADER_WORDS}
        for column in columns:
            normalized_column = self._normalize_match_text(column)
            if any(self._matches_contact_word(normalized_column, word) for word in normalized_words):
                return True
        return False

    def _matches_contact_word(self, normalized_column: str, word: str) -> bool:
        if not word:
            return False
        if word in {"contato", "contact"}:
            tokens = normalized_column.replace("-", " ").replace("/", " ").split()
            return word in tokens
        return word in normalized_column

    def _normalize_match_text(self, value: str) -> str:
        normalized = normalize("NFD", value.casefold())
        return "".join(character for character in normalized if not combining(character))
