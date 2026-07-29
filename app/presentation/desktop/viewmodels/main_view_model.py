from collections.abc import Callable, Sequence

from app.application.dtos.guest_dto import GuestPageDTO, ImportResultDTO, ImportSummaryDTO
from app.application.use_cases.export_selected_guests import ExportSelectedGuestsUseCase
from app.application.use_cases.import_spreadsheet import ImportSpreadsheetUseCase
from app.application.use_cases.list_guests import ListGuestsUseCase, ListImportsUseCase
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
        self._list_imports = ListImportsUseCase(guest_repository)
        self._list_guests = ListGuestsUseCase(guest_repository)
        self._update_selection = UpdateGuestSelectionUseCase(guest_repository)
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
        progress_callback: Callable[[int], None] | None = None,
    ) -> ImportResultDTO:
        return self._import_spreadsheet.execute(
            file_path=file_path,
            sheet_name=sheet_name,
            progress_callback=progress_callback,
        )

    def list_imports(self) -> list[ImportSummaryDTO]:
        return self._list_imports.execute()

    def load_guests(
        self,
        import_id: int,
        page: int,
        page_size: int,
        search: str = "",
    ) -> GuestPageDTO:
        return self._list_guests.execute(
            import_id=import_id,
            page=page,
            page_size=page_size,
            search=search,
        )

    def set_guest_selected(self, guest_id: int, selected: bool) -> None:
        self._update_selection.set_guest_selected(guest_id, selected)

    def set_page_selected(self, guest_ids: Sequence[int], selected: bool) -> int:
        return self._update_selection.set_page_selected(guest_ids, selected)

    def set_all_filtered_selected(
        self,
        import_id: int,
        selected: bool,
        search: str = "",
    ) -> int:
        return self._update_selection.set_all_filtered_selected(
            import_id=import_id,
            selected=selected,
            search=search,
        )

    def export_selected(self, import_id: int, output_path: str) -> ImportResultDTO:
        return self._export_selected.execute(import_id, output_path)
