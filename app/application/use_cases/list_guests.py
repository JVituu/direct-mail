from collections.abc import Iterable
import re
from unicodedata import combining, normalize

from app.application.dtos.guest_dto import (
    GuestPageDTO,
    GuestRowDTO,
    ImportSummaryDTO,
    WorkbookSummaryDTO,
)
from app.application.services.contact_data_cleaner import ContactDataCleaner
from app.domain.entities.imported_workbook import ImportedWorkbook
from app.domain.entities.spreadsheet_import import SpreadsheetImport
from app.domain.repositories.guest_repository import GuestRepository


CATEGORY_HEADER_WORDS = ("categoria", "category")
EMAIL_HEADER_WORDS = ("email", "e-mail", "mail")
PHONE_HEADER_WORDS = ("telefone", "phone", "fone", "tel")
MOBILE_HEADER_WORDS = ("celular", "whatsapp", "mobile", "cell")
CEP_HEADER_WORDS = ("cep", "codigo postal", "postal code", "zip")
CONTACT_HEADER_WORDS = ("contato", "contact")
COUNT_HEADER_WORDS = ("quantidade", "qtd", "total")
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


class ListWorkbooksUseCase:
    def __init__(self, guest_repository: GuestRepository) -> None:
        self._guest_repository = guest_repository

    def execute(self) -> list[WorkbookSummaryDTO]:
        return [self._to_workbook_dto(workbook) for workbook in self._guest_repository.list_workbooks()]

    def _to_workbook_dto(self, workbook: ImportedWorkbook) -> WorkbookSummaryDTO:
        return WorkbookSummaryDTO(
            id=workbook.id,
            file_name=workbook.file_name,
            display_name=workbook.display_name,
            file_path=workbook.file_path,
            imported_at=workbook.imported_at,
            total_rows=workbook.total_rows,
        )


class ListImportsUseCase:
    def __init__(self, guest_repository: GuestRepository) -> None:
        self._guest_repository = guest_repository

    def execute(self, workbook_id: int | None = None) -> list[ImportSummaryDTO]:
        return [
            self._to_summary_dto(imported_file)
            for imported_file in self._guest_repository.list_imports(workbook_id)
        ]

    def _to_summary_dto(self, imported_file: SpreadsheetImport) -> ImportSummaryDTO:
        return ImportSummaryDTO(
            id=imported_file.id,
            workbook_id=imported_file.workbook_id,
            file_name=imported_file.file_name,
            sheet_name=imported_file.sheet_name,
            imported_at=imported_file.imported_at,
            total_rows=imported_file.total_rows,
            columns=imported_file.columns,
            is_selectable=imported_file.is_selectable,
        )


