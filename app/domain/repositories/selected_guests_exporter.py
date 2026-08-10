from collections.abc import Iterable, Sequence
from typing import Protocol

from app.domain.entities.guest_record import GuestRecord


class SelectedGuestsExporter(Protocol):
    def export(
        self,
        output_path: str,
        columns: Sequence[str],
        guests: Iterable[GuestRecord],
        sheet_name: str = "Selecionados",
    ) -> int:
        raise NotImplementedError

    def export_by_category(
        self,
        output_path: str,
        columns: Sequence[str],
        guests: Iterable[GuestRecord],
        category_column: str,
    ) -> int:
        raise NotImplementedError

    def export_name_checklist_pdf(
        self,
        output_path: str,
        guests: Iterable[GuestRecord],
        title: str,
    ) -> int:
        raise NotImplementedError
