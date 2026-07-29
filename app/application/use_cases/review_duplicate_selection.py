from app.application.dtos.guest_dto import GuestRowDTO
from app.domain.entities.guest_record import GuestRecord
from app.domain.repositories.guest_repository import GuestRepository


class ReviewDuplicateSelectionUseCase:
    def __init__(self, guest_repository: GuestRepository) -> None:
        self._guest_repository = guest_repository

    def list_duplicate_candidates(self, guest_id: int) -> list[GuestRowDTO]:
        return [
            self._to_guest_dto(guest)
            for guest in self._guest_repository.list_duplicate_candidates(guest_id)
        ]

    def list_automatic_conflicts(self, guest_id: int) -> list[GuestRowDTO]:
        return [
            self._to_guest_dto(guest)
            for guest in self._guest_repository.list_automatic_conflicts(guest_id)
        ]

    def _to_guest_dto(self, guest: GuestRecord) -> GuestRowDTO:
        return GuestRowDTO(
            id=guest.id or 0,
            import_id=guest.import_id,
            sheet_name=guest.sheet_name,
            row_number=guest.row_number,
            verification_code=guest.verification_code,
            data=guest.data,
            selected=guest.selected,
            selectable=guest.selectable,
            duplicate_reason=guest.duplicate_reason,
            duplicate_count=guest.duplicate_count,
        )
