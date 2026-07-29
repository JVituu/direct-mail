from collections.abc import Sequence

from app.domain.repositories.guest_repository import GuestRepository


class UpdateGuestSelectionUseCase:
    def __init__(self, guest_repository: GuestRepository) -> None:
        self._guest_repository = guest_repository

    def set_guest_selected(self, guest_id: int, selected: bool) -> None:
        self._guest_repository.set_guest_selected(guest_id, selected)

    def set_page_selected(self, guest_ids: Sequence[int], selected: bool) -> int:
        if not guest_ids:
            return 0
        return self._guest_repository.set_guests_selected(
            import_id=0,
            selected=selected,
            guest_ids=guest_ids,
        )

    def set_all_filtered_selected(
        self,
        import_id: int,
        selected: bool,
        search: str = "",
    ) -> int:
        return self._guest_repository.set_guests_selected(
            import_id=import_id,
            selected=selected,
            search=search,
        )
