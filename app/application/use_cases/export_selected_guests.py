from collections.abc import Iterable, Sequence
from pathlib import Path
import re
from unicodedata import combining, normalize

from app.application.dtos.guest_dto import ImportResultDTO
from app.application.services.contact_data_cleaner import ContactDataCleaner
from app.domain.entities.guest_record import GuestRecord
from app.domain.repositories.guest_repository import GuestRepository
from app.domain.repositories.selected_guests_exporter import SelectedGuestsExporter


EXPORT_MODE_COMPLETE = "complete"
EXPORT_MODE_NAMES = "names"
EXPORT_MODE_CATEGORY = "category"
EXPORT_SCOPE_FINAL = "final"
EXPORT_SCOPE_UNIFIED = "unified"
EXPORT_FORMAT_XLSX = "xlsx"
EXPORT_FORMAT_PDF = "pdf"
NAME_HEADER_WORDS = {
    "nome",
    "name",
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
CATEGORY_HEADER_WORDS = {"categoria", "category", "grupo", "group", "tipo", "classificacao", "classificação"}
TREATMENT_HEADER_WORDS = {
    "tratamento",
    "titulo",
    "título",
    "pronome",
    "saudacao",
    "saudação",
}
GENDER_HEADER_WORDS = {"sexo", "genero", "gênero"}
UNKNOWN_HONORIFIC = "SR(a)."
MALE_HONORIFIC = "SR."
FEMALE_HONORIFIC = "SRA."
COUPLE_HONORIFIC = "SR. E SRA."
MALE_FIRST_NAMES = {
    "adalberto",
    "ademar",
    "adriano",
    "afonso",
    "agostinho",
    "alberto",
    "alex",
    "alexandre",
    "alfredo",
    "alvaro",
    "amadeu",
    "americo",
    "andre",
    "angelo",
    "antonio",
    "ari",
    "arthur",
    "benicio",
    "bernardo",
    "bruno",
    "caio",
    "carlos",
    "cicero",
    "claudio",
    "daniel",
    "davi",
    "diego",
    "diogo",
    "eduardo",
    "emerson",
    "enrico",
    "evandro",
    "fabio",
    "felipe",
    "fernando",
    "francisco",
    "gabriel",
    "george",
    "gilberto",
    "guilherme",
    "gustavo",
    "henrique",
    "hugo",
    "igor",
    "joao",
    "jorge",
    "jose",
    "julio",
    "leandro",
    "leonardo",
    "lucas",
    "luiz",
    "marcelo",
    "marcio",
    "marcos",
    "mateus",
    "miguel",
    "nelson",
    "paulo",
    "pedro",
    "rafael",
    "renato",
    "ricardo",
    "roberto",
    "rodrigo",
    "ronaldo",
    "sergio",
    "thiago",
    "vitor",
    "victor",
    "vinicius",
}
FEMALE_FIRST_NAMES = {
    "adriana",
    "aline",
    "amanda",
    "ana",
    "andrea",
    "angela",
    "antonia",
    "barbara",
    "beatriz",
    "bruna",
    "camila",
    "carla",
    "carolina",
    "cecilia",
    "clara",
    "claudia",
    "cristina",
    "daniela",
    "debora",
    "elaine",
    "eliana",
    "elisangela",
    "eloisa",
    "fernanda",
    "flavia",
    "gabriela",
    "helena",
    "isabel",
    "jessica",
    "joana",
    "julia",
    "juliana",
    "larissa",
    "leticia",
    "luciana",
    "luiza",
    "manuela",
    "marcia",
    "maria",
    "mariana",
    "monica",
    "nara",
    "natalia",
    "patricia",
    "paula",
    "raquel",
    "renata",
    "rita",
    "sandra",
    "simone",
    "sonia",
    "tatiana",
    "teresa",
    "vanessa",
    "veronica",
}


class ExportSelectedGuestsUseCase:
    def __init__(
        self,
        guest_repository: GuestRepository,
        exporter: SelectedGuestsExporter,
    ) -> None:
        self._guest_repository = guest_repository
        self._exporter = exporter

    def execute(
        self,
        import_id: int | None,
        output_path: str,
        workbook_id: int | None = None,
        export_mode: str = EXPORT_MODE_COMPLETE,
        export_scope: str = EXPORT_SCOPE_FINAL,
        export_format: str = EXPORT_FORMAT_XLSX,
    ) -> ImportResultDTO:
        imported_file = self._guest_repository.get_import(import_id) if import_id is not None else None
        if import_id is not None and imported_file is None:
            raise ValueError("Importação não encontrada.")

        clean_export_format = str(export_format).strip().lower()
        if clean_export_format not in {EXPORT_FORMAT_XLSX, EXPORT_FORMAT_PDF}:
            raise ValueError("Formato de exportação inválido.")

        if export_scope == EXPORT_SCOPE_UNIFIED:
            export_count = self._guest_repository.count_guests(import_id, workbook_id)
            if export_count == 0:
                raise ValueError("Nenhum registro na Lista unificada para exportar.")
        else:
            export_count = self._guest_repository.count_automatic_guests(import_id, workbook_id)
            if export_count == 0:
                raise ValueError("Nenhum convidado selecionado para exportar.")

        path = Path(output_path)
        expected_suffix = ".pdf" if clean_export_format == EXPORT_FORMAT_PDF else ".xlsx"
        if path.suffix.lower() != expected_suffix:
            path = path.with_suffix(expected_suffix)

        columns = self._guest_repository.get_columns(import_id, workbook_id)
        export_columns = columns if import_id is not None else ("Lista", *columns)
        if export_scope == EXPORT_SCOPE_UNIFIED:
            guests = self._guest_repository.iter_guests(import_id, workbook_id)
        else:
            guests = self._guest_repository.iter_automatic_guests(import_id, workbook_id)
        guests = self._clean_guests(guests, columns)

        if clean_export_format == EXPORT_FORMAT_PDF:
            name_columns = self._find_name_columns(columns)
            if not name_columns:
                raise ValueError("Nenhuma coluna de nome foi encontrada para exportar em PDF.")
            treatment_columns = self._find_columns(columns, TREATMENT_HEADER_WORDS)
            gender_columns = self._find_columns(columns, GENDER_HEADER_WORDS)
            export_columns = ("Nome",)
            sheet_name = "Nomes"
            exported_count = self._exporter.export_name_checklist_pdf(
                str(path),
                self._with_pdf_name_column(guests, name_columns, treatment_columns, gender_columns),
                title=self._pdf_title(export_scope),
            )
            if exported_count == 0:
                raise ValueError("Nenhum nome preenchido foi encontrado para exportar em PDF.")
        elif export_mode == EXPORT_MODE_NAMES:
            name_columns = self._find_name_columns(columns)
            if not name_columns:
                raise ValueError("Nenhuma coluna de nome foi encontrada para exportar.")
            export_columns = ("Nome",)
            exported_count = self._exporter.export(
                str(path),
                export_columns,
                self._with_name_column(guests, name_columns),
                sheet_name="Nomes",
            )
            sheet_name = "Nomes"
        else:
            if import_id is None:
                guests = self._with_list_column(guests)

            if export_mode == EXPORT_MODE_CATEGORY:
                category_column = self._find_column(columns, CATEGORY_HEADER_WORDS)
                if category_column is None:
                    raise ValueError("Nenhuma coluna de categoria foi encontrada para exportar.")
                exported_count = self._exporter.export_by_category(
                    str(path),
                    export_columns,
                    guests,
                    category_column,
                )
                sheet_name = "Por categoria"
            else:
                if imported_file is not None:
                    sheet_name = imported_file.sheet_name
                elif export_scope == EXPORT_SCOPE_UNIFIED:
                    sheet_name = "Lista unificada"
                else:
                    sheet_name = "Selecionados"
                exported_count = self._exporter.export(str(path), export_columns, guests, sheet_name=sheet_name)

        return ImportResultDTO(
            import_id=imported_file.id if imported_file is not None else 0,
            workbook_id=imported_file.workbook_id if imported_file is not None else workbook_id or 0,
            file_name=path.name,
            sheet_name=sheet_name,
            total_rows=exported_count,
            columns=export_columns,
            is_selectable=True,
        )

    def _with_list_column(self, guests: Iterable[GuestRecord]) -> Iterable[GuestRecord]:
        for guest in guests:
            yield GuestRecord(
                id=guest.id,
                import_id=guest.import_id,
                sheet_name=guest.sheet_name,
                row_number=guest.row_number,
                verification_code=guest.verification_code,
                data={"Lista": guest.sheet_name, **guest.data},
                selected=guest.selected,
            )

    def _with_name_column(
        self,
        guests: Iterable[GuestRecord],
        name_columns: Sequence[str],
    ) -> Iterable[GuestRecord]:
        for guest in guests:
            yield GuestRecord(
                id=guest.id,
                import_id=guest.import_id,
                sheet_name=guest.sheet_name,
                row_number=guest.row_number,
                verification_code=guest.verification_code,
                data={"Nome": self._guest_name_value(guest.data, name_columns)},
                selected=guest.selected,
            )

    def _with_pdf_name_column(
        self,
        guests: Iterable[GuestRecord],
        name_columns: Sequence[str],
        treatment_columns: Sequence[str],
        gender_columns: Sequence[str],
    ) -> Iterable[GuestRecord]:
        for guest in guests:
            name = self._guest_name_value(guest.data, name_columns)
            honorific = self._guest_honorific_value(guest.data, treatment_columns, gender_columns, name)
            display_name = f"{honorific} {name}".strip().upper()
            yield GuestRecord(
                id=guest.id,
                import_id=guest.import_id,
                sheet_name=guest.sheet_name,
                row_number=guest.row_number,
                verification_code=guest.verification_code,
                data={"Nome": display_name},
                selected=guest.selected,
            )

    def _clean_guests(
        self,
        guests: Iterable[GuestRecord],
        columns: tuple[str, ...],
    ) -> Iterable[GuestRecord]:
        cleaner = ContactDataCleaner(columns)
        for guest in guests:
            yield GuestRecord(
                id=guest.id,
                import_id=guest.import_id,
                sheet_name=guest.sheet_name,
                row_number=guest.row_number,
                verification_code=guest.verification_code,
                data=cleaner.clean_values(guest.data),
                selected=guest.selected,
            )

    def _find_column(self, columns: tuple[str, ...], header_words: set[str]) -> str | None:
        normalized_words = {self._normalize_match_text(word) for word in header_words}
        for column in columns:
            normalized_column = self._normalize_match_text(column)
            if any(word and word in normalized_column for word in normalized_words):
                return column
        return None

    def _find_columns(self, columns: tuple[str, ...], header_words: set[str]) -> tuple[str, ...]:
        normalized_words = {self._normalize_match_text(word) for word in header_words}
        found_columns: list[str] = []
        for column in columns:
            normalized_column = self._normalize_match_text(column)
            if any(word and word in normalized_column for word in normalized_words):
                found_columns.append(column)
        return tuple(found_columns)

    def _find_name_columns(self, columns: tuple[str, ...]) -> tuple[str, ...]:
        scored_columns: list[tuple[int, int, str]] = []
        for index, column in enumerate(columns):
            score = self._name_column_score(column)
            if score > 0:
                scored_columns.append((-score, index, column))
        scored_columns.sort()
        return tuple(column for _, _, column in scored_columns)

    def _name_column_score(self, column: str) -> int:
        normalized_column = self._normalize_match_text(column)
        tokens = [token for token in re.split(r"[^a-z0-9]+", normalized_column) if token]
        exact_words = {self._normalize_match_text(word) for word in NAME_HEADER_WORDS}

        if normalized_column in exact_words:
            return 100
        if "nome" in tokens or "name" in tokens:
            return 90
        if any(word in tokens for word in {"convidado", "convidados", "pessoa", "pessoas"}):
            return 80
        if any(word in tokens for word in {"cliente", "clientes", "participante", "participantes"}):
            return 70
        if any(word in tokens for word in {"destinatario", "destinatarios"}):
            return 70
        return 0

    def _guest_name_value(self, data: dict[str, str], name_columns: Sequence[str]) -> str:
        for column in name_columns:
            for item in str(data.get(column, "")).splitlines():
                clean_item = item.strip()
                if clean_item:
                    return clean_item
        return ""

    def _guest_honorific_value(
        self,
        data: dict[str, str],
        treatment_columns: Sequence[str],
        gender_columns: Sequence[str],
        name: str,
    ) -> str:
        for column in treatment_columns:
            honorific = self._normalize_honorific(data.get(column, ""))
            if honorific:
                return honorific

        for column in gender_columns:
            honorific = self._honorific_from_gender(data.get(column, ""))
            if honorific:
                return honorific

        return self._infer_honorific_from_name(name)

    def _normalize_honorific(self, value: object) -> str:
        normalized_value = self._normalize_match_text(str(value or ""))
        if not normalized_value:
            return ""
        tokens = set(re.findall(r"[a-z0-9]+", normalized_value))
        has_couple = "casal" in tokens
        has_female = "sra" in tokens or "senhora" in tokens
        has_male = "sr" in tokens or "senhor" in tokens
        if has_couple or (has_male and has_female):
            return COUPLE_HONORIFIC
        if has_female:
            return FEMALE_HONORIFIC
        if has_male:
            return MALE_HONORIFIC
        return ""

    def _honorific_from_gender(self, value: object) -> str:
        normalized_value = self._normalize_match_text(str(value or ""))
        if normalized_value in {"f", "fem", "feminino", "mulher"}:
            return FEMALE_HONORIFIC
        if normalized_value in {"m", "masc", "masculino", "homem"}:
            return MALE_HONORIFIC
        return ""

    def _infer_honorific_from_name(self, name: str) -> str:
        first_name = self._first_name(name)
        if not first_name:
            return UNKNOWN_HONORIFIC
        if first_name in FEMALE_FIRST_NAMES:
            return FEMALE_HONORIFIC
        if first_name in MALE_FIRST_NAMES:
            return MALE_HONORIFIC
        if first_name.endswith(("ana", "ela", "ia", "ina", "isa", "ise", "ita")):
            return FEMALE_HONORIFIC
        if first_name.endswith(("o", "os", "el", "son", "ton", "do", "io")):
            return MALE_HONORIFIC
        return UNKNOWN_HONORIFIC

    def _first_name(self, name: str) -> str:
        tokens = re.findall(r"[A-Za-zÀ-ÿ]+", str(name))
        ignored_tokens = {"sr", "sra", "senhor", "senhora", "dr", "dra", "prof", "profa"}
        for token in tokens:
            normalized_token = self._normalize_match_text(token)
            if normalized_token and normalized_token not in ignored_tokens:
                return normalized_token
        return ""

    def _pdf_title(self, export_scope: str) -> str:
        if export_scope == EXPORT_SCOPE_UNIFIED:
            return "Lista unificada - conferência de presença"
        return "Lista final - conferência de presença"

    def _normalize_match_text(self, value: str) -> str:
        normalized = normalize("NFD", str(value).casefold())
        return "".join(character for character in normalized if not combining(character))
