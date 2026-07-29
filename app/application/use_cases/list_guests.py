from app.application.dtos.guest_dto import GuestPageDTO, GuestRowDTO, ImportSummaryDTO
from app.domain.entities.spreadsheet_import import SpreadsheetImport
from app.domain.repositories.guest_repository import GuestRepository


class ListImportsUseCase:
    def __init__(self, guest_repository: GuestRepository) -> None:
        self._guest_repository = guest_repository

    def execute(self) -> list[ImportSummaryDTO]:
        return [self._to_summary_dto(imported_file) for imported_file in self._guest_repository.list_imports()]

    def _to_summary_dto(self, imported_file: SpreadsheetImport) -> ImportSummaryDTO:
        return ImportSummaryDTO(
            id=imported_file.id,
            file_name=imported_file.file_name,
            sheet_name=imported_file.sheet_name,
            imported_at=imported_file.imported_at,
            total_rows=imported_file.total_rows,
            columns=imported_file.columns,
        )


class ListGuestsUseCase:
    def __init__(self, guest_repository: GuestRepository) -> None:
        self._guest_repository = guest_repository

    def execute(
        self,
        import_id: int | None,
        page: int,
        page_size: int,
        search: str = "",
        selected_only: bool = False,
    ) -> GuestPageDTO:
        imported_file = self._guest_repository.get_import(import_id) if import_id is not None else None
        if import_id is not None and imported_file is None:
            raise ValueError("Importação não encontrada.")

        safe_page = max(page, 0)
        safe_page_size = min(max(page_size, 50), 5000)
        if selected_only:
            total_rows = self._guest_repository.count_selected_guests(import_id, search)
        else:
            total_rows = self._guest_repository.count_guests(import_id, search)
        selected_rows = self._guest_repository.count_selected_guests(import_id, search)
        offset = safe_page * safe_page_size
        columns = self._guest_repository.get_columns(import_id)
        include_list_column = import_id is None or selected_only
        display_columns = (("Lista", *columns) if include_list_column else columns)

        rows = self._guest_repository.list_guests(
            import_id=import_id,
            limit=safe_page_size,
            offset=offset,
            search=search,
            selected_only=selected_only,
        )

        guest_rows = [
            GuestRowDTO(
                id=row.id or 0,
                import_id=row.import_id,
                sheet_name=row.sheet_name,
                row_number=row.row_number,
                data=self._to_display_data(row.sheet_name, row.data, include_list_column),
                selected=row.selected,
            )
            for row in rows
        ]

        return GuestPageDTO(
            rows=guest_rows,
            columns=display_columns,
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
