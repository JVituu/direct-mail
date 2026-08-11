from collections.abc import Mapping
from pathlib import Path
from unicodedata import combining, normalize

from app.application.dtos.guest_dto import ImportResultDTO
from app.domain.entities.spreadsheet_import import SpreadsheetImport
from app.domain.repositories.guest_repository import GuestRepository
from app.domain.value_objects.spreadsheet_row import SpreadsheetRow


MANUAL_FILE_NAME = "cadastros_manuais.xlsx"
MANUAL_SHEET_NAME = "Cadastros manuais"
MANUAL_COLUMNS = ("NOME", "Telefone", "Celular", "E-mail", "ENDEREÇO", "Categoria", "OBS")
MANUAL_COLUMN_WORDS = {
    "NOME": ("nome", "convidado", "pessoa", "cliente", "participante"),
    "Telefone": ("telefone", "phone", "fone", "tel"),
    "Celular": ("celular", "whatsapp", "mobile"),
    "E-mail": ("email", "e-mail", "mail"),
    "ENDEREÇO": ("endereco", "address", "logradouro", "rua", "avenida"),
    "Categoria": ("categoria", "category", "grupo", "tipo"),
    "OBS": ("obs", "observacao", "observacoes", "nota"),
}


class RegisterGuestUseCase:
    def __init__(self, guest_repository: GuestRepository) -> None:
        self._guest_repository = guest_repository

    def execute(
        self,
        values: Mapping[str, object],
        workbook_id: int | None = None,
    ) -> ImportResultDTO:
        clean_values = self._clean_values(values)
        if not clean_values["NOME"]:
            raise ValueError("Informe o nome do convidado.")

        target_workbook_id = self._target_workbook_id(workbook_id)
        imported_file = self._manual_import(target_workbook_id)
        column_map = self._manual_column_map(
            imported_file.columns,
            self._guest_repository.get_columns(None, target_workbook_id),
        )
        data = {
            column_map[column]: clean_values[column]
            for column in MANUAL_COLUMNS
        }

        row_number = imported_file.total_rows + 2
        self._guest_repository.insert_guests(
            imported_file.id,
            [SpreadsheetRow(row_number=row_number, values=data)],
        )

        import_total = self._guest_repository.count_guests(imported_file.id, target_workbook_id)
        workbook_total = self._guest_repository.count_guests(None, target_workbook_id)
        self._guest_repository.update_import_total_rows(imported_file.id, import_total)
        self._guest_repository.update_workbook_total_rows(target_workbook_id, workbook_total)

        return ImportResultDTO(
            import_id=imported_file.id,
            workbook_id=target_workbook_id,
            file_name=MANUAL_FILE_NAME,
            sheet_name=MANUAL_SHEET_NAME,
            total_rows=import_total,
            columns=tuple(column_map.values()),
            is_selectable=True,
        )

    def _clean_values(self, values: Mapping[str, object]) -> dict[str, str]:
        clean_values = {
            column: str(values.get(column, "") or "").strip()
            for column in MANUAL_COLUMNS
        }
        return clean_values

    def _target_workbook_id(self, workbook_id: int | None) -> int:
        if workbook_id is not None:
            return workbook_id

        workbooks = self._guest_repository.list_workbooks()
        if workbooks:
            return workbooks[0].id

        manual_path = Path(MANUAL_FILE_NAME)
        new_workbook_id = self._guest_repository.create_workbook(str(manual_path))
        self._guest_repository.rename_workbook(new_workbook_id, "Lista manual")
        return new_workbook_id

    def _manual_import(self, workbook_id: int) -> SpreadsheetImport:
        for imported_file in self._guest_repository.list_imports(workbook_id):
            if imported_file.sheet_name == MANUAL_SHEET_NAME:
                return imported_file

        columns = self._manual_columns(self._guest_repository.get_columns(None, workbook_id))
        import_id = self._guest_repository.create_import(
            workbook_id=workbook_id,
            file_path=MANUAL_FILE_NAME,
            sheet_name=MANUAL_SHEET_NAME,
            columns=columns,
            is_selectable=True,
        )
        imported_file = self._guest_repository.get_import(import_id)
        if imported_file is None:
            raise ValueError("Nao foi possivel preparar o cadastro manual.")
        return imported_file

    def _manual_columns(self, available_columns: tuple[str, ...]) -> tuple[str, ...]:
        column_map = self._manual_column_map(MANUAL_COLUMNS, available_columns)
        return tuple(column_map.values())

    def _manual_column_map(
        self,
        preferred_columns: tuple[str, ...],
        available_columns: tuple[str, ...],
    ) -> dict[str, str]:
        used_columns: set[str] = set()
        column_map: dict[str, str] = {}
        for default_column in MANUAL_COLUMNS:
            column_map[default_column] = self._matching_column(
                preferred_columns,
                default_column,
                used_columns,
            ) or self._matching_column(
                available_columns,
                default_column,
                used_columns,
            ) or default_column
            used_columns.add(column_map[default_column])
        return column_map

    def _matching_column(
        self,
        columns: tuple[str, ...],
        default_column: str,
        used_columns: set[str],
    ) -> str:
        words = MANUAL_COLUMN_WORDS[default_column]
        normalized_words = {self._normalize_text(word) for word in words}
        for column in columns:
            column_name = str(column).strip()
            if not column_name or column_name in used_columns:
                continue
            normalized_column = self._normalize_text(column_name)
            if any(word and word in normalized_column for word in normalized_words):
                return column_name
        return ""

    def _normalize_text(self, value: str) -> str:
        normalized = normalize("NFD", str(value).casefold())
        return "".join(character for character in normalized if not combining(character))
