from app.domain.repositories.guest_repository import GuestRepository


class DeleteWorkbookUseCase:
    def __init__(self, guest_repository: GuestRepository) -> None:
        self._guest_repository = guest_repository

    def execute(self, workbook_id: int) -> None:
        self._guest_repository.delete_workbook(workbook_id)
