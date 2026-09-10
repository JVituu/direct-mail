from app.domain.repositories.guest_repository import GuestRepository


class CreateGuestColumnUseCase:
    def __init__(self, guest_repository: GuestRepository) -> None:
        self._guest_repository = guest_repository

    def execute(
        self,
        column_name: str,
        import_id: int | None = None,
        workbook_id: int | None = None,
        automatic: bool = False,
    ) -> int:
        clean_column_name = str(column_name or "").strip()
        if not clean_column_name:
            raise ValueError("Informe o nome da coluna.")
        if not automatic and import_id is None and workbook_id is None:
            raise ValueError("Abra uma planilha antes de criar uma coluna.")

        updated_lists = self._guest_repository.add_guest_column(
            column_name=clean_column_name,
            import_id=import_id,
            workbook_id=workbook_id,
            automatic=automatic,
        )
        if updated_lists <= 0:
            raise ValueError("Nenhuma lista disponível para receber a nova coluna.")
        return updated_lists
