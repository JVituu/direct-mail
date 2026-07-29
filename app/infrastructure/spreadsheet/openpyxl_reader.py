from collections.abc import Iterable
from datetime import date, datetime

from openpyxl import load_workbook

from app.domain.value_objects.spreadsheet_row import SpreadsheetRow


class OpenpyxlSpreadsheetReader:
    _MAX_HEADER_SCAN_ROWS = 40
    _KNOWN_HEADER_WORDS = {
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

        for index, (row_number, raw_values) in enumerate(sample):
            headers = self._normalize_headers(raw_values)
            non_empty_headers = [header for header in headers if header]
            if len(non_empty_headers) < 2:
                continue
            if not self._looks_like_header(non_empty_headers):
                continue
            if not self._has_data_after(sample, index, len(headers)):
                continue
            return row_number, headers

        return None

    def _looks_like_header(self, headers: list[str]) -> bool:
        normalized_headers = {header.casefold() for header in headers}
        if normalized_headers.intersection(self._KNOWN_HEADER_WORDS):
            return True
        if any(len(header) > 60 for header in headers):
            return False
        return len(headers) >= 2

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
