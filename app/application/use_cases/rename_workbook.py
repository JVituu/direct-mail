from app.domain.repositories.guest_repository import GuestRepository


class RenameWorkbookUseCase:
    def __init__(self, guest_repository: GuestRepository) -> None:
        self._guest_repository = guest_repository

    def execute(self, workbook_id: int, display_name: str) -> None:
        clean_name = display_name.strip()
        if not clean_name:
            raise ValueError("Informe um nome para a planilha.")
        self._guest_repository.rename_workbook(workbook_id, clean_name)
