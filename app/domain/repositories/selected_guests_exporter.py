from collections.abc import Iterable, Sequence
from typing import Protocol

from app.domain.entities.guest_record import GuestRecord


class SelectedGuestsExporter(Protocol):
    def export(
        self,
        output_path: str,
        columns: Sequence[str],
        guests: Iterable[GuestRecord],
    ) -> int:
        raise NotImplementedError
