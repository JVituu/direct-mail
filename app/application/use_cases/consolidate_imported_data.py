from app.application.dtos.guest_dto import WorkbookConsolidationResultDTO
from app.domain.repositories.guest_repository import GuestRepository


class ConsolidateImportedDataUseCase:
    def __init__(self, guest_repository: GuestRepository) -> None:
        self._guest_repository = guest_repository

    def execute(self) -> WorkbookConsolidationResultDTO:
        workbooks = self._guest_repository.list_workbooks()
        if not workbooks:
            return WorkbookConsolidationResultDTO(
                workbook_id=0,
                moved_sheets=0,
                removed_duplicates=0,
                total_rows=0,
            )

        target_workbook = min(workbooks, key=lambda workbook: workbook.id)
        moved_sheets = 0

        for workbook in sorted(workbooks, key=lambda workbook: workbook.id):
            if workbook.id == target_workbook.id:
                continue
            moved, _moved_rows, _target_total_rows = self._guest_repository.merge_workbooks(
                source_workbook_id=workbook.id,
                target_workbook_id=target_workbook.id,
            )
            moved_sheets += moved

        removed_duplicates = self._guest_repository.deduplicate_guests(target_workbook.id)
        refreshed_workbook = next(
            (
                workbook
                for workbook in self._guest_repository.list_workbooks()
                if workbook.id == target_workbook.id
            ),
            target_workbook,
        )

        return WorkbookConsolidationResultDTO(
            workbook_id=target_workbook.id,
            moved_sheets=moved_sheets,
            removed_duplicates=removed_duplicates,
            total_rows=refreshed_workbook.total_rows,
        )
