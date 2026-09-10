from collections.abc import Iterable
from unicodedata import combining, normalize

from app.application.dtos.guest_dto import GuestFilterOptionsDTO
from app.application.services.contact_data_cleaner import ContactDataCleaner
from app.domain.entities.guest_record import GuestRecord
from app.domain.repositories.guest_repository import GuestRepository


CATEGORY_HEADER_WORDS = {"categoria", "category", "grupo", "group", "tipo", "classificacao", "classificação"}
CITY_HEADER_WORDS = {"cidade", "city", "municipio", "município"}
STATE_HEADER_WORDS = {"estado", "state", "uf"}
OPTIONS_PAGE_SIZE = 5000


class ListGuestFilterOptionsUseCase:
    def __init__(self, guest_repository: GuestRepository) -> None:
        self._guest_repository = guest_repository
        self._options_cache: dict[tuple[object, ...], GuestFilterOptionsDTO] = {}

    def clear_cache(self) -> None:
        self._options_cache.clear()

    def execute(
        self,
        import_id: int | None,
        workbook_id: int | None,
        selected_only: bool = False,
        duplicates_only: bool = False,
    ) -> GuestFilterOptionsDTO:
        columns = self._guest_repository.get_columns(import_id, workbook_id)
        cache_key = (import_id, workbook_id, selected_only, duplicates_only, columns)
        cached_options = self._options_cache.get(cache_key)
        if cached_options is not None:
            return cached_options

        cleaner = ContactDataCleaner(columns)
        category_columns = self._matching_columns(columns, CATEGORY_HEADER_WORDS)
        city_columns = self._matching_columns(columns, CITY_HEADER_WORDS)
        state_columns = self._matching_columns(columns, STATE_HEADER_WORDS)

        categories: set[str] = set()
        locations: set[str] = set()

        for guest in self._iter_context_guests(import_id, workbook_id, selected_only, duplicates_only):
            data = cleaner.clean_values(guest.data)
            category = self._first_value(data, category_columns)
            location = self._location_value(data, city_columns, state_columns)
            if category:
                categories.add(category)
            if location:
                locations.add(location)

        options = GuestFilterOptionsDTO(
            categories=tuple(sorted(categories, key=str.casefold)),
            locations=tuple(sorted(locations, key=str.casefold)),
        )
        self._options_cache[cache_key] = options
        return options

    def _iter_context_guests(
        self,
        import_id: int | None,
        workbook_id: int | None,
        selected_only: bool,
        duplicates_only: bool,
    ) -> Iterable[GuestRecord]:
        offset = 0
        while True:
            if selected_only:
                rows = self._guest_repository.list_automatic_guests(
                    import_id=import_id,
                    workbook_id=workbook_id,
                    limit=OPTIONS_PAGE_SIZE,
                    offset=offset,
                    duplicates_only=duplicates_only,
                )
            else:
                rows = self._guest_repository.list_guests(
                    import_id=import_id,
                    workbook_id=workbook_id,
                    limit=OPTIONS_PAGE_SIZE,
                    offset=offset,
                    duplicates_only=duplicates_only,
                )
            if not rows:
                break
            yield from rows
            offset += OPTIONS_PAGE_SIZE

    def _matching_columns(self, columns: tuple[str, ...], header_words: set[str]) -> tuple[str, ...]:
        normalized_words = {self._normalize_text(word) for word in header_words}
        matching_columns: list[str] = []
        for column in columns:
            normalized_column = self._normalize_text(column)
            if any(word and word in normalized_column for word in normalized_words):
                matching_columns.append(column)
        return tuple(matching_columns)

    def _location_value(
        self,
        data: dict[str, str],
        city_columns: tuple[str, ...],
        state_columns: tuple[str, ...],
    ) -> str:
        city = self._first_value(data, city_columns)
        state = self._first_value(data, state_columns)
        if city and state and self._normalize_text(state) not in self._normalize_text(city):
            return f"{city} - {state}"
        return city or state

    def _first_value(self, data: dict[str, str], columns: tuple[str, ...]) -> str:
        for column in columns:
            for item in str(data.get(column, "")).splitlines():
                clean_item = item.strip()
                if clean_item:
                    return clean_item
        return ""

    def _normalize_text(self, value: str) -> str:
        normalized = normalize("NFD", str(value).casefold())
        return "".join(character for character in normalized if not combining(character))
