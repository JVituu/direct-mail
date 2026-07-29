from pathlib import Path
import tempfile
import unittest

from openpyxl import Workbook, load_workbook

from app.application.use_cases.export_selected_guests import ExportSelectedGuestsUseCase
from app.application.use_cases.import_spreadsheet import ImportSpreadsheetUseCase
from app.application.use_cases.list_guests import ListGuestsUseCase
from app.application.use_cases.manage_automatic_sheet import ManageAutomaticSheetUseCase
from app.application.use_cases.review_duplicate_selection import ReviewDuplicateSelectionUseCase
from app.application.use_cases.update_guest_data import UpdateGuestDataUseCase
from app.application.use_cases.update_guest_selection import UpdateGuestSelectionUseCase
from app.infrastructure.repositories.sqlite_guest_repository import SqliteGuestRepository
from app.infrastructure.spreadsheet.openpyxl_exporter import OpenpyxlSelectedGuestsExporter
from app.infrastructure.spreadsheet.openpyxl_reader import OpenpyxlSpreadsheetReader


class ImportExportFlowTest(unittest.TestCase):
    def test_detects_duplicates_across_workbooks_by_normalized_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            first_spreadsheet = temp_path / "lista_a.xlsx"
            second_spreadsheet = temp_path / "lista_b.xlsx"
            database_path = temp_path / "mala_direta.sqlite3"

            self._create_single_contact_workbook(first_spreadsheet, "Amigos", "José da Silva", "(00) 90000-0000")
            self._create_single_contact_workbook(second_spreadsheet, "Políticos", "Jose Silva", "(00) 91111-1111")

            repository = SqliteGuestRepository(database_path)
            repository.initialize()
            reader = OpenpyxlSpreadsheetReader()
            import_use_case = ImportSpreadsheetUseCase(repository, reader)

            first_import = import_use_case.execute_workbook(str(first_spreadsheet))
            second_import = import_use_case.execute_workbook(str(second_spreadsheet))

            duplicates_page = ListGuestsUseCase(repository).execute(
                import_id=None,
                workbook_id=None,
                page=0,
                page_size=50,
                duplicates_only=True,
            )

            self.assertEqual(duplicates_page.total_rows, 2)
            self.assertEqual({row.duplicate_reason for row in duplicates_page.rows}, {"Nome"})
            self.assertEqual({row.duplicate_count for row in duplicates_page.rows}, {2})

            first_page = ListGuestsUseCase(repository).execute(
                import_id=first_import.imported_sheets[0].import_id,
                workbook_id=first_import.workbook_id,
                page=0,
                page_size=50,
            )
            second_page = ListGuestsUseCase(repository).execute(
                import_id=second_import.imported_sheets[0].import_id,
                workbook_id=second_import.workbook_id,
                page=0,
                page_size=50,
            )

            self.assertEqual(first_page.rows[0].duplicate_reason, "Nome")
            self.assertEqual(first_page.rows[0].duplicate_count, 2)
            self.assertEqual(second_page.rows[0].duplicate_reason, "Nome")
            self.assertEqual(second_page.rows[0].duplicate_count, 2)

            review_use_case = ReviewDuplicateSelectionUseCase(repository)
            candidates = review_use_case.list_duplicate_candidates(first_page.rows[0].id)
            self.assertEqual({candidate.id for candidate in candidates}, {first_page.rows[0].id, second_page.rows[0].id})

            UpdateGuestSelectionUseCase(repository).set_guest_selected(first_page.rows[0].id, True)
            automatic_conflicts = review_use_case.list_automatic_conflicts(second_page.rows[0].id)
            self.assertEqual([conflict.id for conflict in automatic_conflicts], [first_page.rows[0].id])

    def test_ignores_weak_single_token_duplicate_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            first_spreadsheet = temp_path / "lista_a.xlsx"
            second_spreadsheet = temp_path / "lista_b.xlsx"
            database_path = temp_path / "mala_direta.sqlite3"

            self._create_single_contact_workbook(first_spreadsheet, "Lista A", "FILHA", "(00) 90000-0000")
            self._create_single_contact_workbook(second_spreadsheet, "Lista B", "FILHA", "(00) 91111-1111")

            repository = SqliteGuestRepository(database_path)
            repository.initialize()
            import_use_case = ImportSpreadsheetUseCase(repository, OpenpyxlSpreadsheetReader())

            first_import = import_use_case.execute_workbook(str(first_spreadsheet))
            import_use_case.execute_workbook(str(second_spreadsheet))

            duplicates_page = ListGuestsUseCase(repository).execute(
                import_id=None,
                workbook_id=None,
                page=0,
                page_size=50,
                duplicates_only=True,
            )
            first_page = ListGuestsUseCase(repository).execute(
                import_id=first_import.imported_sheets[0].import_id,
                workbook_id=first_import.workbook_id,
                page=0,
                page_size=50,
            )
            candidates = ReviewDuplicateSelectionUseCase(repository).list_duplicate_candidates(first_page.rows[0].id)

            self.assertEqual(duplicates_page.total_rows, 0)
            self.assertLessEqual(len(candidates), 1)

    def test_imports_simple_single_column_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            spreadsheet_path = temp_path / "convidados.xlsx"
            database_path = temp_path / "mala_direta.sqlite3"

            workbook = Workbook()
            worksheet = workbook.active
            worksheet.title = "Lista"
            worksheet.append(["Convidado"])
            worksheet.append(["Jose"])
            worksheet.append(["Maria"])
            workbook.save(spreadsheet_path)
            workbook.close()

            repository = SqliteGuestRepository(database_path)
            repository.initialize()

            import_result = ImportSpreadsheetUseCase(
                guest_repository=repository,
                spreadsheet_reader=OpenpyxlSpreadsheetReader(),
            ).execute_workbook(str(spreadsheet_path))

            self.assertEqual(import_result.total_rows, 2)
            self.assertEqual(len(import_result.imported_sheets), 1)
            self.assertTrue(import_result.imported_sheets[0].is_selectable)

            page = ListGuestsUseCase(repository).execute(
                import_id=import_result.imported_sheets[0].import_id,
                workbook_id=import_result.workbook_id,
                page=0,
                page_size=50,
            )

            self.assertEqual(page.columns, ("Convidado",))
            self.assertEqual(len(page.rows[0].verification_code), 8)
            self.assertTrue(page.rows[0].verification_code.isdigit())
            self.assertNotEqual(page.rows[0].verification_code, page.rows[1].verification_code)
            self.assertEqual(page.rows[0].data["Convidado"], "Jose")

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

            self.assertEqual(import_result.total_rows, 6)
            self.assertEqual(len(import_result.imported_sheets), 3)
            self.assertEqual(import_result.skipped_sheets, tuple())
            self.assertEqual(len(repository.list_workbooks()), 1)
            repository.rename_workbook(import_result.workbook_id, "Agenda de teste")
            self.assertEqual(repository.list_workbooks()[0].display_name, "Agenda de teste")

            summary_sheet = self._find_sheet(import_result.imported_sheets, "Resumo")
            amigos_sheet = self._find_sheet(import_result.imported_sheets, "Amigos")
            politicos_sheet = self._find_sheet(import_result.imported_sheets, "Políticos")

            self.assertFalse(summary_sheet.is_selectable)
            self.assertTrue(amigos_sheet.is_selectable)
            self.assertTrue(politicos_sheet.is_selectable)

            summary_page = ListGuestsUseCase(repository).execute(
                import_id=summary_sheet.import_id,
                workbook_id=import_result.workbook_id,
                page=0,
                page_size=50,
            )

            self.assertEqual(summary_page.total_rows, 2)
            self.assertEqual(summary_page.columns, ("Categoria", "Quantidade de contatos"))
            self.assertFalse(summary_page.rows[0].selectable)

            amigos_page = ListGuestsUseCase(repository).execute(
                import_id=amigos_sheet.import_id,
                workbook_id=import_result.workbook_id,
                page=0,
                page_size=50,
            )

            self.assertEqual(amigos_page.total_rows, 2)
            self.assertEqual(amigos_page.columns, ("Nome", "Endereço", "Telefone", "Obra / Universo"))
            self.assertEqual(amigos_page.rows[0].data["Nome"], "Chandler Bing")
            self.assertEqual(len(amigos_page.rows[0].verification_code), 8)
            self.assertNotEqual(amigos_page.rows[0].verification_code, amigos_page.rows[1].verification_code)
            self.assertTrue(amigos_page.rows[0].selectable)

            code_search_page = ListGuestsUseCase(repository).execute(
                import_id=amigos_sheet.import_id,
                workbook_id=import_result.workbook_id,
                page=0,
                page_size=50,
                search=amigos_page.rows[0].verification_code,
            )
            self.assertEqual(code_search_page.total_rows, 1)
            self.assertEqual(code_search_page.rows[0].data["Nome"], "Chandler Bing")

            selection_use_case = UpdateGuestSelectionUseCase(repository)
            updated_rows = selection_use_case.set_all_filtered_selected(
                import_id=amigos_sheet.import_id,
                workbook_id=import_result.workbook_id,
                selected=True,
                search="Friends",
            )
            self.assertEqual(updated_rows, 2)

            cleared_rows = selection_use_case.set_all_filtered_selected(
                import_id=amigos_sheet.import_id,
                workbook_id=import_result.workbook_id,
                selected=False,
                search="Monica",
            )
            self.assertEqual(cleared_rows, 1)

            selection_use_case.set_guest_selected(
                guest_id=amigos_page.rows[1].id,
                selected=True,
            )

            politicos_page = ListGuestsUseCase(repository).execute(
                import_id=politicos_sheet.import_id,
                workbook_id=import_result.workbook_id,
                page=0,
                page_size=50,
            )
            selection_use_case.set_guest_selected(
                guest_id=politicos_page.rows[0].id,
                selected=True,
            )

            update_data_use_case = UpdateGuestDataUseCase(repository)
            update_data_use_case.execute(
                guest_id=amigos_page.rows[0].id,
                column_name="Telefone",
                value="(00) 99999-0001",
            )
            update_data_use_case.execute(
                guest_id=politicos_page.rows[0].id,
                column_name="Nome",
                value="Ada Byron",
            )

            refreshed_amigos_page = ListGuestsUseCase(repository).execute(
                import_id=amigos_sheet.import_id,
                workbook_id=import_result.workbook_id,
                page=0,
                page_size=50,
            )
            self.assertEqual(refreshed_amigos_page.rows[0].data["Telefone"], "(00) 99999-0001")

            selected_page = ListGuestsUseCase(repository).execute(
                import_id=None,
                workbook_id=import_result.workbook_id,
                page=0,
                page_size=50,
                selected_only=True,
            )

            self.assertEqual(selected_page.total_rows, 3)
            self.assertEqual(selected_page.columns, ("Lista", "Nome", "Endereço", "Telefone", "Obra / Universo"))
            self.assertEqual(selected_page.editable_columns, ("Nome", "Endereço", "Telefone", "Obra / Universo"))
            self.assertEqual(selected_page.rows[0].data["Telefone"], "(00) 90000-0001")
            self.assertEqual(selected_page.rows[2].data["Nome"], "Ada Lovelace")
            self.assertEqual(selected_page.rows[0].verification_code, amigos_page.rows[0].verification_code)

            update_data_use_case.execute(
                guest_id=selected_page.rows[0].id,
                column_name="Nome",
                value="Chandler Export",
                automatic=True,
            )

            automatic_page_after_edit = ListGuestsUseCase(repository).execute(
                import_id=None,
                workbook_id=import_result.workbook_id,
                page=0,
                page_size=50,
                selected_only=True,
            )
            source_page_after_automatic_edit = ListGuestsUseCase(repository).execute(
                import_id=amigos_sheet.import_id,
                workbook_id=import_result.workbook_id,
                page=0,
                page_size=50,
            )
            self.assertEqual(automatic_page_after_edit.rows[0].data["Nome"], "Chandler Export")
            self.assertEqual(source_page_after_automatic_edit.rows[0].data["Nome"], "Chandler Bing")

            automatic_sheet_use_case = ManageAutomaticSheetUseCase(repository)
            self.assertEqual(automatic_sheet_use_case.get_name(), "Planilha automática")
            automatic_sheet_use_case.rename("Lista final")
            self.assertEqual(automatic_sheet_use_case.get_name(), "Lista final")

            export_result = ExportSelectedGuestsUseCase(
                guest_repository=repository,
                exporter=exporter,
            ).execute(None, str(export_path), workbook_id=import_result.workbook_id)

            self.assertEqual(export_result.total_rows, 3)
            self.assertTrue(export_path.exists())
            self._assert_exported_content(export_path)

            cleared_rows = automatic_sheet_use_case.clear()
            self.assertEqual(cleared_rows, 3)
            self.assertEqual(automatic_sheet_use_case.get_name(), "Planilha automática")

            selected_page_after_clear = ListGuestsUseCase(repository).execute(
                import_id=None,
                workbook_id=import_result.workbook_id,
                page=0,
                page_size=50,
                selected_only=True,
            )
            self.assertEqual(selected_page_after_clear.total_rows, 0)

            repository.delete_workbook(import_result.workbook_id)
            self.assertEqual(repository.list_workbooks(), [])
            self.assertEqual(repository.list_imports(import_result.workbook_id), [])

    def _create_workbook(self, path: Path) -> None:
        workbook = Workbook()
        summary = workbook.active
        summary.title = "Resumo"
        summary.append(["Workbook criado para testes de mala direta", None, None, None])
        summary.merge_cells("A1:D1")
        summary.append(["Resumo das categorias importadas", None, None, None])
        summary.append(["Categoria", "Quantidade de contatos"])
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

    def _create_single_contact_workbook(self, path: Path, sheet_name: str, name: str, phone: str) -> None:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = sheet_name
        worksheet.append(["Nome", "Telefone"])
        worksheet.append([name, phone])
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
        self.assertEqual(rows[1], ("Amigos", "Chandler Export", "Rua da Comédia, 101", "(00) 90000-0001", "Friends"))
        self.assertEqual(rows[2], ("Amigos", "Monica Geller", "Rua do Café, 303", "(00) 90000-0003", "Friends"))
        self.assertEqual(rows[3], ("Políticos", "Ada Lovelace", "Rua Analítica, 1843", "(00) 91000-0001", "Computação"))
        self.assertEqual(len(rows), 4)

    def _find_sheet(self, sheets: object, sheet_name: str) -> object:
        for sheet in sheets:
            if sheet.sheet_name == sheet_name:
                return sheet
        raise AssertionError(f"Aba não encontrada: {sheet_name}")


if __name__ == "__main__":
    unittest.main()
