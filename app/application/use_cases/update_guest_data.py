from app.domain.repositories.guest_repository import GuestRepository


class UpdateGuestDataUseCase:
    def __init__(self, guest_repository: GuestRepository) -> None:
        self._guest_repository = guest_repository

    def execute(
        self,
        guest_id: int,
        column_name: str,
        value: object,
        automatic: bool = False,
    ) -> None:
        if guest_id <= 0:
            raise ValueError("Registro inválido para edição.")

        clean_column_name = column_name.strip()
        if not clean_column_name:
            raise ValueError("Coluna inválida para edição.")

        clean_value = "" if value is None else str(value).strip()
        if automatic:
            self._guest_repository.update_automatic_guest_data(
                source_guest_id=guest_id,
                column_name=clean_column_name,
                value=clean_value,
            )
        else:
            self._guest_repository.update_guest_data(
                guest_id=guest_id,
                column_name=clean_column_name,
                value=clean_value,
            )
