from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT_TEXT = str(PROJECT_ROOT)
if PROJECT_ROOT_TEXT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_TEXT)

from PySide6.QtWidgets import QApplication

from app.infrastructure.database.connection import default_database_path
from app.infrastructure.repositories.sqlite_guest_repository import SqliteGuestRepository
from app.infrastructure.spreadsheet.openpyxl_exporter import OpenpyxlSelectedGuestsExporter
from app.infrastructure.spreadsheet.openpyxl_reader import OpenpyxlSpreadsheetReader
from app.presentation.desktop.viewmodels.main_view_model import MainViewModel
from app.presentation.desktop.views.main_window import MainWindow


def ensure_project_root_on_path() -> None:
    if PROJECT_ROOT_TEXT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT_TEXT)


def build_view_model() -> MainViewModel:
    repository = SqliteGuestRepository(default_database_path())
    spreadsheet_reader = OpenpyxlSpreadsheetReader()
    exporter = OpenpyxlSelectedGuestsExporter()
    view_model = MainViewModel(
        guest_repository=repository,
        spreadsheet_reader=spreadsheet_reader,
        selected_guests_exporter=exporter,
    )
    view_model.initialize()
    return view_model


def main() -> int:
    ensure_project_root_on_path()
    app = QApplication(sys.argv)
    window = MainWindow(build_view_model())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