class ListGuestsUseCase:
    def __init__(self, guest_repository: GuestRepository) -> None:
        self._guest_repository = guest_repository
        self._display_columns_cache: dict[tuple[object, ...], tuple[str, ...]] = {}

    def clear_cache(self) -> None:
        self._display_columns_cache.clear()

    def execute(
        self,
        import_id: int | None,
        workbook_id: int | None,
        page: int,
        page_size: int,
        search: str = "",
        selected_only: bool = False,
        duplicates_only: bool = False,
    ) -> GuestPageDTO:
        imported_file = self._guest_repository.get_import(import_id) if import_id is not None else None
        if import_id is not None and imported_file is None:
            raise ValueError("Importação não encontrada.")

        safe_page = max(page, 0)
        safe_page_size = min(max(page_size, 50), 5000)
        if selected_only:
            total_rows = self._guest_repository.count_automatic_guests(
                import_id,
                workbook_id,
                search,
                duplicates_only=duplicates_only,
            )
            selected_rows = total_rows
        else:
            total_rows = self._guest_repository.count_guests(
                import_id,
                workbook_id,
                search,
                duplicates_only=duplicates_only,
            )
            selected_rows = self._guest_repository.count_selected_guests(import_id, workbook_id, search)
        offset = safe_page * safe_page_size
        columns = self._guest_repository.get_columns(import_id, workbook_id)
        display_source_columns, merged_column_aliases = self._display_column_projection(columns)
        cleaner = ContactDataCleaner(columns)
        display_source_columns = self._remove_empty_display_columns(
            display_source_columns,
            merged_column_aliases,
            cleaner,
            import_id,
            workbook_id,
            selected_only,
            total_rows,
        )
        include_list_column = import_id is None or selected_only
        display_columns = (
            ("Lista", *display_source_columns)
            if include_list_column
            else display_source_columns
        )
        editable_columns = display_source_columns

        if selected_only:
            rows = self._guest_repository.list_automatic_guests(
                import_id=import_id,
                workbook_id=workbook_id,
                limit=safe_page_size,
                offset=offset,
                search=search,
                duplicates_only=duplicates_only,
            )
        else:
            rows = self._guest_repository.list_guests(
                import_id=import_id,
                workbook_id=workbook_id,
                limit=safe_page_size,
                offset=offset,
                search=search,
                selected_only=False,
                duplicates_only=duplicates_only,
            )

        guest_rows = [
            GuestRowDTO(
                id=row.id or 0,
                import_id=row.import_id,
                sheet_name=row.sheet_name,
                row_number=row.row_number,
                verification_code=row.verification_code,
                data=self._to_display_data(
                    row.sheet_name,
                    self._project_display_data(
                        cleaner.clean_values(row.data),
                        display_source_columns,
                        merged_column_aliases,
                    ),
                    include_list_column,
                ),
                selected=row.selected,
                selectable=row.selectable,
                duplicate_reason=row.duplicate_reason,
                duplicate_count=row.duplicate_count,
                invitation_status=row.invitation_status,
                contact_statuses=dict(row.contact_statuses),
            )
            for row in rows
        ]

        return GuestPageDTO(
            rows=guest_rows,
            columns=display_columns,
            editable_columns=editable_columns,
            total_rows=total_rows,
            selected_rows=selected_rows,
            page=safe_page,
            page_size=safe_page_size,
        )

    def _to_display_data(
        self,
        sheet_name: str,
        data: dict[str, str],
        include_list_column: bool,
    ) -> dict[str, str]:
        if not include_list_column:
            return data
        return {"Lista": sheet_name, **data}

    def _remove_empty_display_columns(
        self,
        display_columns: tuple[str, ...],
        merged_column_aliases: dict[str, tuple[str, ...]],
        cleaner: ContactDataCleaner,
        import_id: int | None,
        workbook_id: int | None,
        selected_only: bool,
        total_rows: int,
    ) -> tuple[str, ...]:
        if not display_columns:
            return display_columns

        cache_key = (
            import_id,
            workbook_id,
            selected_only,
            total_rows,
            display_columns,
            tuple(sorted(merged_column_aliases.items())),
        )
        cached_columns = self._display_columns_cache.get(cache_key)
        if cached_columns is not None:
            return cached_columns

        filled_columns: set[str] = set()
        scanned_rows = False
        for row in self._iter_context_rows(import_id, workbook_id, selected_only):
            scanned_rows = True
            data = self._project_display_data(
                cleaner.clean_values(row.data),
                display_columns,
                merged_column_aliases,
            )
            for column in display_columns:
                if self._has_meaningful_value(column, data.get(column, "")):
                    filled_columns.add(column)
            if len(filled_columns) == len(display_columns):
                break

        if not scanned_rows or not filled_columns:
            self._display_columns_cache[cache_key] = display_columns
            return display_columns
        filtered_columns = tuple(column for column in display_columns if column in filled_columns)
        self._display_columns_cache[cache_key] = filtered_columns
        return filtered_columns

    def _iter_context_rows(
        self,
        import_id: int | None,
        workbook_id: int | None,
        selected_only: bool,
    ) -> Iterable[object]:
        if selected_only:
            return self._guest_repository.iter_automatic_guests(import_id, workbook_id)
        return self._guest_repository.iter_guests(import_id, workbook_id)

    def _display_column_projection(
        self,
        columns: tuple[str, ...],
    ) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
        display_columns: list[str] = []
        aliases_by_column: dict[str, list[str]] = {}
        category_column: str | None = None

        for column in columns:
            if self._is_category_column(column):
                if category_column is None:
                    category_column = column
                    display_columns.append(column)
                    aliases_by_column[column] = [column]
                else:
                    aliases_by_column[category_column].append(column)
                continue

            display_columns.append(column)
            aliases_by_column[column] = [column]

        merged_aliases = {
            column: tuple(aliases)
            for column, aliases in aliases_by_column.items()
            if len(aliases) > 1
        }
        return tuple(display_columns), merged_aliases

    def _project_display_data(
        self,
        data: dict[str, str],
        display_columns: tuple[str, ...],
        merged_column_aliases: dict[str, tuple[str, ...]],
    ) -> dict[str, str]:
        projected_data = {column: str(data.get(column, "")) for column in display_columns}
        for column, aliases in merged_column_aliases.items():
            projected_data[column] = self._merge_cell_values(data.get(alias, "") for alias in aliases)
        return projected_data

    def _merge_cell_values(self, values: Iterable[object]) -> str:
        merged_values: list[str] = []
        seen: set[str] = set()
        for value in values:
            for item in str(value or "").replace("\r", "\n").split("\n"):
                clean_item = item.strip()
                if not clean_item:
                    continue
                normalized_item = self._normalize_column_text(clean_item)
                if normalized_item in seen:
                    continue
                merged_values.append(clean_item)
                seen.add(normalized_item)
        return "\n".join(merged_values)

    def _is_category_column(self, column_name: str) -> bool:
        normalized_column = self._normalize_column_text(column_name)
        return any(word and word in normalized_column for word in CATEGORY_HEADER_WORDS)

    def _has_meaningful_value(self, column_name: str, value: object) -> bool:
        text = str(value or "").strip()
        if not text:
            return False

        normalized_column = self._normalize_column_text(column_name)
        if self._column_matches(normalized_column, COUNT_HEADER_WORDS):
            return True
        if self._column_matches(normalized_column, EMAIL_HEADER_WORDS):
            return bool(EMAIL_PATTERN.search(text))
        if self._column_matches(normalized_column, CEP_HEADER_WORDS):
            return any(len(re.sub(r"\D+", "", item)) == 8 for item in self._split_cell_values(text))
        if self._column_matches(normalized_column, PHONE_HEADER_WORDS + MOBILE_HEADER_WORDS):
            return any(len(re.sub(r"\D+", "", item)) >= 8 for item in self._split_cell_values(text))
        if self._column_matches(normalized_column, CONTACT_HEADER_WORDS):
            return bool(EMAIL_PATTERN.search(text)) or any(
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

    def _normalize_column_text(self, value: str) -> str:
        normalized = normalize("NFD", str(value).casefold())
        return "".join(character for character in normalized if not combining(character))
