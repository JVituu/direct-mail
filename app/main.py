from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT_TEXT = str(PROJECT_ROOT)
if PROJECT_ROOT_TEXT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_TEXT)

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.infrastructure.database.connection import default_database_path
from app.infrastructure.repositories.sqlite_guest_repository import SqliteGuestRepository
from app.infrastructure.spreadsheet.openpyxl_exporter import OpenpyxlSelectedGuestsExporter
from app.infrastructure.spreadsheet.openpyxl_reader import OpenpyxlSpreadsheetReader
from app.presentation.desktop.viewmodels.main_view_model import MainViewModel
from app.presentation.desktop.views.main_window import MainWindow


APP_USER_MODEL_ID = "InstitutoRicardoBrennand.MalaDireta"
APP_ICON_PATH = Path("assets") / "mala_direta_rb_oficial.ico"


def ensure_project_root_on_path() -> None:
    if PROJECT_ROOT_TEXT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT_TEXT)


def configure_windows_app_id() -> None:
    if sys.platform != "win32":
        return

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        return


def resource_path(relative_path: str | Path) -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)) / relative_path
    return PROJECT_ROOT / relative_path


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
    configure_windows_app_id()
    app = QApplication(sys.argv)
    app_icon = QIcon(str(resource_path(APP_ICON_PATH)))
    app.setWindowIcon(app_icon)
    window = MainWindow(build_view_model())
    window.setWindowIcon(app_icon)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
