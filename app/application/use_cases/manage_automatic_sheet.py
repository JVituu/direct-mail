from app.domain.repositories.guest_repository import GuestRepository


DEFAULT_AUTOMATIC_SHEET_NAME = "Planilha automática"


class ManageAutomaticSheetUseCase:
    def __init__(self, guest_repository: GuestRepository) -> None:
        self._guest_repository = guest_repository

    def get_name(self) -> str:
        return self._guest_repository.get_automatic_sheet_name()

    def rename(self, display_name: str) -> None:
        clean_name = display_name.strip()
        if not clean_name:
            raise ValueError("Informe um nome para a planilha.")
        self._guest_repository.rename_automatic_sheet(clean_name)

    def clear(self) -> int:
        selected_rows = self._guest_repository.clear_automatic_guests()
        self._guest_repository.rename_automatic_sheet(DEFAULT_AUTOMATIC_SHEET_NAME)
        return selected_rows
