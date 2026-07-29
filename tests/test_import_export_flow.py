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
    def test_import_select_and_export_selected_guests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            spreadsheet_path = temp_path / "convidados.xlsx"
            database_path = temp_path / "mala_direta.sqlite3"
            export_path = temp_path / "selecionados.xlsx"

            self._create_spreadsheet(spreadsheet_path)

            repository = SqliteGuestRepository(database_path)
            repository.initialize()
            reader = OpenpyxlSpreadsheetReader()
            exporter = OpenpyxlSelectedGuestsExporter()

            import_result = ImportSpreadsheetUseCase(
                guest_repository=repository,
                spreadsheet_reader=reader,
                batch_size=2,
            ).execute(str(spreadsheet_path), "Convidados")

            self.assertEqual(import_result.total_rows, 3)
            self.assertEqual(import_result.columns, ("Nome", "Email", "Cidade"))

            page = ListGuestsUseCase(repository).execute(
                import_id=import_result.import_id,
                page=0,
                page_size=50,
            )

            self.assertEqual(page.total_rows, 3)
            self.assertEqual(len(page.rows), 3)

            UpdateGuestSelectionUseCase(repository).set_guest_selected(
                guest_id=page.rows[0].id,
                selected=True,
            )

            export_result = ExportSelectedGuestsUseCase(
                guest_repository=repository,
                exporter=exporter,
            ).execute(import_result.import_id, str(export_path))

            self.assertEqual(export_result.total_rows, 1)
            self.assertTrue(export_path.exists())
            self._assert_exported_content(export_path)

    def _create_spreadsheet(self, path: Path) -> None:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Convidados"
        worksheet.append(["Nome", "Email", "Cidade"])
        worksheet.append(["Ana Silva", "ana@example.com", "Sao Paulo"])
        worksheet.append(["Bruno Costa", "bruno@example.com", "Rio de Janeiro"])
        worksheet.append(["Carla Souza", "carla@example.com", "Curitiba"])
        workbook.save(path)
        workbook.close()

    def _assert_exported_content(self, path: Path) -> None:
        workbook = load_workbook(path, read_only=True)
        try:
            worksheet = workbook["Selecionados"]
            rows = list(worksheet.iter_rows(values_only=True))
        finally:
            workbook.close()

        self.assertEqual(rows[0], ("Nome", "Email", "Cidade"))
        self.assertEqual(rows[1], ("Ana Silva", "ana@example.com", "Sao Paulo"))
        self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
