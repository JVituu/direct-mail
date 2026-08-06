from collections.abc import Callable, Sequence

from app.application.dtos.guest_dto import (
    GuestPageDTO,
    GuestRowDTO,
    ImportResultDTO,
    ImportSummaryDTO,
    WorkbookMergeResultDTO,
    WorkbookImportResultDTO,
    WorkbookSummaryDTO,
)
from app.application.use_cases.delete_workbook import DeleteWorkbookUseCase
from app.application.use_cases.export_selected_guests import ExportSelectedGuestsUseCase
from app.application.use_cases.import_spreadsheet import ImportSpreadsheetUseCase
from app.application.use_cases.list_guests import ListGuestsUseCase, ListImportsUseCase, ListWorkbooksUseCase
from app.application.use_cases.manage_automatic_sheet import ManageAutomaticSheetUseCase
from app.application.use_cases.merge_workbooks import MergeWorkbooksUseCase
from app.application.use_cases.rename_workbook import RenameWorkbookUseCase
from app.application.use_cases.review_duplicate_selection import ReviewDuplicateSelectionUseCase
from app.application.use_cases.update_guest_data import UpdateGuestDataUseCase
from app.application.use_cases.update_guest_selection import UpdateGuestSelectionUseCase
from app.domain.repositories.guest_repository import GuestRepository
from app.domain.repositories.selected_guests_exporter import SelectedGuestsExporter
from app.domain.repositories.spreadsheet_reader import SpreadsheetReader


class MainViewModel:
    def __init__(
        self,
        guest_repository: GuestRepository,
        spreadsheet_reader: SpreadsheetReader,
        selected_guests_exporter: SelectedGuestsExporter,
    ) -> None:
        self._guest_repository = guest_repository
        self._spreadsheet_reader = spreadsheet_reader
        self._selected_guests_exporter = selected_guests_exporter
        self._import_spreadsheet = ImportSpreadsheetUseCase(
            guest_repository=guest_repository,
            spreadsheet_reader=spreadsheet_reader,
        )
        self._list_workbooks = ListWorkbooksUseCase(guest_repository)
        self._list_imports = ListImportsUseCase(guest_repository)
        self._list_guests = ListGuestsUseCase(guest_repository)
        self._update_guest_data = UpdateGuestDataUseCase(guest_repository)
        self._update_selection = UpdateGuestSelectionUseCase(guest_repository)
        self._delete_workbook = DeleteWorkbookUseCase(guest_repository)
        self._merge_workbooks = MergeWorkbooksUseCase(guest_repository)
        self._rename_workbook = RenameWorkbookUseCase(guest_repository)
        self._manage_automatic_sheet = ManageAutomaticSheetUseCase(guest_repository)
        self._review_duplicate_selection = ReviewDuplicateSelectionUseCase(guest_repository)
        self._export_selected = ExportSelectedGuestsUseCase(
            guest_repository=guest_repository,
            exporter=selected_guests_exporter,
        )

    def initialize(self) -> None:
        self._guest_repository.initialize()

    def list_sheets(self, file_path: str) -> list[str]:
        return self._spreadsheet_reader.list_sheets(file_path)

    def import_spreadsheet(
        self,
        file_path: str,
        sheet_name: str,
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> ImportResultDTO:
        return self._import_spreadsheet.execute(
            file_path=file_path,
            sheet_name=sheet_name,
            progress_callback=progress_callback,
        )

    def import_workbook(
        self,
        file_path: str,
        sheet_names: list[str] | None = None,
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> WorkbookImportResultDTO:
        return self._import_spreadsheet.execute_workbook(
            file_path=file_path,
            sheet_names=sheet_names,
            progress_callback=progress_callback,
        )

    def list_workbooks(self) -> list[WorkbookSummaryDTO]:
        return self._list_workbooks.execute()

    def list_imports(self, workbook_id: int | None = None) -> list[ImportSummaryDTO]:
        return self._list_imports.execute(workbook_id)

    def load_guests(
        self,
        import_id: int | None,
        workbook_id: int | None,
        page: int,
        page_size: int,
        search: str = "",
        selected_only: bool = False,
        duplicates_only: bool = False,
    ) -> GuestPageDTO:
        return self._list_guests.execute(
            import_id=import_id,
            workbook_id=workbook_id,
            page=page,
            page_size=page_size,
            search=search,
            selected_only=selected_only,
            duplicates_only=duplicates_only,
        )

    def set_guest_selected(self, guest_id: int, selected: bool) -> None:
        self._update_selection.set_guest_selected(guest_id, selected)

    def list_duplicate_candidates(self, guest_id: int) -> list[GuestRowDTO]:
        return self._review_duplicate_selection.list_duplicate_candidates(guest_id)

    def list_automatic_conflicts(self, guest_id: int) -> list[GuestRowDTO]:
        return self._review_duplicate_selection.list_automatic_conflicts(guest_id)

    def update_guest_data(
        self,
        guest_id: int,
        column_name: str,
        value: object,
        automatic: bool = False,
    ) -> None:
        self._update_guest_data.execute(guest_id, column_name, value, automatic=automatic)

    def set_page_selected(self, guest_ids: Sequence[int], selected: bool) -> int:
        return self._update_selection.set_page_selected(guest_ids, selected)

    def set_all_filtered_selected(
        self,
        import_id: int | None,
        workbook_id: int | None,
        selected: bool,
        search: str = "",
    ) -> int:
        return self._update_selection.set_all_filtered_selected(
            import_id=import_id,
            workbook_id=workbook_id,
            selected=selected,
            search=search,
        )

    def delete_workbook(self, workbook_id: int) -> None:
        self._delete_workbook.execute(workbook_id)

    def merge_workbooks(
        self,
        source_workbook_id: int,
        target_workbook_id: int,
    ) -> WorkbookMergeResultDTO:
        return self._merge_workbooks.execute(source_workbook_id, target_workbook_id)

    def rename_workbook(self, workbook_id: int, display_name: str) -> None:
        self._rename_workbook.execute(workbook_id, display_name)

    def automatic_sheet_name(self) -> str:
        return self._manage_automatic_sheet.get_name()

    def rename_automatic_sheet(self, display_name: str) -> None:
        self._manage_automatic_sheet.rename(display_name)

    def clear_automatic_sheet(self) -> int:
        return self._manage_automatic_sheet.clear()

    def export_selected(
        self,
        import_id: int | None,
        output_path: str,
        workbook_id: int | None = None,
    ) -> ImportResultDTO:
        return self._export_selected.execute(import_id, output_path, workbook_id)


