from app.application.dtos.guest_dto import WorkbookMergeResultDTO
from app.domain.repositories.guest_repository import GuestRepository


class MergeWorkbooksUseCase:
    def __init__(self, guest_repository: GuestRepository) -> None:
        self._guest_repository = guest_repository

    def execute(self, source_workbook_id: int, target_workbook_id: int) -> WorkbookMergeResultDTO:
        moved_sheets, moved_rows, target_total_rows = self._guest_repository.merge_workbooks(
            source_workbook_id=source_workbook_id,
            target_workbook_id=target_workbook_id,
        )
        return WorkbookMergeResultDTO(
            source_workbook_id=source_workbook_id,
            target_workbook_id=target_workbook_id,
            moved_sheets=moved_sheets,
            moved_rows=moved_rows,
            target_total_rows=target_total_rows,
        )
