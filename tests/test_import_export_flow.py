from pathlib import Path
import tempfile
import unittest

from openpyxl import Workbook, load_workbook

from app.application.use_cases.export_selected_guests import ExportSelectedGuestsUseCase
from app.application.use_cases.import_spreadsheet import ImportSpreadsheetUseCase
from app.application.use_cases.list_guests import ListGuestsUseCase
from app.application.use_cases.update_guest_selection import UpdateGuestSelectionUseCase
from app.infrastructure.repositories.sqlite_guest_repository import SqliteGuestRepository
from app.infrastructure.spreadsheet.openpyxl_exporter import OpenpyxlSelectedGuestsExporter
from app.infrastructure.spreadsheet.openpyxl_reader import OpenpyxlSpreadsheetReader


class ImportExportFlowTest(unittest.TestCase):
    def test_import_workbook_select_and_export_automatic_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            spreadsheet_path = temp_path / "mala_direta.xlsx"
            database_path = temp_path / "mala_direta.sqlite3"
            export_path = temp_path / "selecionados.xlsx"

            self._create_workbook(spreadsheet_path)

            repository = SqliteGuestRepository(database_path)
            repository.initialize()
            reader = OpenpyxlSpreadsheetReader()
            exporter = OpenpyxlSelectedGuestsExporter()

            import_result = ImportSpreadsheetUseCase(
                guest_repository=repository,
                spreadsheet_reader=reader,
                batch_size=2,
            ).execute_workbook(str(spreadsheet_path))

            self.assertEqual(import_result.total_rows, 4)
            self.assertEqual(len(import_result.imported_sheets), 2)
            self.assertEqual(import_result.skipped_sheets, ("Resumo",))

            all_page = ListGuestsUseCase(repository).execute(
                import_id=None,
                page=0,
                page_size=50,
            )

            self.assertEqual(all_page.total_rows, 4)
            self.assertEqual(all_page.columns, ("Lista", "Nome", "Endereço", "Telefone", "Obra / Universo"))
            self.assertEqual(all_page.rows[0].data["Lista"], "Amigos")

            selection_use_case = UpdateGuestSelectionUseCase(repository)
            updated_rows = selection_use_case.set_all_filtered_selected(
                import_id=None,
                selected=True,
                search="Friends",
            )
            self.assertEqual(updated_rows, 2)

            amigos_import_id = import_result.imported_sheets[0].import_id
            cleared_rows = selection_use_case.set_all_filtered_selected(
                import_id=amigos_import_id,
                selected=False,
                search="Monica",
            )
            self.assertEqual(cleared_rows, 1)

            selection_use_case.set_guest_selected(
                guest_id=all_page.rows[1].id,
                selected=True,
            )
            selection_use_case.set_guest_selected(
                guest_id=all_page.rows[2].id,
                selected=True,
            )

            selected_page = ListGuestsUseCase(repository).execute(
                import_id=None,
                page=0,
                page_size=50,
                selected_only=True,
            )

            self.assertEqual(selected_page.total_rows, 3)
            self.assertEqual(selected_page.columns, ("Lista", "Nome", "Endereço", "Telefone", "Obra / Universo"))

            export_result = ExportSelectedGuestsUseCase(
                guest_repository=repository,
                exporter=exporter,
            ).execute(None, str(export_path))

            self.assertEqual(export_result.total_rows, 3)
            self.assertTrue(export_path.exists())
            self._assert_exported_content(export_path)

    def _create_workbook(self, path: Path) -> None:
        workbook = Workbook()
        summary = workbook.active
        summary.title = "Resumo"
        summary.append(["Lista", "Total"])
        summary.append(["Amigos", 2])
        summary.append(["Políticos", 2])

        self._append_contact_sheet(
            workbook,
            "Amigos",
            [
                ["Chandler Bing", "Rua da Comédia, 101", "(00) 90000-0001", "Friends"],
                ["Monica Geller", "Rua do Café, 303", "(00) 90000-0003", "Friends"],
            ],
        )
        self._append_contact_sheet(
            workbook,
            "Políticos",
            [
                ["Ada Lovelace", "Rua Analítica, 1843", "(00) 91000-0001", "Computação"],
                ["Machado de Assis", "Rua Cosme Velho, 18", "(00) 91000-0002", "Literatura"],
            ],
        )

        workbook.save(path)
        workbook.close()

    def _append_contact_sheet(
        self,
        workbook: Workbook,
        sheet_name: str,
        rows: list[list[str]],
    ) -> None:
        worksheet = workbook.create_sheet(sheet_name)
        worksheet.append([f"Contatos fictícios — {sheet_name}", None, None, None])
        worksheet.merge_cells("A1:D1")
        worksheet.append(["Todos os nomes, endereços e telefones desta aba são fictícios.", None, None, None])
        worksheet.append(["Nome", "Endereço", "Telefone", "Obra / Universo"])
        for row in rows:
            worksheet.append(row)

    def _assert_exported_content(self, path: Path) -> None:
        workbook = load_workbook(path, read_only=True)
        try:
            worksheet = workbook["Selecionados"]
            rows = list(worksheet.iter_rows(values_only=True))
        finally:
            workbook.close()

        self.assertEqual(rows[0], ("Lista", "Nome", "Endereço", "Telefone", "Obra / Universo"))
        self.assertEqual(rows[1], ("Amigos", "Chandler Bing", "Rua da Comédia, 101", "(00) 90000-0001", "Friends"))
        self.assertEqual(rows[2], ("Amigos", "Monica Geller", "Rua do Café, 303", "(00) 90000-0003", "Friends"))
        self.assertEqual(rows[3], ("Políticos", "Ada Lovelace", "Rua Analítica, 1843", "(00) 91000-0001", "Computação"))
        self.assertEqual(len(rows), 4)


if __name__ == "__main__":
    unittest.main()
