from collections.abc import Sequence
import re
from unicodedata import combining, normalize

from app.domain.value_objects.spreadsheet_row import SpreadsheetRow


class ContactDataCleaner:
    _EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
    _CEP_PATTERN = re.compile(r"(?<!\d)\d{5}-?\d{3}(?!\d)")
    _FORMATTED_CEP_PATTERN = re.compile(r"(?<!\d)\d{5}-\d{3}(?!\d)")
    _PHONE_PATTERN = re.compile(
        r"(?<!\d)(?:\+?55\s*)?(?:\(?\d{2}\)?[\s.-]*)?(?:9[\s.-]*)?\d{4}[\s.-]?\d{4}(?!\d)"
    )
    _COLUMN_WORDS = {
        "email": ("email", "e-mail", "mail"),
        "mobile": ("celular", "whatsapp", "mobile", "cell"),
        "phone": ("telefone", "phone", "fone", "tel"),
        "cep": ("cep", "codigo postal", "postal code", "zip"),
        "address": ("endereco", "address", "logradouro", "rua", "avenida", "av"),
        "building": ("edificio", "edificio", "edif", "predio", "condominio", "residencial"),
        "state": ("estado", "uf"),
    }
    _ADDRESS_WORDS = (
        "alameda",
        "avenida",
        "av",
        "estrada",
        "largo",
        "praca",
        "rodovia",
        "rua",
        "travessa",
    )
    _BUILDING_WORDS = ("ed", "edf", "edificio", "condominio", "residencial", "empresarial")
    _STATE_VALUES = {
        "ac",
        "al",
        "ap",
        "am",
        "ba",
        "ce",
        "df",
        "es",
        "go",
        "ma",
        "mt",
        "ms",
        "mg",
        "pa",
        "pb",
        "pr",
        "pe",
        "pi",
        "rj",
        "rn",
        "rs",
        "ro",
        "rr",
        "sc",
        "sp",
        "se",
        "to",
        "acre",
        "alagoas",
        "amapa",
        "amazonas",
        "bahia",
        "ceara",
        "distrito federal",
        "espirito santo",
        "goias",
        "maranhao",
        "mato grosso",
        "mato grosso do sul",
        "minas gerais",
        "para",
        "paraiba",
        "parana",
        "pernambuco",
        "piaui",
        "rio de janeiro",
        "rio grande do norte",
        "rio grande do sul",
        "rondonia",
        "roraima",
        "santa catarina",
        "sao paulo",
        "sergipe",
        "tocantins",
    }

    def __init__(self, columns: Sequence[str]) -> None:
        self._columns = tuple(columns)
        self._column_kinds = {column: self._column_kind(column) for column in self._columns}
        self._targets = {
            "email": self._first_column("email"),
            "mobile": self._first_column("mobile"),
            "phone": self._first_column("phone"),
            "cep": self._first_column("cep"),
            "address": self._first_column("address"),
            "building": self._first_column("building"),
            "state": self._first_column("state"),
        }

    def clean_row(self, row: SpreadsheetRow) -> SpreadsheetRow:
        return SpreadsheetRow(row_number=row.row_number, values=self.clean_values(row.values))

    def clean_values(self, values: dict[str, str]) -> dict[str, str]:
        cleaned = {column: str(values.get(column, "")).strip() for column in self._columns}
        for column in self._columns:
            original_value = cleaned.get(column, "")
            if not original_value:
                continue

            residual_value = original_value
            residual_value = self._move_emails(cleaned, column, residual_value)
            residual_value = self._move_ceps(cleaned, column, residual_value)
            residual_value = self._move_phones(cleaned, column, residual_value)
            residual_value = self._move_address_like_values(cleaned, column, residual_value)
            cleaned[column] = self._clean_residual(residual_value)

        self._normalize_contact_targets(cleaned)
        return cleaned

    def _move_emails(self, cleaned: dict[str, str], column: str, value: str) -> str:
        target = self._targets["email"]
        if target is None or target == column:
            return value

        residual = value
        for email in self._EMAIL_PATTERN.findall(value):
            self._append_value(cleaned, target, email, "email")
            residual = self._remove_token(residual, email)
        return residual

    def _move_ceps(self, cleaned: dict[str, str], column: str, value: str) -> str:
        target = self._targets["cep"]
        if target is None or target == column:
            return value
        if self._column_kinds.get(column) in {"phone", "mobile"} or self._looks_like_contact_column(column):
            return value

        residual = value
        for cep in self._CEP_PATTERN.findall(value):
            self._append_value(cleaned, target, cep, "digits")
            residual = self._remove_token(residual, cep)
        return residual

    def _move_phones(self, cleaned: dict[str, str], column: str, value: str) -> str:
        residual = value
        for phone in self._PHONE_PATTERN.findall(value):
            if self._column_kinds.get(column) == "cep" and self._CEP_PATTERN.fullmatch(phone):
                continue
            phone_kind = self._phone_kind(phone)
            target = self._phone_target(phone_kind)
            if target is None or target == column:
                continue

            self._append_value(cleaned, target, phone, "digits")
            residual = self._remove_token(residual, phone)
        return residual

    def _move_address_like_values(self, cleaned: dict[str, str], column: str, value: str) -> str:
        if not value:
            return value

        target_kind = ""
        target = None
        if self._looks_like_address(value):
            target_kind = "address"
            target = self._targets["address"]
        elif self._looks_like_building(value):
            target_kind = "building"
            target = self._targets["building"]
        elif self._looks_like_state(value):
            target_kind = "state"
            target = self._targets["state"]

        if target is None or target == column or self._column_kinds.get(column) == target_kind:
            return value

        self._append_value(cleaned, target, value, "text")
        return ""

    def _phone_target(self, phone_kind: str) -> str | None:
        if phone_kind == "mobile":
            return self._targets["mobile"] or self._targets["phone"]
        return self._targets["phone"] or self._targets["mobile"]

    def _phone_kind(self, value: str) -> str:
        digits = self._phone_digits(value)
        local_number = digits[-9:] if len(digits) in (9, 11) else digits[-8:]
        if len(local_number) == 9 and local_number.startswith("9"):
            return "mobile"
        if len(local_number) == 8 and local_number.startswith(("7", "8", "9")):
            return "mobile"
        return "phone"

    def _phone_digits(self, value: str) -> str:
        digits = re.sub(r"\D+", "", value)
        if digits.startswith("55") and len(digits) > 11:
            return digits[2:]
        return digits

    def _append_value(
        self,
        cleaned: dict[str, str],
        column: str,
        value: str,
        comparison: str,
    ) -> None:
        value = self._clean_residual(value)
        if not value:
            return

        current_values = self._split_values(cleaned.get(column, ""))
        if any(self._same_value(existing, value, comparison) for existing in current_values):
            return
        current_values.append(value)
        cleaned[column] = "\n".join(current_values)

    def _normalize_contact_targets(self, cleaned: dict[str, str]) -> None:
        self._normalize_email_target(cleaned)
        self._normalize_cep_target(cleaned)
        self._normalize_phone_target(cleaned, "phone")
        self._normalize_phone_target(cleaned, "mobile")

    def _normalize_email_target(self, cleaned: dict[str, str]) -> None:
        target = self._targets["email"]
        if target is None:
            return

        emails: list[str] = []
        for email in self._EMAIL_PATTERN.findall(cleaned.get(target, "")):
            self._append_clean_value(emails, email, "email")
        cleaned[target] = "\n".join(emails)

    def _normalize_cep_target(self, cleaned: dict[str, str]) -> None:
        target = self._targets["cep"]
        if target is None:
            return

        raw_value = cleaned.get(target, "")
        if not raw_value:
            return

        formatted_ceps = self._FORMATTED_CEP_PATTERN.findall(raw_value)
        all_ceps = self._CEP_PATTERN.findall(raw_value)
        kept_ceps: list[str] = []
        for cep in formatted_ceps:
            self._append_clean_value(kept_ceps, cep, "digits")
        if not kept_ceps and all_ceps:
            self._append_clean_value(kept_ceps, all_ceps[0], "digits")

        kept_cep_digits = {re.sub(r"\D+", "", cep) for cep in kept_ceps}
        for phone in self._PHONE_PATTERN.findall(raw_value):
            if re.sub(r"\D+", "", phone) in kept_cep_digits:
                continue
            target_column = self._phone_target(self._phone_kind(phone))
            if target_column is not None:
                self._append_value(cleaned, target_column, phone, "digits")

        cleaned[target] = "\n".join(kept_ceps)

    def _normalize_phone_target(self, cleaned: dict[str, str], expected_kind: str) -> None:
        target = self._targets["mobile"] if expected_kind == "mobile" else self._targets["phone"]
        if target is None:
            return

        phones: list[str] = []
        raw_value = cleaned.get(target, "")
        for cep in self._FORMATTED_CEP_PATTERN.findall(raw_value):
            cep_target = self._targets["cep"]
            if cep_target is not None:
                self._append_value(cleaned, cep_target, cep, "digits")

        for phone in self._PHONE_PATTERN.findall(raw_value):
            if self._FORMATTED_CEP_PATTERN.fullmatch(phone):
                continue
            phone_kind = self._phone_kind(phone)
            target_column = self._phone_target(phone_kind)
            if phone_kind == expected_kind or target_column == target:
                self._append_clean_value(phones, phone, "digits")
                continue

            if target_column is not None and target_column != target:
                self._append_value(cleaned, target_column, phone, "digits")

        cleaned[target] = "\n".join(phones)

    def _append_clean_value(self, values: list[str], value: str, comparison: str) -> None:
        value = self._clean_residual(value)
        if not value:
            return
        if any(self._same_value(existing, value, comparison) for existing in values):
            return
        values.append(value)

    def _same_value(self, left: str, right: str, comparison: str) -> bool:
        if comparison == "digits":
            return re.sub(r"\D+", "", left) == re.sub(r"\D+", "", right)
        if comparison == "email":
            return left.strip().casefold() == right.strip().casefold()
        return self._normalize_text(left) == self._normalize_text(right)

    def _split_values(self, value: str) -> list[str]:
        return [
            item.strip()
            for item in re.split(r"[\n;]+", value)
            if item.strip()
        ]

    def _remove_token(self, value: str, token: str) -> str:
        updated = value.replace(token, " ")
        return self._clean_residual(updated)

    def _clean_residual(self, value: str) -> str:
        return re.sub(r"\s{2,}", " ", str(value).strip(" \t\r\n;|,/"))

    def _looks_like_address(self, value: str) -> bool:
        normalized = self._normalize_text(value)
        tokens = normalized.replace(".", " ").replace(",", " ").split()
        return any(word in tokens for word in self._ADDRESS_WORDS) and any(character.isdigit() for character in value)

    def _looks_like_building(self, value: str) -> bool:
        normalized = self._normalize_text(value)
        tokens = normalized.replace(".", " ").replace(",", " ").split()
        return any(word in tokens or normalized.startswith(f"{word} ") for word in self._BUILDING_WORDS)

    def _looks_like_state(self, value: str) -> bool:
        normalized = self._normalize_text(value)
        return normalized in self._STATE_VALUES

    def _first_column(self, kind: str) -> str | None:
        for column, column_kind in self._column_kinds.items():
            if column_kind == kind:
                return column
        return None

    def _column_kind(self, column_name: str) -> str:
        normalized_column = self._normalize_text(column_name)
        for kind, words in self._COLUMN_WORDS.items():
            if any(word and word in normalized_column for word in words):
                return kind
        return "other"

    def _looks_like_contact_column(self, column_name: str) -> bool:
        normalized_column = self._normalize_text(column_name)
        return "contato" in normalized_column or "contact" in normalized_column

    def _normalize_text(self, value: str) -> str:
        normalized = normalize("NFD", str(value).casefold())
        return "".join(character for character in normalized if not combining(character))
