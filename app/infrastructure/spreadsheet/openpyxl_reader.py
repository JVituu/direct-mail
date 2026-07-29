from collections.abc import Iterable
from datetime import date, datetime
from unicodedata import combining, normalize

from openpyxl import load_workbook

from app.domain.value_objects.spreadsheet_row import SpreadsheetRow


class OpenpyxlSpreadsheetReader:
    _MAX_HEADER_SCAN_ROWS = 80
    _CONTACT_HEADER_WORDS = {
        "nome",
        "name",
        "email",
        "e-mail",
        "telefone",
        "phone",
        "celular",
        "whatsapp",
        "endereco",
        "endereço",
        "contato",
        "contact",
        "convidado",
        "convidados",
        "pessoa",
        "pessoas",
        "cliente",
        "clientes",
        "participante",
        "participantes",
        "destinatario",
        "destinatário",
    }
    _TABLE_HEADER_WORDS = _CONTACT_HEADER_WORDS | {
        "categoria",
        "category",
        "lista",
        "total",
        "quantidade",
        "quantidade de contatos",
    }

    def list_sheets(self, file_path: str) -> list[str]:
        workbook = load_workbook(file_path, read_only=True, data_only=True)
        try:
            return list(workbook.sheetnames)
        finally:
            workbook.close()

    def read_headers(self, file_path: str, sheet_name: str) -> list[str]:
        workbook = load_workbook(file_path, read_only=True, data_only=True)
        try:
            worksheet = workbook[sheet_name]
            table = self._find_table_header(worksheet)
            if table is None:
                return []
            _, headers = table
            return headers
        finally:
            workbook.close()

    def has_table(self, file_path: str, sheet_name: str) -> bool:
        return bool(self.read_headers(file_path, sheet_name))

    def iter_rows(self, file_path: str, sheet_name: str) -> Iterable[SpreadsheetRow]:
        workbook = load_workbook(file_path, read_only=True, data_only=True)
        try:
            worksheet = workbook[sheet_name]
            table = self._find_table_header(worksheet)
            if table is None:
                return

            header_row_number, columns = table
            rows = worksheet.iter_rows(
                min_row=header_row_number + 1,
                values_only=True,
            )
            for row_number, raw_values in enumerate(rows, start=header_row_number + 1):
                values = self._row_to_dict(columns, raw_values)
                if any(value for value in values.values()):
                    yield SpreadsheetRow(row_number=row_number, values=values)
        finally:
            workbook.close()

    def _find_table_header(self, worksheet: object) -> tuple[int, list[str]] | None:
        sample: list[tuple[int, tuple[object, ...]]] = []
        for row_number, raw_values in enumerate(worksheet.iter_rows(values_only=True), start=1):
            sample.append((row_number, raw_values))
            if len(sample) >= self._MAX_HEADER_SCAN_ROWS:
                break

        best_candidate: tuple[int, int, list[str]] | None = None

        for index, (row_number, raw_values) in enumerate(sample):
            headers = self._normalize_headers(raw_values)
            header_texts = self._raw_text_values(raw_values)
            if not header_texts:
                continue
            score = self._score_header_candidate(header_texts, sample, index, len(headers))
            if score <= 0:
                continue

            if best_candidate is None or score > best_candidate[0]:
                best_candidate = (score, row_number, headers)

        if best_candidate is None:
            return None
        _, row_number, headers = best_candidate
        return row_number, headers

    def _score_header_candidate(
        self,
        header_texts: list[str],
        sample: list[tuple[int, tuple[object, ...]]],
        header_index: int,
        expected_columns: int,
    ) -> int:
        if expected_columns <= 0:
            return 0

        known_words = self._known_words_in_headers(header_texts, self._TABLE_HEADER_WORDS)

        # A long single-cell row is usually a title or description, not a table header.
        if len(header_texts) == 1 and not known_words and len(header_texts[0]) > 70:
            return 0
        if len(header_texts) == 1 and not known_words:
            return 0
        if not self._has_data_after(sample, header_index, expected_columns):
            return 0

        following_data_score = self._following_data_score(sample, header_index, expected_columns)
        score = len(header_texts) * 2
        score += len(known_words) * 10
        score += following_data_score

        if not known_words and following_data_score == 0:
            return 0
        return score

    def _has_data_after(
        self,
        sample: list[tuple[int, tuple[object, ...]]],
        header_index: int,
        expected_columns: int,
    ) -> bool:
        for _, raw_values in sample[header_index + 1 :]:
            values = [self._to_text(value) for value in raw_values[:expected_columns]]
            if sum(1 for value in values if value) >= 1:
                return True
        return True

    def _following_data_score(
        self,
        sample: list[tuple[int, tuple[object, ...]]],
        header_index: int,
        expected_columns: int,
    ) -> int:
        score = 0
        for _, raw_values in sample[header_index + 1 : header_index + 4]:
            values = [self._to_text(value) for value in raw_values[:expected_columns]]
            filled_values = sum(1 for value in values if value)
            if filled_values >= 2:
                score += 3
            elif filled_values == 1:
                score += 1
        return score

    def _raw_text_values(self, raw_values: tuple[object, ...]) -> list[str]:
        return [text for text in (self._to_text(value) for value in raw_values) if text]

    def _row_to_dict(
        self,
        columns: list[str],
        raw_values: tuple[object, ...],
    ) -> dict[str, str]:
        values: dict[str, str] = {}
        for index, column in enumerate(columns):
            raw_value = raw_values[index] if index < len(raw_values) else None
            values[column] = self._to_text(raw_value)
        return values

    def _normalize_headers(self, raw_headers: tuple[object, ...]) -> list[str]:
        headers: list[str] = []
        seen: dict[str, int] = {}
        trimmed_headers = self._trim_trailing_empty(raw_headers)

        for index, raw_header in enumerate(trimmed_headers, start=1):
            header = self._to_text(raw_header) or f"Coluna {index}"
            count = seen.get(header, 0) + 1
            seen[header] = count
            if count > 1:
                header = f"{header} {count}"
            headers.append(header)

        return headers

    def _trim_trailing_empty(self, raw_values: tuple[object, ...]) -> tuple[object, ...]:
        values = list(raw_values)
        while values and not self._to_text(values[-1]):
            values.pop()
        return tuple(values)

    def _to_text(self, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, date):
            return value.isoformat()
        return str(value).strip()

    def _known_words_in_headers(self, headers: list[str], known_words: set[str]) -> set[str]:
        normalized_words = {self._normalize_match_text(word) for word in known_words}
        matches: set[str] = set()
        for header in headers:
            normalized_header = self._normalize_match_text(header)
            for word in normalized_words:
                if word and word in normalized_header:
                    matches.add(word)
        return matches

    def _normalize_match_text(self, value: str) -> str:
        normalized = normalize("NFD", value.casefold())
        return "".join(character for character in normalized if not combining(character))
