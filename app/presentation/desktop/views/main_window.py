from math import ceil
from pathlib import Path
import re
import sys
from unicodedata import combining, normalize

from PySide6.QtCore import QEvent, QModelIndex, QObject, QPointF, QRect, QThread, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QComboBox,
    QPushButton,
    QRadioButton,
    QProgressBar,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QTableView,
    QToolTip,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from app.application.dtos.guest_dto import (
    GuestRowDTO,
    ImportSummaryDTO,
    WorkbookImportResultDTO,
    WorkbookSummaryDTO,
)
from app.presentation.desktop.viewmodels.main_view_model import MainViewModel
from app.presentation.desktop.widgets.guest_table_model import (
    GroupedGuestTableModel,
    GuestGroupDTO,
    GuestTableModel,
)


DIALOG_NAME_WORDS = (
    "nome",
    "name",
    "convidado",
    "pessoa",
    "cliente",
    "participante",
    "destinatario",
)
DIALOG_PHONE_WORDS = ("telefone", "phone", "fone", "tel")
DIALOG_MOBILE_WORDS = ("celular", "whatsapp", "mobile", "cell")
DIALOG_GENERIC_CONTACT_WORDS = ("contato", "contact")
DIALOG_EMAIL_WORDS = ("email", "e-mail", "mail")
DIALOG_CEP_WORDS = ("cep", "codigo postal", "postal code", "zip")
DIALOG_ADDRESS_WORDS = ("endereco", "address", "logradouro", "rua", "avenida", "av")
QUICK_FILTER_COLUMN_WORDS = {
    "name": DIALOG_NAME_WORDS,
    "category": ("categoria", "category"),
    "location": ("estado", "cidade", "uf", "city", "municipio"),
}
QUICK_FILTER_ORDER = ("name", "category", "location")
DEFAULT_REGISTRATION_CATEGORIES = (
    "ADVOGADA",
    "ADVOGADO",
    "ADVOGADOS",
    "AMIGOS",
    "ARQUITETA",
    "ARQUITETOS",
    "ART. PLASTICOS",
    "ATITUDE",
    "AUTORIDADES",
    "CON DA ALEMANHA",
    "CONS DA FRANCA",
    "CULTURA",
    "CURADOR",
    "ESCRITORIO",
    "EXPERIENCE CLUB",
    "FAMILIA",
    "FORNECEDORES",
    "GALERIA",
    "JORNALISTAS",
    "MEDICOS",
    "OUTROS",
    "POLITICOS",
)
HIDDEN_REGISTRATION_CATEGORIES = {"outros - riomar"}
COLUMN_DISPLAY_PRIORITY_WORDS = (
    ("lista",),
    ("selecao",),
    ("tratamento",),
    ("nome", "name", "convidado", "pessoa", "cliente", "participante"),
    ("categoria", "category", "grupo", "tipo"),
    ("endereco", "address", "logradouro", "rua", "avenida"),
    ("edificio", "edif", "predio"),
    ("cep", "codigo postal", "postal code", "zip"),
    ("estado", "cidade", "uf", "city", "municipio"),
    ("telefone", "phone", "fone", "tel"),
    ("celular", "whatsapp", "mobile", "cell"),
    ("email", "e-mail", "mail"),
    ("obs", "observacao", "observacoes"),
)
FILTER_EMPTY_VALUE_LABEL = "(Vazios)"
DIALOG_NON_CONTACT_WORDS = (
    *DIALOG_NAME_WORDS,
    *DIALOG_EMAIL_WORDS,
    *DIALOG_CEP_WORDS,
    *DIALOG_ADDRESS_WORDS,
    "bairro",
    "categoria",
    "category",
    "cidade",
    "edificio",
    "edif",
    "estado",
    "observacao",
    "obs",
    "predio",
    "uf",
)
DIALOG_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
DIALOG_CEP_PATTERN = re.compile(r"(?<!\d)\d{5}-?\d{3}(?!\d)")
DIALOG_PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?55\s*)?(?:\(?\d{2}\)?[\s.-]*)?(?:9[\s.-]*)?\d{4}[\s.-]?\d{4}(?!\d)"
)
DEFAULT_PAGE_SIZE = 500
HEADER_LOGO_PATH = Path("assets") / "rb_instituto_header_logo.png"


def resource_path(relative_path: str | Path) -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)) / relative_path
    return Path(__file__).resolve().parents[4] / relative_path


class ImportWorker(QObject):
    progress = Signal(str, int)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, view_model: MainViewModel, file_path: str) -> None:
        super().__init__()
        self._view_model = view_model
        self._file_path = file_path

    @Slot()
    def run(self) -> None:
        try:
            result = self._view_model.import_workbook(
                file_path=self._file_path,
                progress_callback=self.progress.emit,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class SendCornerButton(QPushButton):
    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        background = QColor("#eef3f9") if self.underMouse() and self.isEnabled() else QColor("#ffffff")
        if not self.isEnabled():
            background = QColor("#f8fafc")
        painter.setPen(QPen(QColor("#dde4ef")))
        painter.setBrush(QBrush(background))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        icon_color = QColor("#176bd7") if self.isEnabled() else QColor("#a8b2c1")
        width = max(self.width(), 1)
        height = max(self.height(), 1)
        points = QPolygonF(
            [
                QPointF(width * 0.30, height * 0.20),
                QPointF(width * 0.82, height * 0.50),
                QPointF(width * 0.30, height * 0.80),
                QPointF(width * 0.39, height * 0.57),
                QPointF(width * 0.57, height * 0.50),
                QPointF(width * 0.39, height * 0.43),
            ]
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(icon_color))
        painter.drawPolygon(points)


class FilterMenuButton(QPushButton):
    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        background = QColor("#ffffff") if not self.underMouse() else QColor("#eef3f9")
        if not self.isEnabled():
            background = QColor("#f8fafc")
        painter.setPen(QPen(QColor("#cfd9e8")))
        painter.setBrush(QBrush(background))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 4, 4)

        icon_color = QColor("#245783") if self.isEnabled() else QColor("#a8b2c1")
        funnel = QPolygonF(
            [
                QPointF(11, 9),
                QPointF(23, 9),
                QPointF(18, 15),
                QPointF(18, 22),
                QPointF(15, 24),
                QPointF(15, 15),
            ]
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(icon_color))
        painter.drawPolygon(funnel)

        painter.setPen(QColor("#172033") if self.isEnabled() else QColor("#98a5b8"))
        painter.drawText(
            QRect(32, 0, max(self.width() - 48, 1), self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.text(),
        )

        arrow_color = QColor("#52647d") if self.isEnabled() else QColor("#a8b2c1")
        arrow = QPolygonF(
            [
                QPointF(self.width() - 16, self.height() / 2 - 2),
                QPointF(self.width() - 8, self.height() / 2 - 2),
                QPointF(self.width() - 12, self.height() / 2 + 3),
            ]
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(arrow_color))
        painter.drawPolygon(arrow)


class CircleCheckDelegate(QStyledItemDelegate):
    @staticmethod
    def _is_checked(check_state: object) -> bool:
        return check_state == Qt.CheckState.Checked or check_state == Qt.CheckState.Checked.value

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        check_state = index.data(Qt.ItemDataRole.CheckStateRole)
        if check_state is None:
            super().paint(painter, option, index)
            return

        view_option = QStyleOptionViewItem(option)
        self.initStyleOption(view_option, index)
        view_option.text = ""
        view_option.features &= ~QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator

        style = view_option.widget.style() if view_option.widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, view_option, painter, view_option.widget)

        box_size = 16
        box_x = option.rect.x() + (option.rect.width() - box_size) // 2
        box_y = option.rect.y() + (option.rect.height() - box_size) // 2
        box_rect = QRect(box_x, box_y, box_size, box_size)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#8b98a8")))
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawRoundedRect(box_rect, 4, 4)

        if self._is_checked(check_state):
            dot_size = 8
            dot_x = box_x + (box_size - dot_size) // 2
            dot_y = box_y + (box_size - dot_size) // 2
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#111827")))
            painter.drawEllipse(dot_x, dot_y, dot_size, dot_size)
        painter.restore()

    def editorEvent(
        self,
        event: object,
        model: object,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        if not index.flags() & Qt.ItemFlag.ItemIsUserCheckable:
            return False
        if event.type() == QEvent.Type.MouseButtonRelease:
            current_state = index.data(Qt.ItemDataRole.CheckStateRole)
            next_state = (
                Qt.CheckState.Unchecked
                if self._is_checked(current_state)
                else Qt.CheckState.Checked
            )
            return bool(model.setData(index, next_state, Qt.ItemDataRole.CheckStateRole))
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Select):
            current_state = index.data(Qt.ItemDataRole.CheckStateRole)
            next_state = (
                Qt.CheckState.Unchecked
                if self._is_checked(current_state)
                else Qt.CheckState.Checked
            )
            return bool(model.setData(index, next_state, Qt.ItemDataRole.CheckStateRole))
        return False


class InvitationStatusDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        status = index.data(Qt.ItemDataRole.UserRole)
        if status is None:
            super().paint(painter, option, index)
            return

        view_option = QStyleOptionViewItem(option)
        self.initStyleOption(view_option, index)
        view_option.text = ""
        style = view_option.widget.style() if view_option.widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, view_option, painter, view_option.widget)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rects = self._action_rects(option.rect)
        self._draw_sent_action(painter, rects["sent"], status == "sent")
        self._draw_pending_action(painter, rects["waiting"], status == "waiting")
        self._draw_not_sent_action(painter, rects["not_sent"], status == "not_sent")
        painter.restore()

    def editorEvent(
        self,
        event: object,
        model: object,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False

        position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        for action, rect in self._action_rects(option.rect).items():
            if rect.contains(position):
                return bool(model.setData(index, action, Qt.ItemDataRole.UserRole))
        return False

    def helpEvent(
        self,
        event: object,
        view: object,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        if event.type() == QEvent.Type.ToolTip and index.isValid():
            for action, rect in self._action_rects(option.rect).items():
                if rect.contains(event.pos()):
                    QToolTip.showText(event.globalPos(), self._action_tooltip(action), view)
                    return True
            QToolTip.hideText()
            return True
        return super().helpEvent(event, view, option, index)

    def _action_rects(self, cell_rect: QRect) -> dict[str, QRect]:
        size = 17
        gap = 7
        total_width = size * 3 + gap * 2
        start_x = cell_rect.x() + max((cell_rect.width() - total_width) // 2, 0)
        y = cell_rect.y() + max((cell_rect.height() - size) // 2, 0)
        return {
            "sent": QRect(start_x, y, size, size),
            "waiting": QRect(start_x + size + gap, y, size, size),
            "not_sent": QRect(start_x + (size + gap) * 2, y, size, size),
        }

    def _action_tooltip(self, action: str) -> str:
        tooltips = {
            "sent": "E-mail enviado",
            "waiting": "E-mail em aguardo",
            "not_sent": "E-mail nao enviado",
        }
        return tooltips.get(action, "")

    def _draw_sent_action(self, painter: QPainter, rect: QRect, active: bool) -> None:
        painter.setPen(QPen(QColor("#22a35a"), 1))
        painter.setBrush(QBrush(QColor("#effaf3") if active else QColor("#ffffff")))
        painter.drawRoundedRect(rect, 4, 4)
        if not active:
            return
        painter.setPen(QPen(QColor("#168344"), 1))
        painter.drawLine(
            QPointF(rect.left() + 4, rect.center().y()),
            QPointF(rect.left() + 7, rect.bottom() - 5),
        )
        painter.drawLine(
            QPointF(rect.left() + 7, rect.bottom() - 5),
            QPointF(rect.right() - 4, rect.top() + 4),
        )

    def _draw_pending_action(self, painter: QPainter, rect: QRect, active: bool) -> None:
        painter.setPen(QPen(QColor("#d8a300"), 1))
        painter.setBrush(QBrush(QColor("#fff8df") if active else QColor("#ffffff")))
        painter.drawRoundedRect(rect, 4, 4)
        if not active:
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#e4ad00")))
        dot_size = 6
        painter.drawEllipse(
            rect.x() + (rect.width() - dot_size) // 2,
            rect.y() + (rect.height() - dot_size) // 2,
            dot_size,
            dot_size,
        )

    def _draw_not_sent_action(self, painter: QPainter, rect: QRect, active: bool) -> None:
        painter.setPen(QPen(QColor("#dc3b3b"), 1))
        painter.setBrush(QBrush(QColor("#fff1f2") if active else QColor("#ffffff")))
        painter.drawRoundedRect(rect, 4, 4)
        if not active:
            return
        painter.setPen(QPen(QColor("#dc2626"), 1))
        painter.drawLine(
            QPointF(rect.left() + 5, rect.top() + 5),
            QPointF(rect.right() - 5, rect.bottom() - 5),
        )
        painter.drawLine(
            QPointF(rect.right() - 5, rect.top() + 5),
            QPointF(rect.left() + 5, rect.bottom() - 5),
        )


class ContactTrackingDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        statuses = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(statuses, dict):
            super().paint(painter, option, index)
            return

        view_option = QStyleOptionViewItem(option)
        self.initStyleOption(view_option, index)
        view_option.text = ""
        style = view_option.widget.style() if view_option.widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, view_option, painter, view_option.widget)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#334155"), 1))
        painter.drawText(self._label_rect(option.rect), Qt.AlignmentFlag.AlignCenter, "Tel/Cel")
        rects = self._action_rects(option.rect)
        status = str(statuses.get("call", "")).casefold()
        self._draw_done_action(painter, rects["done"], status == "done")
        self._draw_missed_action(painter, rects["missed"], status == "missed")
        self._draw_not_done_action(painter, rects["not_done"], status == "not_done")
        painter.restore()

    def editorEvent(
        self,
        event: object,
        model: object,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False

        position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        for status, rect in self._action_rects(option.rect).items():
            if rect.contains(position):
                return bool(model.setData(index, f"call:{status}", Qt.ItemDataRole.UserRole))
        return False

    def helpEvent(
        self,
        event: object,
        view: object,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        if event.type() == QEvent.Type.ToolTip and index.isValid():
            for status, rect in self._action_rects(option.rect).items():
                if rect.contains(event.pos()):
                    QToolTip.showText(event.globalPos(), self._action_tooltip(status), view)
                    return True
            QToolTip.hideText()
            return True
        return super().helpEvent(event, view, option, index)

    def _layout_parts(self, cell_rect: QRect) -> tuple[int, int, int, int]:
        size = 17
        gap = 7
        label_width = 50
        total_width = label_width + size * 3 + gap * 2
        start_x = cell_rect.x() + max((cell_rect.width() - total_width) // 2, 2)
        y = cell_rect.y() + max((cell_rect.height() - size) // 2, 0)
        return start_x, y, size, gap

    def _label_rect(self, cell_rect: QRect) -> QRect:
        x, y, size, _ = self._layout_parts(cell_rect)
        return QRect(x, y - 1, 50, size + 2)

    def _action_rects(self, cell_rect: QRect) -> dict[str, QRect]:
        x, y, size, gap = self._layout_parts(cell_rect)
        start_x = x + 50
        return {
            "done": QRect(start_x, y, size, size),
            "missed": QRect(start_x + size + gap, y, size, size),
            "not_done": QRect(start_x + (size + gap) * 2, y, size, size),
        }

    def _action_tooltip(self, status: str) -> str:
        tooltips = {
            "done": "Contato por telefone/celular efetuado",
            "missed": "Não atendeu telefone/celular",
            "not_done": "Contato por telefone/celular não efetuado",
        }
        return tooltips.get(status, "")

    def _draw_done_action(self, painter: QPainter, rect: QRect, active: bool) -> None:
        painter.setPen(QPen(QColor("#22a35a"), 1))
        painter.setBrush(QBrush(QColor("#effaf3") if active else QColor("#ffffff")))
        painter.drawRoundedRect(rect, 4, 4)
        if not active:
            return
        painter.setPen(QPen(QColor("#168344"), 1))
        painter.drawLine(
            QPointF(rect.left() + 4, rect.center().y()),
            QPointF(rect.left() + 7, rect.bottom() - 5),
        )
        painter.drawLine(
            QPointF(rect.left() + 7, rect.bottom() - 5),
            QPointF(rect.right() - 4, rect.top() + 4),
        )

    def _draw_missed_action(self, painter: QPainter, rect: QRect, active: bool) -> None:
        painter.setPen(QPen(QColor("#d8a300"), 1))
        painter.setBrush(QBrush(QColor("#fff8df") if active else QColor("#ffffff")))
        painter.drawRoundedRect(rect, 4, 4)
        if not active:
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#e4ad00")))
        dot_size = 6
        painter.drawEllipse(
            rect.x() + (rect.width() - dot_size) // 2,
            rect.y() + (rect.height() - dot_size) // 2,
            dot_size,
            dot_size,
        )

    def _draw_not_done_action(self, painter: QPainter, rect: QRect, active: bool) -> None:
        painter.setPen(QPen(QColor("#dc3b3b"), 1))
        painter.setBrush(QBrush(QColor("#fff1f2") if active else QColor("#ffffff")))
        painter.drawRoundedRect(rect, 4, 4)
        if not active:
            return
        painter.setPen(QPen(QColor("#dc2626"), 1))
        painter.drawLine(
            QPointF(rect.left() + 5, rect.top() + 5),
            QPointF(rect.right() - 5, rect.bottom() - 5),
        )
        painter.drawLine(
            QPointF(rect.right() - 5, rect.top() + 5),
            QPointF(rect.left() + 5, rect.bottom() - 5),
        )


class MainWindow(QMainWindow):
    def __init__(self, view_model: MainViewModel) -> None:
        super().__init__()
        self._view_model = view_model
        self._current_workbook_id: int | None = None
        self._current_import_id: int | None = None
        self._current_sheet_selectable = False
        self._automatic_mode = False
        self._duplicates_mode = False
        self._current_search = ""
        self._current_page = 0
        self._total_rows = 0
        self._selected_rows = 0
        self._page_size = DEFAULT_PAGE_SIZE
        self._imports: list[ImportSummaryDTO] = []
        self._available_columns: tuple[str, ...] = tuple()
        self._visible_columns_by_context: dict[str, set[str]] = {}
        self._hidden_system_columns_by_context: dict[str, set[str]] = {}
        self._forced_visible_columns_by_context: dict[str, list[str]] = {}
        self._table_column_order_by_context: dict[str, list[str]] = {}
        self._table_column_value_filters_by_context: dict[str, dict[str, set[str]]] = {}
        self._restoring_table_header_layout = False
        self._filter_options_context_key: tuple[object, ...] | None = None
        self._filter_controls_updating = False
        self._quick_column_filters: set[str] = set()
        self._selected_category_filters: set[str] = set()
        self._selected_location_filters: set[str] = set()
        self._grouped_filter_kind: str | None = None
        self._grouped_filter_source_columns: tuple[str, ...] = tuple()
        self._grouped_filter_groups_by_key: dict[str, GuestGroupDTO] = {}
        self._marked_filter_group_keys: set[str] = set()
        self._duplicates_count_value = 0
        self._marked_guest_ids: set[int] = set()
        self._table_model: GuestTableModel | GroupedGuestTableModel | None = None
        self._import_thread: QThread | None = None
        self._import_worker: ImportWorker | None = None
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._apply_live_search)

        self.setWindowTitle("Mala Direta")
        self.resize(1320, 840)
        self._build_ui()
        self._apply_styles()
        self._load_workbooks()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("AppRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_workbook_tabs())
        layout.addWidget(self._build_filters_and_actions())

        self.table = self._create_table()
        layout.addWidget(self.table, 1)

        layout.addWidget(self._build_sheet_tabs())
        layout.addWidget(self._build_footer())

        self.setCentralWidget(root)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("Header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(16)

        logo_label = self._build_header_logo(header)
        if logo_label is not None:
            layout.addWidget(logo_label)

        title_box = QVBoxLayout()
        title = QLabel("Mala Direta")
        title.setObjectName("Title")
        subtitle = QLabel("Instituto Ricardo Brennand | Arquivos Excel são unificados automaticamente; selecione convidados e exporte a lista final.")
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box, 1)

        self.register_button = QPushButton("Cadastrar contato")
        self.register_button.setObjectName("SecondaryButton")
        self.register_button.clicked.connect(self._open_guest_registration_dialog)
        layout.addWidget(self.register_button)

        self.import_button = QPushButton("Importar planilha")
        self.import_button.setObjectName("PrimaryButton")
        self.import_button.clicked.connect(self._choose_file)
        layout.addWidget(self.import_button)

        self.export_button = QPushButton("Exportar lista final")
        self.export_button.setObjectName("SuccessButton")
        self.export_button.clicked.connect(self._export_selected)
        layout.addWidget(self.export_button)

        self.options_button = QPushButton("Opções")
        self.options_button.clicked.connect(self._show_options_menu)
        self.options_button.hide()
        layout.addWidget(self.options_button)

        return header

    def _build_header_logo(self, parent: QWidget) -> QLabel | None:
        pixmap = QPixmap(str(resource_path(HEADER_LOGO_PATH)))
        if pixmap.isNull():
            return None

        label = QLabel(parent)
        label.setObjectName("HeaderLogo")
        label.setFixedSize(250, 72)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setPixmap(
            pixmap.scaled(
                label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        return label

    def _build_workbook_tabs(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)

        label = QLabel("Planilha")
        label.setObjectName("SmallLabel")
        layout.addWidget(label)

        self.workbook_tabs = QTabBar()
        self.workbook_tabs.setExpanding(False)
        self.workbook_tabs.setUsesScrollButtons(True)
        self.workbook_tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.workbook_tabs.currentChanged.connect(self._on_workbook_changed)
        self.workbook_tabs.customContextMenuRequested.connect(self._show_workbook_context_menu)
        layout.addWidget(self.workbook_tabs, 1)

        return frame

    def _build_filters_and_actions(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        self.filter_button = FilterMenuButton("[Filtro: Todos]")
        self.filter_button.setMinimumWidth(140)
        self.filter_button.clicked.connect(self._show_quick_filter_menu)
        layout.addWidget(self.filter_button)

        self.column_filter_button = FilterMenuButton("Colunas")
        self.column_filter_button.setMinimumWidth(120)
        self.column_filter_button.clicked.connect(self._show_column_filter_menu)
        layout.addWidget(self.column_filter_button)

        self.create_column_button = QPushButton("Criar coluna", frame)
        self.create_column_button.setObjectName("CompactButton")
        self.create_column_button.clicked.connect(self._create_column)
        layout.addWidget(self.create_column_button)

        self.select_page_button = QPushButton("Marcar pág.", frame)
        self.select_page_button.setObjectName("CompactButton")
        self.select_page_button.clicked.connect(lambda: self._set_page_selection(True))
        layout.addWidget(self.select_page_button)

        self.clear_page_button = QPushButton("Desmarcar pág.", frame)
        self.clear_page_button.setObjectName("CompactButton")
        self.clear_page_button.clicked.connect(lambda: self._set_page_selection(False))
        layout.addWidget(self.clear_page_button)

        self.search_input = QLineEdit(frame)
        self.search_input.setPlaceholderText("Buscar por nome, telefone, endereço, obra ou qualquer coluna")
        self.search_input.returnPressed.connect(self._apply_search)
        self.search_input.textChanged.connect(self._schedule_live_search)
        self.search_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.search_input, 1)

        self.category_filter_combo = QComboBox(frame)
        self.category_filter_combo.addItem("Categoria: todas", "")
        self.category_filter_combo.hide()

        self.location_filter_combo = QComboBox(frame)
        self.location_filter_combo.addItem("Estado/Cidade: todos", "")
        self.location_filter_combo.hide()

        self.clear_search_button = QPushButton("Limpar", frame)
        self.clear_search_button.clicked.connect(self._clear_search)
        layout.addWidget(self.clear_search_button)

        return frame

    def _build_sheet_tabs(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("SheetBar")
        self.sheet_frame = frame
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        label = QLabel("Lista")
        label.setObjectName("SmallLabel")
        layout.addWidget(label)

        self.sheet_tabs = QTabBar()
        self.sheet_tabs.setExpanding(False)
        self.sheet_tabs.setUsesScrollButtons(True)
        self.sheet_tabs.currentChanged.connect(self._on_sheet_changed)
        layout.addWidget(self.sheet_tabs, 1)

        return frame

    def _build_footer(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("StatusBar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.first_page_button = QPushButton("Primeira")
        self.first_page_button.clicked.connect(self._go_first_page)
        layout.addWidget(self.first_page_button)

        self.previous_page_button = QPushButton("Anterior")
        self.previous_page_button.clicked.connect(self._go_previous_page)
        layout.addWidget(self.previous_page_button)

        self.next_page_button = QPushButton("Próxima")
        self.next_page_button.clicked.connect(self._go_next_page)
        layout.addWidget(self.next_page_button)

        self.last_page_button = QPushButton("Última")
        self.last_page_button.clicked.connect(self._go_last_page)
        layout.addWidget(self.last_page_button)

        self.page_label = QLabel("Nenhuma planilha importada")
        layout.addWidget(self.page_label)
        layout.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Pronto")
        layout.addWidget(self.status_label)

        return frame

    def _create_table(self) -> QTableView:
        table = QTableView()
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setDefaultSectionSize(170)
        header.setSectionsClickable(True)
        header.setSectionsMovable(True)
        header.setFirstSectionMovable(True)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.sectionMoved.connect(self._on_table_header_section_moved)
        header.sectionClicked.connect(self._show_table_header_filter_menu)
        header.customContextMenuRequested.connect(self._show_table_header_context_menu)
        table.verticalHeader().setDefaultSectionSize(28)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.setWordWrap(True)
        table.clicked.connect(self._on_table_clicked)
        table.doubleClicked.connect(self._on_table_double_clicked)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(self._show_table_context_menu)
        table.setItemDelegateForColumn(0, CircleCheckDelegate(table))
        self.table_send_button = SendCornerButton(table)
        self.table_send_button.setObjectName("TableSendButton")
        self.table_send_button.setToolTip("Enviar registros marcados para a Planilha automática")
        self.table_send_button.clicked.connect(self._send_marked_rows_to_automatic)
        self.table_send_button.setEnabled(False)
        self.table_send_button.raise_()
        QTimer.singleShot(0, self._position_table_send_button)
        return table

    def _position_table_send_button(self) -> None:
        if not hasattr(self, "table_send_button"):
            return
        frame_width = self.table.frameWidth()
        width = self.table.verticalHeader().width()
        height = max(self.table.horizontalHeader().height(), 28)
        if width <= 0:
            self.table_send_button.hide()
            return
        self.table_send_button.setGeometry(frame_width, frame_width, width, height)
        self.table_send_button.raise_()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#AppRoot {
                background: #f5f7fb;
                color: #172033;
                font-size: 13px;
            }
            QFrame#Header, QFrame#Panel, QFrame#SheetBar {
                background: #ffffff;
                border: 1px solid #dde4ef;
                border-radius: 8px;
            }
            QLabel#Title {
                color: #0f2f5f;
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#Subtitle {
                color: #607089;
            }
            QLabel#HeaderLogo {
                background: transparent;
                border: none;
            }
            QLabel#SmallLabel {
                color: #52647d;
                font-weight: 700;
            }
            QPushButton {
                background: #eef3f9;
                border: 1px solid #cfd9e8;
                border-radius: 6px;
                padding: 8px 12px;
                color: #172033;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #e3ecf7;
            }
            QPushButton:disabled {
                color: #98a5b8;
                background: #f1f3f6;
                border-color: #e1e6ee;
            }
            QPushButton#CompactButton {
                padding: 8px 10px;
                font-size: 12px;
                min-width: 0;
            }
            QPushButton#SecondaryButton {
                background: #ffffff;
                border-color: #b9c8dc;
                color: #0f2f5f;
                padding: 10px 18px;
            }
            QPushButton#SecondaryButton:hover {
                background: #eef3f9;
                border-color: #8fb0d8;
            }
            QPushButton#PrimaryButton {
                background: #1f5eff;
                border-color: #1f5eff;
                color: #ffffff;
                padding: 10px 18px;
            }
            QPushButton#PrimaryButton:hover {
                background: #174ed6;
            }
            QPushButton#SuccessButton {
                background: #16835f;
                border-color: #16835f;
                color: #ffffff;
                padding: 10px 18px;
            }
            QPushButton#SuccessButton:hover {
                background: #126c50;
            }
            QLineEdit, QComboBox {
                background: #ffffff;
                border: 1px solid #cfd9e8;
                border-radius: 6px;
                padding: 7px 9px;
            }
            QTableView {
                background: #ffffff;
                alternate-background-color: #f1f6fd;
                border: 1px solid #dde4ef;
                gridline-color: #dde4ef;
                selection-background-color: #cfe0ff;
                selection-color: #172033;
            }
            QPushButton#TableSendButton {
                background: #ffffff;
                border: 1px solid #dde4ef;
                border-radius: 0;
                color: #172033;
                font-size: 16px;
                font-weight: 800;
                padding: 0;
            }
            QPushButton#TableSendButton:hover {
                background: #eef3f9;
                border-color: #9bb8df;
            }
            QPushButton#TableSendButton:disabled {
                color: #a8b2c1;
                background: #f8fafc;
            }
            QHeaderView::section {
                background: #245783;
                color: #ffffff;
                border: 0;
                border-right: 1px solid #4779a4;
                padding: 7px;
                font-weight: 700;
            }
            QTabBar::tab {
                background: #e9eff7;
                color: #33445f;
                border: 1px solid #cfd9e8;
                padding: 8px 14px;
                margin-right: 4px;
                border-radius: 6px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0f2f5f;
                border-color: #9bb8df;
            }
            """
        )

    def _choose_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar planilha",
            str(Path.home()),
            "Planilhas Excel (*.xlsx)",
        )
        if file_path:
            self._start_import(file_path)

    def _start_import(self, file_path: str) -> None:
        self._set_busy(True)
        self.status_label.setText("Importando arquivo...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        thread = QThread(self)
        worker = ImportWorker(self._view_model, file_path)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_import_progress)
        worker.finished.connect(self._on_import_finished)
        worker.failed.connect(self._on_import_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_import_worker)

        self._import_thread = thread
        self._import_worker = worker
        thread.start()

    @Slot(str, int)
    def _on_import_progress(self, sheet_name: str, imported_rows: int) -> None:
        self.status_label.setText(f"Importando {sheet_name}: {imported_rows} linhas...")

    @Slot(object)
    def _on_import_finished(self, result: WorkbookImportResultDTO) -> None:
        self._set_busy(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.status_label.setText(f"{result.total_rows} linhas na Lista unificada.")
        self._load_workbooks(preferred_workbook_id=result.workbook_id)

        selectable_count = sum(1 for sheet in result.imported_sheets if sheet.is_selectable)
        duplicate_message = (
            f"\n{result.removed_duplicates} duplicidades removidas automaticamente."
            if result.removed_duplicates
            else ""
        )
        QMessageBox.information(
            self,
            "Importação concluída",
            (
                f"Arquivo '{result.file_name}' importado e unificado.\n"
                f"{len(result.imported_sheets)} abas carregadas, "
                f"{selectable_count} listas selecionáveis.\n"
                f"Lista unificada com {result.total_rows} linhas."
                f"{duplicate_message}"
            ),
        )

    @Slot(str)
    def _on_import_failed(self, message: str) -> None:
        self._set_busy(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.status_label.setText("Falha na importação.")
        QMessageBox.critical(self, "Erro ao importar", message)

    def _clear_import_worker(self) -> None:
        self._import_thread = None
        self._import_worker = None

    def _open_guest_registration_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Cadastrar convidado")
        dialog.resize(560, 360)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(12)

        title = QLabel("Cadastrar Contato")
        title.setObjectName("Title")
        subtitle = QLabel("Adicione um contato diretamente na base de dados.")
        subtitle.setObjectName("Subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        name_input = QLineEdit(dialog)
        name_input.setPlaceholderText("Nome completo")
        phone_input = QLineEdit(dialog)
        phone_input.setPlaceholderText("Telefone")
        mobile_input = QLineEdit(dialog)
        mobile_input.setPlaceholderText("Celular")
        email_input = QLineEdit(dialog)
        email_input.setPlaceholderText("E-mail")
        address_input = QLineEdit(dialog)
        address_input.setPlaceholderText("Endereco")

        category_input = QComboBox(dialog)
        category_input.setEditable(True)
        category_input.addItem("")
        for category in self._registration_categories():
            category_input.addItem(category)
        category_input.setCurrentText("")
        if category_input.lineEdit() is not None:
            category_input.lineEdit().setPlaceholderText("Selecione ou digite uma categoria")

        notes_input = QLineEdit(dialog)
        notes_input.setPlaceholderText("Observacao")

        form.addRow("NOME:", name_input)
        form.addRow("TELEFONE:", phone_input)
        form.addRow("CELULAR:", mobile_input)
        form.addRow("E-MAIL:", email_input)
        form.addRow("ENDERECO:", address_input)
        form.addRow("CATEGORIA:", category_input)
        form.addRow("OBS:", notes_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText("Cadastrar")
        if cancel_button is not None:
            cancel_button.setText("Cancelar")

        def accept_if_valid() -> None:
            if not name_input.text().strip():
                QMessageBox.information(dialog, "Cadastrar convidado", "Informe o nome do convidado.")
                name_input.setFocus()
                return
            dialog.accept()

        buttons.accepted.connect(accept_if_valid)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        name_input.setFocus()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = {
            "NOME": name_input.text(),
            "Telefone": phone_input.text(),
            "Celular": mobile_input.text(),
            "E-mail": email_input.text(),
            "ENDEREÇO": address_input.text(),
            "Categoria": category_input.currentText(),
            "OBS": notes_input.text(),
        }

        try:
            result = self._view_model.register_guest(values, workbook_id=self._current_workbook_id)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao cadastrar", str(exc))
            return

        self._marked_guest_ids.clear()
        self._current_search = ""
        self._reset_filter_inputs()
        self._filter_options_context_key = None
        self.status_label.setText("Convidado cadastrado na Lista unificada.")
        self._load_workbooks(preferred_workbook_id=result.workbook_id)

    def _registration_categories(self) -> tuple[str, ...]:
        categories = list(DEFAULT_REGISTRATION_CATEGORIES)
        try:
            options = self._view_model.load_filter_options(
                import_id=None,
                workbook_id=self._current_workbook_id,
            )
            categories.extend(options.categories)
        except Exception:
            pass

        hidden_categories = {
            self._normalize_dialog_text(category)
            for category in HIDDEN_REGISTRATION_CATEGORIES
        }
        unique_categories: list[str] = []
        seen: set[str] = set()
        for category in categories:
            clean_category = str(category or "").strip()
            normalized_category = self._normalize_dialog_text(clean_category)
            if not clean_category or normalized_category in hidden_categories or normalized_category in seen:
                continue
            unique_categories.append(clean_category.upper())
            seen.add(normalized_category)
        return tuple(unique_categories)

    def _load_workbooks(self, preferred_workbook_id: int | None = None) -> None:
        workbooks = self._view_model.list_workbooks()

        self.workbook_tabs.blockSignals(True)
        self._clear_tab_bar(self.workbook_tabs)
        for workbook in workbooks:
            self.workbook_tabs.addTab(self._workbook_tab_text(workbook, len(workbooks)))
            self.workbook_tabs.setTabData(
                self.workbook_tabs.count() - 1,
                {"kind": "workbook", "workbook_id": workbook.id},
            )
        duplicates_count = self._duplicates_count()
        self._update_duplicates_button(duplicates_count)
        automatic_count = self._automatic_selected_count()
        if automatic_count > 0:
            self.workbook_tabs.addTab(self._automatic_tab_text(automatic_count))
            self.workbook_tabs.setTabData(
                self.workbook_tabs.count() - 1,
                {"kind": "automatic", "workbook_id": None},
            )
        self.workbook_tabs.blockSignals(False)

        if not workbooks and automatic_count <= 0:
            self._current_workbook_id = None
            self._automatic_mode = False
            self._duplicates_mode = False
            self._imports = []
            self._load_sheet_tabs()
            self._update_actions()
            return

        target_index = 0
        if not workbooks and automatic_count > 0:
            target_index = self._automatic_tab_index()
        if preferred_workbook_id is not None:
            for index in range(self.workbook_tabs.count()):
                tab_data = self.workbook_tabs.tabData(index)
                if tab_data and tab_data["kind"] == "workbook" and tab_data["workbook_id"] == preferred_workbook_id:
                    target_index = index
                    break
        self.workbook_tabs.setCurrentIndex(target_index)
        self._on_workbook_changed(target_index)

    def _workbook_tab_text(self, workbook: WorkbookSummaryDTO, workbook_count: int) -> str:
        if workbook_count == 1:
            return f"Lista unificada ({workbook.total_rows})"
        return f"{workbook.display_name} ({workbook.total_rows})"

    def _on_workbook_changed(self, index: int) -> None:
        tab_data = self.workbook_tabs.tabData(index) if index >= 0 else None
        if index < 0:
            self._current_workbook_id = None
            self._automatic_mode = False
            self._duplicates_mode = False
        elif tab_data and tab_data["kind"] == "automatic":
            self._current_workbook_id = None
            self._current_import_id = None
            self._current_sheet_selectable = True
            self._automatic_mode = True
            self._duplicates_mode = False
        elif tab_data and tab_data["kind"] == "duplicates":
            self._current_workbook_id = None
            self._current_import_id = None
            self._current_sheet_selectable = True
            self._automatic_mode = False
            self._duplicates_mode = True
        else:
            self._current_workbook_id = int(tab_data["workbook_id"])
            self._automatic_mode = False
            self._duplicates_mode = False
        self._current_search = ""
        self._reset_filter_inputs()
        self._filter_options_context_key = None
        self._marked_guest_ids.clear()
        self._table_column_value_filters_by_context.clear()
        self._current_page = 0
        self._load_sheet_tabs()

    def _load_sheet_tabs(self) -> None:
        if self._automatic_mode or self._duplicates_mode:
            self.sheet_frame.setVisible(False)
            self.sheet_tabs.blockSignals(True)
            self._clear_tab_bar(self.sheet_tabs)
            self.sheet_tabs.blockSignals(False)
            self._load_table()
            return

        self.sheet_frame.setVisible(False)
        self.sheet_tabs.blockSignals(True)
        self._clear_tab_bar(self.sheet_tabs)

        self._imports = self._view_model.list_imports(self._current_workbook_id) if self._current_workbook_id else []
        selectable_imports = [imported_sheet for imported_sheet in self._imports if imported_sheet.is_selectable]
        total_rows = sum(imported_sheet.total_rows for imported_sheet in selectable_imports)
        if not total_rows:
            total_rows = sum(imported_sheet.total_rows for imported_sheet in self._imports)
        if self._imports:
            self.sheet_tabs.addTab(f"Lista unificada ({total_rows})")
            self.sheet_tabs.setTabData(
                self.sheet_tabs.count() - 1,
                {
                    "kind": "unified",
                    "import_id": None,
                    "selectable": bool(selectable_imports),
                },
            )

        self.sheet_tabs.blockSignals(False)
        self.sheet_tabs.setCurrentIndex(0 if self.sheet_tabs.count() else -1)
        self._on_sheet_changed(self.sheet_tabs.currentIndex())

    def _clear_tab_bar(self, tab_bar: QTabBar) -> None:
        while tab_bar.count():
            tab_bar.removeTab(0)

    def _find_matching_sheet_tab(self, previous_data: object) -> int:
        if not previous_data:
            return -1
        for index in range(self.sheet_tabs.count()):
            tab_data = self.sheet_tabs.tabData(index)
            if tab_data == previous_data:
                return index
        return -1

    def _show_quick_filter_menu(self) -> None:
        has_workspace = (
            self._current_workbook_id is not None
            or self._automatic_mode
            or self._duplicates_mode
        )
        if not has_workspace:
            return

        menu = QMenu(self)
        container = QWidget(menu)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(10, 8, 10, 8)
        container_layout.setSpacing(8)

        filter_options = (
            ("Nome", "name"),
            ("Categoria", "category"),
            ("Estado", "location"),
        )
        checkboxes: dict[str, QCheckBox] = {}
        for label, filter_kind in filter_options:
            checkbox = QCheckBox(label, container)
            checkbox.setChecked(filter_kind in self._quick_column_filters)
            container_layout.addWidget(checkbox)
            checkboxes[filter_kind] = checkbox

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 4, 0, 0)
        button_layout.setSpacing(8)

        clear_button = QPushButton("Limpar", container)
        cancel_button = QPushButton("Cancelar", container)
        apply_button = QPushButton("Aplicar", container)
        apply_button.setDefault(True)

        button_layout.addWidget(clear_button)
        button_layout.addStretch(1)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(apply_button)
        container_layout.addLayout(button_layout)

        widget_action = QWidgetAction(menu)
        widget_action.setDefaultWidget(container)
        menu.addAction(widget_action)

        clear_button.clicked.connect(lambda: self._set_quick_filter_checkboxes(checkboxes, False))
        cancel_button.clicked.connect(menu.close)
        apply_button.clicked.connect(lambda: self._apply_quick_filter_menu(checkboxes, menu))
        menu.exec(self.filter_button.mapToGlobal(self.filter_button.rect().bottomLeft()))

    def _set_quick_filter_checkboxes(
        self,
        checkboxes: dict[str, QCheckBox],
        checked: bool,
    ) -> None:
        for checkbox in checkboxes.values():
            checkbox.setChecked(checked)

    def _apply_quick_filter_menu(
        self,
        checkboxes: dict[str, QCheckBox],
        menu: QMenu,
    ) -> None:
        selected_filters = {
            filter_kind
            for filter_kind, checkbox in checkboxes.items()
            if checkbox.isChecked()
        }
        if selected_filters == self._quick_column_filters:
            menu.close()
            return
        self._quick_column_filters = selected_filters
        self._current_search = ""
        self._marked_guest_ids.clear()
        self._marked_filter_group_keys.clear()
        self._filter_controls_updating = True
        self.search_input.clear()
        self._selected_category_filters.clear()
        self._selected_location_filters.clear()
        self._filter_controls_updating = False
        self._update_quick_filter_button_text()
        menu.close()
        self._load_table()

    def _show_options_menu(self) -> None:
        return

    def _show_filter_menu(self) -> None:
        if self._automatic_mode or self._duplicates_mode or not self._imports:
            return

        menu = QMenu(self)
        for index, imported_sheet in enumerate(self._imports):
            label = imported_sheet.sheet_name
            if not imported_sheet.is_selectable:
                label = f"{label} · visualização"
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(index == self.sheet_tabs.currentIndex())
            action.setData(index)

        selected_action = menu.exec(self.options_button.mapToGlobal(self.options_button.rect().bottomLeft()))
        if selected_action is None:
            return

        target_index = int(selected_action.data())
        if target_index != self.sheet_tabs.currentIndex():
            self.sheet_tabs.setCurrentIndex(target_index)

    def _show_column_filter_menu(self) -> None:
        if not self._available_columns:
            return

        menu = QMenu(self)
        menu.setObjectName("ColumnFilterMenu")

        container = QWidget(menu)
        container.setMinimumWidth(340)
        container.setMaximumHeight(460)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        label = QLabel("Selecione as colunas que deseja visualizar na tabela.")
        label.setWordWrap(True)
        layout.addWidget(label)

        column_list = QListWidget(container)
        column_list.setMinimumHeight(220)
        visible_columns = self._visible_columns_for_current_context(self._available_columns)
        for column_name in self._available_columns:
            item = QListWidgetItem(column_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if column_name in visible_columns
                else Qt.CheckState.Unchecked
            )
            column_list.addItem(item)
        layout.addWidget(column_list, 1)

        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(8)
        show_all_button = QPushButton("Mostrar todas")
        hide_all_button = QPushButton("Desmarcar todas")
        apply_button = QPushButton("Aplicar")
        cancel_button = QPushButton("Cancelar")
        show_all_button.clicked.connect(lambda: self._set_all_column_items_checked(column_list, True))
        hide_all_button.clicked.connect(lambda: self._set_all_column_items_checked(column_list, False))
        apply_button.clicked.connect(lambda: self._apply_column_filter_from_list(column_list, menu))
        cancel_button.clicked.connect(menu.close)
        buttons_layout.addWidget(show_all_button)
        buttons_layout.addWidget(hide_all_button)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(cancel_button)
        buttons_layout.addWidget(apply_button)
        layout.addLayout(buttons_layout)

        widget_action = QWidgetAction(menu)
        widget_action.setDefaultWidget(container)
        menu.addAction(widget_action)
        menu.exec(self.column_filter_button.mapToGlobal(self.column_filter_button.rect().bottomLeft()))

    def _apply_column_filter_from_list(self, column_list: QListWidget, menu: QMenu) -> None:
        selected_columns = {
            column_list.item(index).text()
            for index in range(column_list.count())
            if column_list.item(index).checkState() == Qt.CheckState.Checked
        }
        if not selected_columns:
            QMessageBox.warning(
                self,
                "Filtro de colunas",
                "Selecione pelo menos uma coluna para visualizar.",
            )
            return

        context_key = self._column_filter_context_key()
        if len(selected_columns) == len(self._available_columns):
            self._visible_columns_by_context.pop(context_key, None)
        else:
            self._visible_columns_by_context[context_key] = selected_columns
        menu.close()
        self._load_table()

    def _set_all_column_items_checked(self, column_list: QListWidget, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for index in range(column_list.count()):
            column_list.item(index).setCheckState(state)

    def _column_filter_context_key(self) -> str:
        if self._automatic_mode:
            return "automatic"
        if self._duplicates_mode:
            return "duplicates"
        if self._current_import_id is not None:
            return f"sheet:{self._current_import_id}"
        if self._current_workbook_id is not None:
            return f"workbook:{self._current_workbook_id}"
        return "empty"

    def _visible_columns_for_current_context(self, columns: tuple[str, ...]) -> set[str]:
        visible_columns = self._visible_columns_by_context.get(self._column_filter_context_key())
        if visible_columns is None:
            return set(columns)
        return {column_name for column_name in columns if column_name in visible_columns}

    def _quick_visible_columns(self, columns: tuple[str, ...]) -> set[str] | None:
        if not self._quick_column_filters:
            return None

        visible_columns = {
            column_name
            for column_name in columns
            if self._matches_quick_column_filter(column_name)
        }
        return visible_columns or None

    def _matches_quick_column_filter(self, column_name: str) -> bool:
        return any(
            self._matches_quick_filter_kind_column(column_name, filter_kind)
            for filter_kind in self._active_quick_filter_kinds()
        )

    def _matches_quick_filter_kind_column(self, column_name: str, filter_kind: str) -> bool:
        normalized_column = self._normalize_dialog_text(column_name)
        words = QUICK_FILTER_COLUMN_WORDS.get(filter_kind, tuple())
        normalized_words = {self._normalize_dialog_text(word) for word in words}
        return any(word and word in normalized_column for word in normalized_words)

    def _active_quick_filter_kinds(self) -> tuple[str, ...]:
        return tuple(
            filter_kind
            for filter_kind in QUICK_FILTER_ORDER
            if filter_kind in self._quick_column_filters
        )

    def _quick_column_groups(self, columns: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
        column_groups: list[tuple[str, ...]] = []
        for filter_kind in self._active_quick_filter_kinds():
            matching_columns = tuple(
                column_name
                for column_name in columns
                if self._matches_quick_filter_kind_column(column_name, filter_kind)
            )
            if matching_columns:
                column_groups.append(matching_columns)
        return tuple(column_groups)

    def _apply_quick_row_filter(
        self,
        rows: list[GuestRowDTO],
        columns: tuple[str, ...],
    ) -> list[GuestRowDTO]:
        if not self._quick_column_filters:
            return rows

        column_groups = self._quick_column_groups(columns)
        if not column_groups:
            return rows

        filtered_rows = [
            row
            for row in rows
            if self._quick_row_filter_values(row, column_groups)
        ]
        return sorted(
            filtered_rows,
            key=lambda row: self._quick_row_sort_key(row, column_groups),
        )

    def _quick_row_sort_key(
        self,
        row: GuestRowDTO,
        column_groups: tuple[tuple[str, ...], ...],
    ) -> tuple[str, str, str, int, int]:
        values = self._quick_row_filter_values(row, column_groups)
        normalized_values = [self._normalize_dialog_text(value) for value in values]
        primary_value = normalized_values[0] if normalized_values else ""
        return (
            primary_value,
            " ".join(normalized_values),
            self._normalize_dialog_text(row.sheet_name),
            row.row_number,
            row.id,
        )

    def _quick_row_filter_values(
        self,
        row: GuestRowDTO,
        column_groups: tuple[tuple[str, ...], ...],
    ) -> list[str]:
        values: list[str] = []
        for columns in column_groups:
            group_value = self._first_quick_row_group_value(row, columns)
            if group_value:
                values.append(group_value)
        return values

    def _first_quick_row_group_value(
        self,
        row: GuestRowDTO,
        columns: tuple[str, ...],
    ) -> str:
        for column_name in columns:
            value = self._clean_quick_row_value(row.data.get(column_name, ""))
            if value:
                return value
        return ""

    def _clean_quick_row_value(self, value: object) -> str:
        for item in str(value or "").replace("\r", "\n").split("\n"):
            clean_item = item.strip()
            if clean_item:
                return clean_item
        return ""

    def _should_show_grouped_quick_filter(
        self,
        selected_only: bool,
        duplicates_only: bool,
    ) -> bool:
        if selected_only or duplicates_only:
            return False
        if not self._current_sheet_selectable:
            return False
        active_filters = self._active_quick_filter_kinds()
        return len(active_filters) == 1 and active_filters[0] in {"name", "category", "location"}

    def _grouped_filter_header_label(self, filter_kind: str) -> str:
        labels = {
            "name": "Nome",
            "category": "Categoria",
            "location": "Estado/Cidade",
        }
        return labels.get(filter_kind, "Filtro")

    def _build_grouped_filter_groups(
        self,
        rows: list[GuestRowDTO],
        columns: tuple[str, ...],
        filter_kind: str,
    ) -> list[GuestGroupDTO]:
        matching_columns = tuple(
            column_name
            for column_name in columns
            if self._matches_quick_filter_kind_column(column_name, filter_kind)
        )
        if not matching_columns:
            return []

        labels_by_key: dict[str, str] = {}
        rows_by_key: dict[str, list[GuestRowDTO]] = {}
        for row in rows:
            for group_value in self._group_values_for_row(row, matching_columns):
                group_key = self._normalize_dialog_text(group_value)
                if not group_key:
                    continue
                labels_by_key.setdefault(group_key, group_value.upper())
                rows_by_key.setdefault(group_key, []).append(row)

        return [
            GuestGroupDTO(
                key=group_key,
                label=labels_by_key[group_key],
                rows=tuple(group_rows),
            )
            for group_key, group_rows in sorted(
                rows_by_key.items(),
                key=lambda item: (
                    self._normalize_dialog_text(labels_by_key[item[0]]),
                    labels_by_key[item[0]],
                ),
            )
        ]

    def _group_values_for_row(
        self,
        row: GuestRowDTO,
        columns: tuple[str, ...],
    ) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for column_name in columns:
            raw_value = str(row.data.get(column_name, ""))
            for item in raw_value.replace("\r", "\n").split("\n"):
                clean_item = item.strip()
                if not clean_item:
                    continue
                normalized_item = self._normalize_dialog_text(clean_item)
                if normalized_item in seen:
                    continue
                values.append(clean_item)
                seen.add(normalized_item)
        return values

    def _apply_column_filter(
        self,
        columns: tuple[str, ...],
        editable_columns: tuple[str, ...],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        self._available_columns = columns
        if not columns:
            return tuple(), tuple()

        visible_column_names = self._visible_columns_for_current_context(columns)
        quick_visible_columns = self._quick_visible_columns(columns)
        if quick_visible_columns is not None:
            visible_column_names = visible_column_names.intersection(quick_visible_columns)

        filtered_columns = tuple(column_name for column_name in columns if column_name in visible_column_names)
        if not filtered_columns:
            filtered_columns = columns
            self._visible_columns_by_context.pop(self._column_filter_context_key(), None)

        filtered_editable_columns = tuple(
            column_name for column_name in editable_columns if column_name in filtered_columns
        )
        return filtered_columns, filtered_editable_columns

    def _update_filter_button_text(self, visible_columns: tuple[str, ...]) -> None:
        if not self._available_columns or len(visible_columns) == len(self._available_columns):
            self.column_filter_button.setText("Colunas")
            return
        self.column_filter_button.setText(f"Colunas ({len(visible_columns)}/{len(self._available_columns)})")

    def _automatic_selected_count(self) -> int:
        try:
            return self._view_model.load_guests(
                import_id=None,
                workbook_id=None,
                page=0,
                page_size=50,
                selected_only=True,
            ).total_rows
        except Exception:
            return 0

    def _duplicates_count(self) -> int:
        try:
            return self._view_model.load_guests(
                import_id=None,
                workbook_id=None,
                page=0,
                page_size=50,
                duplicates_only=True,
            ).total_rows
        except Exception:
            return 0

    def _update_duplicates_button(self, duplicates_count: int | None = None) -> None:
        count = self._duplicates_count() if duplicates_count is None else duplicates_count
        self._duplicates_count_value = count

    def _open_duplicates_view(self) -> None:
        if self._duplicates_count() <= 0:
            self._update_duplicates_button(0)
            return

        self.workbook_tabs.blockSignals(True)
        self.workbook_tabs.setCurrentIndex(-1)
        self.workbook_tabs.blockSignals(False)
        self._current_workbook_id = None
        self._current_import_id = None
        self._current_sheet_selectable = True
        self._automatic_mode = False
        self._duplicates_mode = True
        self._current_search = ""
        self._reset_filter_inputs()
        self._filter_options_context_key = None
        self._current_page = 0
        self._load_sheet_tabs()

    def _automatic_tab_text(self, selected_count: int | None = None) -> str:
        count = self._automatic_selected_count() if selected_count is None else selected_count
        return f"{self._view_model.automatic_sheet_name()} ({count})"

    def _automatic_tab_index(self) -> int:
        for index in range(self.workbook_tabs.count()):
            tab_data = self.workbook_tabs.tabData(index)
            if tab_data and tab_data["kind"] == "automatic":
                return index
        return -1

    def _refresh_automatic_tab_label(self) -> None:
        selected_count = self._automatic_selected_count()
        index = self._automatic_tab_index()

        if selected_count > 0:
            if index >= 0:
                self.workbook_tabs.setTabText(index, self._automatic_tab_text(selected_count))
                return

            self.workbook_tabs.blockSignals(True)
            self.workbook_tabs.addTab(self._automatic_tab_text(selected_count))
            self.workbook_tabs.setTabData(
                self.workbook_tabs.count() - 1,
                {"kind": "automatic", "workbook_id": None},
            )
            self.workbook_tabs.blockSignals(False)
            return

        if index < 0:
            return

        if self.workbook_tabs.currentIndex() == index:
            self._load_workbooks()
            return

        self.workbook_tabs.blockSignals(True)
        self.workbook_tabs.removeTab(index)
        self.workbook_tabs.blockSignals(False)

    def _on_sheet_changed(self, index: int) -> None:
        if self._automatic_mode or self._duplicates_mode:
            self._current_import_id = None
            self._current_sheet_selectable = True
            self._load_table()
            return

        tab_data = self.sheet_tabs.tabData(index) if index >= 0 else None
        if not tab_data:
            self._current_import_id = None
            self._current_sheet_selectable = False
            self._automatic_mode = False
        else:
            self._current_import_id = tab_data["import_id"]
            self._current_sheet_selectable = bool(tab_data["selectable"])
        self._marked_guest_ids.clear()
        self._table_column_value_filters_by_context.pop(self._column_filter_context_key(), None)
        self._current_page = 0
        self._load_table()

    def _apply_search(self) -> None:
        self._search_timer.stop()
        self._apply_search_text()

    def _schedule_live_search(self) -> None:
        if self._filter_controls_updating:
            return
        has_workspace = self._current_workbook_id is not None or self._automatic_mode or self._duplicates_mode
        self.clear_search_button.setEnabled(
            has_workspace
            and (bool(self.search_input.text().strip()) or bool(self._active_table_column_value_filters()))
        )
        self._search_timer.start()

    def _apply_live_search(self) -> None:
        self._apply_search_text()

    def _apply_filter_controls_changed(self) -> None:
        if self._filter_controls_updating:
            return
        self._search_timer.stop()
        self._apply_search_text()

    def _apply_search_text(self) -> None:
        search = self._combined_filter_search()
        if search == self._current_search:
            return
        self._current_search = search
        self._marked_guest_ids.clear()
        self._current_page = 0
        self._load_table()

    def _clear_search(self) -> None:
        had_column_filters = bool(self._active_table_column_value_filters())
        self._filter_controls_updating = True
        self.search_input.clear()
        self._filter_controls_updating = False
        self._search_timer.stop()
        self._table_column_value_filters_by_context.pop(self._column_filter_context_key(), None)
        previous_search = self._current_search
        self._apply_search_text()
        if had_column_filters and not previous_search:
            self._load_table()

    def _combined_filter_search(self) -> str:
        return self.search_input.text().strip()

    def _combo_value(self, combo: QComboBox) -> str:
        value = combo.currentData()
        return str(value or "").strip()

    def _copy_filter_combo_items(self, source: QComboBox, target: QComboBox) -> None:
        target.clear()
        for index in range(source.count()):
            target.addItem(source.itemText(index), source.itemData(index))
        target.setCurrentIndex(max(source.currentIndex(), 0))

    def _set_combo_current_data(self, combo: QComboBox, value: object) -> None:
        target_index = combo.findData(value)
        combo.setCurrentIndex(target_index if target_index >= 0 else 0)

    def _reset_filter_inputs(self) -> None:
        self._filter_controls_updating = True
        self.search_input.clear()
        self._quick_column_filters.clear()
        self._selected_category_filters.clear()
        self._selected_location_filters.clear()
        self._marked_filter_group_keys.clear()
        if hasattr(self, "category_filter_combo"):
            self.category_filter_combo.setCurrentIndex(0)
        if hasattr(self, "location_filter_combo"):
            self.location_filter_combo.setCurrentIndex(0)
        self._filter_controls_updating = False
        self._update_quick_filter_button_text()

    def _update_quick_filter_button_text(self) -> None:
        if not hasattr(self, "filter_button"):
            return

        filter_labels = {
            "name": "Nome",
            "category": "Categoria",
            "location": "Estado",
        }
        active_filters = [
            filter_labels[filter_kind]
            for filter_kind in self._active_quick_filter_kinds()
        ]

        if not active_filters:
            self.filter_button.setText("[Filtro: Todos]")
        else:
            self.filter_button.setText(f"[Filtro: {active_filters[0]}]")

    def _refresh_filter_options(
        self,
        import_id: int | None,
        workbook_id: int | None,
        selected_only: bool,
        duplicates_only: bool,
    ) -> None:
        context_key = (import_id, workbook_id, selected_only, duplicates_only)
        if context_key == self._filter_options_context_key:
            return

        self._filter_options_context_key = context_key
        try:
            options = self._view_model.load_filter_options(
                import_id=import_id,
                workbook_id=workbook_id,
                selected_only=selected_only,
                duplicates_only=duplicates_only,
            )
        except Exception:
            options = None

        current_category = self._combo_value(self.category_filter_combo)
        current_location = self._combo_value(self.location_filter_combo)
        categories = options.categories if options is not None else tuple()
        locations = options.locations if options is not None else tuple()
        self._selected_category_filters.intersection_update(categories)
        self._selected_location_filters.intersection_update(locations)
        self._set_filter_combo_items(
            self.category_filter_combo,
            "Categoria: todas",
            categories,
            current_category,
        )
        self._set_filter_combo_items(
            self.location_filter_combo,
            "Estado/Cidade: todos",
            locations,
            current_location,
        )

    def _reset_filter_options(self) -> None:
        self._filter_options_context_key = None
        self._set_filter_combo_items(self.category_filter_combo, "Categoria: todas", tuple(), "")
        self._set_filter_combo_items(self.location_filter_combo, "Estado/Cidade: todos", tuple(), "")

    def _set_filter_combo_items(
        self,
        combo: QComboBox,
        placeholder: str,
        values: tuple[str, ...],
        current_value: str,
    ) -> None:
        self._filter_controls_updating = True
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(placeholder, "")
        for value in values:
            combo.addItem(value, value)
        selected_index = combo.findData(current_value)
        combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        combo.blockSignals(False)
        self._filter_controls_updating = False
        self._update_quick_filter_button_text()

    def _load_table(self) -> None:
        if self._automatic_mode:
            workbook_id = None
            import_id = None
            selected_only = True
            duplicates_only = False
        elif self._duplicates_mode:
            workbook_id = None
            import_id = None
            selected_only = False
            duplicates_only = True
        elif self._current_workbook_id is not None and self.sheet_tabs.count() > 0:
            workbook_id = self._current_workbook_id
            import_id = self._current_import_id
            selected_only = False
            duplicates_only = False
        else:
            self._reset_filter_options()
            self._set_table_page([], tuple(), tuple(), 0, 0, 0)
            return

        self._refresh_filter_options(import_id, workbook_id, selected_only, duplicates_only)

        try:
            has_column_value_filters = bool(self._active_table_column_value_filters())
            if self._should_show_grouped_quick_filter(selected_only, duplicates_only):
                active_filter = self._active_quick_filter_kinds()[0]
                page = self._view_model.load_guests(
                    import_id=import_id,
                    workbook_id=workbook_id,
                    page=0,
                    page_size=5000,
                    search=self._current_search,
                    selected_only=selected_only,
                    duplicates_only=duplicates_only,
                )
                groups = self._build_grouped_filter_groups(page.rows, page.columns, active_filter)
                self._current_page = 0
                self._set_grouped_filter_page(
                    groups=groups,
                    filter_kind=active_filter,
                    source_columns=page.columns,
                    source_total_rows=page.total_rows,
                    selected_rows=page.selected_rows,
                )
                return

            page = self._view_model.load_guests(
                import_id=import_id,
                workbook_id=workbook_id,
                page=0 if has_column_value_filters else self._current_page,
                page_size=5000 if has_column_value_filters else DEFAULT_PAGE_SIZE,
                search=self._current_search,
                selected_only=selected_only,
                duplicates_only=duplicates_only,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao carregar dados", str(exc))
            return

        self._current_page = self._normalize_page(self._current_page, page.total_rows, page.page_size)
        self._set_table_page(
            rows=page.rows,
            columns=page.columns,
            editable_columns=page.editable_columns,
            total_rows=page.total_rows,
            selected_rows=page.selected_rows,
            page_size=page.page_size,
        )

    def _set_table_page(
        self,
        rows: list[GuestRowDTO],
        columns: tuple[str, ...],
        editable_columns: tuple[str, ...],
        total_rows: int,
        selected_rows: int,
        page_size: int,
    ) -> None:
        self._grouped_filter_kind = None
        self._grouped_filter_source_columns = tuple()
        self._grouped_filter_groups_by_key = {}
        self._marked_filter_group_keys.clear()
        self._total_rows = total_rows
        self._selected_rows = selected_rows
        self._page_size = page_size
        rows = self._apply_quick_row_filter(rows, columns)
        rows = self._apply_table_column_value_filters(rows)
        if self._active_table_column_value_filters():
            self._current_page = 0
            total_rows = len(rows)
            page_size = max(len(rows), 1)
            self._total_rows = total_rows
            self._page_size = page_size
        columns, editable_columns = self._include_forced_visible_columns(rows, columns, editable_columns)
        columns, editable_columns = self._order_columns_for_display(columns, editable_columns)
        columns, editable_columns = self._apply_column_filter(columns, editable_columns)
        self._table_model = GuestTableModel(
            rows,
            columns,
            editable_columns,
            self._marked_guest_ids,
            self._on_row_selection_changed,
            self._on_cell_changed,
            highlight_selected_rows=not self._automatic_mode,
            automatic_mode=self._automatic_mode,
            invitation_status_changed=self._on_invitation_status_changed,
            contact_status_changed=self._on_contact_status_changed,
        )
        self.table.setUpdatesEnabled(False)
        self.table.setModel(self._table_model)
        self.table.horizontalHeader().setStretchLastSection(False)
        for logical_column in range(self._table_model.columnCount()):
            self.table.setItemDelegateForColumn(logical_column, QStyledItemDelegate(self.table))
            self.table.setColumnHidden(logical_column, False)
        if self._automatic_mode:
            selection_column = self._table_model.system_column_index("selection")
            tracking_column = self._table_model.system_column_index("contact_tracking")
            if selection_column is not None:
                self.table.setItemDelegateForColumn(selection_column, InvitationStatusDelegate(self.table))
                self.table.setColumnWidth(selection_column, 120)
            if tracking_column is not None:
                self.table.setItemDelegateForColumn(tracking_column, ContactTrackingDelegate(self.table))
                self.table.setColumnWidth(tracking_column, 150)
            self.table.verticalHeader().setDefaultSectionSize(34)
        else:
            selection_column = self._table_model.system_column_index("selection")
            if selection_column is not None:
                self.table.setItemDelegateForColumn(selection_column, CircleCheckDelegate(self.table))
                self.table.setColumnWidth(selection_column, 110)
            self.table.verticalHeader().setDefaultSectionSize(28)
        code_column = self._table_model.system_column_index("code")
        duplicate_column = self._table_model.system_column_index("duplicate")
        if code_column is not None:
            self.table.setColumnWidth(code_column, 95)
        if duplicate_column is not None:
            self.table.setColumnWidth(duplicate_column, 120)
        first_data_column = self._first_data_table_column()
        if first_data_column is not None:
            self.table.setColumnWidth(first_data_column, 190)
        self._apply_default_table_column_widths()
        if self._table_model.has_multiline_cells():
            self.table.resizeRowsToContents()
        self._restore_table_header_layout()
        self._apply_hidden_system_columns()
        self.table.setUpdatesEnabled(True)
        self._position_table_send_button()
        self._update_filter_button_text(columns)
        self._update_page_label()
        self._update_actions()

    def _set_grouped_filter_page(
        self,
        groups: list[GuestGroupDTO],
        filter_kind: str,
        source_columns: tuple[str, ...],
        source_total_rows: int,
        selected_rows: int,
    ) -> None:
        groups = self._apply_grouped_column_value_filters(groups)
        self._grouped_filter_kind = filter_kind
        self._grouped_filter_source_columns = source_columns
        self._grouped_filter_groups_by_key = {group.key: group for group in groups}
        self._marked_filter_group_keys.intersection_update(self._grouped_filter_groups_by_key)
        self._rebuild_group_marked_guest_ids()

        self._total_rows = len(groups)
        self._selected_rows = selected_rows
        self._page_size = max(len(groups), 1)
        self._available_columns = tuple()

        self._table_model = GroupedGuestTableModel(
            groups,
            self._grouped_filter_header_label(filter_kind),
            self._marked_filter_group_keys,
            self._on_filter_group_selection_changed,
        )
        self.table.setUpdatesEnabled(False)
        self.table.setModel(self._table_model)
        for logical_column in range(self._table_model.columnCount()):
            self.table.setItemDelegateForColumn(logical_column, QStyledItemDelegate(self.table))
            self.table.setColumnHidden(logical_column, False)
        self.table.setItemDelegateForColumn(0, CircleCheckDelegate(self.table))
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(0, 115)
        self.table.setColumnWidth(1, 280)
        self.table.setColumnWidth(2, 120)
        self.table.setUpdatesEnabled(True)
        self._position_table_send_button()
        self._update_filter_button_text(tuple())
        self._update_grouped_page_label(source_total_rows)
        self._update_actions()

    def _update_grouped_page_label(self, source_total_rows: int) -> None:
        label = self._grouped_filter_header_label(self._grouped_filter_kind or "")
        if self._total_rows == 0:
            self.page_label.setText(f"Nenhum grupo encontrado por {label}")
            return
        self.page_label.setText(
            f"Resumo por {label}: {self._total_rows} grupos | "
            f"{source_total_rows} registros analisados | Lista final: {self._selected_rows}"
        )

    def _is_grouped_filter_mode(self) -> bool:
        return isinstance(self._table_model, GroupedGuestTableModel)

    def _active_table_column_value_filters(self) -> dict[str, set[str]]:
        return self._table_column_value_filters_by_context.get(
            self._column_filter_context_key(),
            {},
        )

    def _set_table_column_value_filter(self, column_identifier: str, values: set[str] | None) -> None:
        context_key = self._column_filter_context_key()
        filters = dict(self._table_column_value_filters_by_context.get(context_key, {}))
        if values:
            filters[column_identifier] = values
        else:
            filters.pop(column_identifier, None)

        if filters:
            self._table_column_value_filters_by_context[context_key] = filters
        else:
            self._table_column_value_filters_by_context.pop(context_key, None)

    def _apply_table_column_value_filters(self, rows: list[GuestRowDTO]) -> list[GuestRowDTO]:
        filters = {
            column_identifier: values
            for column_identifier, values in self._active_table_column_value_filters().items()
            if column_identifier.startswith(("data:", "system:"))
        }
        if not filters:
            return rows

        return [
            row
            for row in rows
            if all(
                self._row_matches_column_value_filter(row, column_identifier, values)
                for column_identifier, values in filters.items()
            )
        ]

    def _apply_grouped_column_value_filters(self, groups: list[GuestGroupDTO]) -> list[GuestGroupDTO]:
        filters = {
            column_identifier: values
            for column_identifier, values in self._active_table_column_value_filters().items()
            if column_identifier.startswith("group:")
        }
        if not filters:
            return groups

        return [
            group
            for group in groups
            if all(
                bool(set(self._filter_values_for_group(group, column_identifier)).intersection(values))
                for column_identifier, values in filters.items()
            )
        ]

    def _row_matches_column_value_filter(
        self,
        row: GuestRowDTO,
        column_identifier: str,
        allowed_values: set[str],
    ) -> bool:
        return bool(set(self._filter_values_for_row(row, column_identifier)).intersection(allowed_values))

    def _filter_values_for_row(self, row: GuestRowDTO, column_identifier: str) -> list[str]:
        if column_identifier == "system:selection":
            if self._automatic_mode:
                invitation_status_labels = {
                    "sent": "E-mail enviado",
                    "waiting": "E-mail em aguardo",
                    "not_sent": "E-mail nao enviado",
                    "pending": FILTER_EMPTY_VALUE_LABEL,
                }
                return [
                    invitation_status_labels.get(
                        str(row.invitation_status or "").strip().casefold(),
                        FILTER_EMPTY_VALUE_LABEL,
                    )
                ]
            return ["Marcado" if row.selected or row.id in self._marked_guest_ids else "Nao marcado"]
        if column_identifier == "system:duplicate":
            return [self._format_duplicate_label(row) or FILTER_EMPTY_VALUE_LABEL]
        if column_identifier == "system:contact_tracking":
            status = str(row.contact_statuses.get("phone") or row.contact_statuses.get("mobile") or "").strip()
            status_labels = {
                "done": "Contato efetuado",
                "missed": "Nao atendeu",
                "not_done": "Contato nao efetuado",
            }
            return [status_labels.get(status, FILTER_EMPTY_VALUE_LABEL)]
        if column_identifier.startswith("data:"):
            column_name = column_identifier.split(":", 1)[1]
            return self._split_filter_cell_values(row.data.get(column_name, ""))
        return [FILTER_EMPTY_VALUE_LABEL]

    def _filter_values_for_group(self, group: GuestGroupDTO, column_identifier: str) -> list[str]:
        if column_identifier == "group:selection":
            return ["Marcado" if group.key in self._marked_filter_group_keys else "Nao marcado"]
        if column_identifier == "group:value":
            return [group.label or FILTER_EMPTY_VALUE_LABEL]
        if column_identifier == "group:quantity":
            return [str(group.quantity)]
        return [FILTER_EMPTY_VALUE_LABEL]

    def _split_filter_cell_values(self, value: object) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for item in str(value or "").replace("\r", "\n").split("\n"):
            clean_item = item.strip()
            normalized_item = self._normalize_dialog_text(clean_item)
            if not clean_item or normalized_item in seen:
                continue
            values.append(clean_item.upper())
            seen.add(normalized_item)
        return values or [FILTER_EMPTY_VALUE_LABEL]

    def _first_data_table_column(self) -> int | None:
        if self._table_model is None:
            return None
        for logical_column in range(self._table_model.columnCount()):
            if self._table_model.data_column_name(logical_column) is not None:
                return logical_column
        return None

    def _update_page_label(self) -> None:
        if self._total_rows == 0:
            if self._automatic_mode:
                message = "Lista final vazia"
            elif self._duplicates_mode:
                message = "Nenhum repetido encontrado"
            else:
                message = "Nenhum registro na lista"
            self.page_label.setText(message)
            return

        total_pages = max(ceil(self._total_rows / max(self._page_size, 1)), 1)
        if self._automatic_mode:
            context = f"Lista final: {self._total_rows} convidados"
        else:
            context = f"Lista unificada: {self._total_rows} registros | Lista final: {self._selected_rows}"
        if self._duplicates_mode:
            context = f"Possíveis repetidos: {self._total_rows} registros"
        self.page_label.setText(
            f"{context} | Página {self._current_page + 1} de {total_pages}"
        )

    def _normalize_page(self, page: int, total_rows: int, page_size: int) -> int:
        max_page_index = max(ceil(total_rows / max(page_size, 1)) - 1, 0)
        return min(page, max_page_index)

    def _on_row_selection_changed(self, guest_id: int, selected: bool) -> None:
        try:
            if selected:
                self._marked_guest_ids.add(guest_id)
                self.status_label.setText(
                    f"{len(self._marked_guest_ids)} registros marcados para envio."
                )
            else:
                row = self._table_rows_by_guest_id().get(guest_id)
                self._marked_guest_ids.discard(guest_id)
                if row is not None and row.selected:
                    self._view_model.set_guest_selected(guest_id, False)
                    self._refresh_automatic_tab_label()
                    self._load_table()
                    return
                self.status_label.setText(
                    f"{len(self._marked_guest_ids)} registros marcados para envio."
                )
            self._update_actions()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao selecionar", str(exc))

    def _on_filter_group_selection_changed(self, group_key: str, selected: bool) -> None:
        if selected:
            self._marked_filter_group_keys.add(group_key)
        else:
            self._marked_filter_group_keys.discard(group_key)

        self._rebuild_group_marked_guest_ids()
        if isinstance(self._table_model, GroupedGuestTableModel):
            self._table_model.refresh_selection_states()
        self.status_label.setText(f"{len(self._marked_guest_ids)} registros marcados para envio.")
        self._update_actions()

    def _rebuild_group_marked_guest_ids(self) -> None:
        if not self._grouped_filter_groups_by_key:
            return

        grouped_guest_ids = {
            row.id
            for group in self._grouped_filter_groups_by_key.values()
            for row in group.rows
        }
        self._marked_guest_ids.difference_update(grouped_guest_ids)

        for group_key in self._marked_filter_group_keys:
            group = self._grouped_filter_groups_by_key.get(group_key)
            if group is None:
                continue
            for row in group.rows:
                if row.selectable and not row.selected:
                    self._marked_guest_ids.add(row.id)

    def _select_guest_for_automatic(self, guest_id: int) -> int | None:
        selected_guest_id = guest_id
        if not self._automatic_mode:
            reviewed_guest_id = self._review_duplicate_selection(guest_id)
            if reviewed_guest_id is None:
                return None
            selected_guest_id = reviewed_guest_id
            if not self._confirm_automatic_conflicts(selected_guest_id):
                return None

        self._view_model.set_guest_selected(selected_guest_id, True)
        return selected_guest_id

    def _review_and_send_guest_batch(self, guest_ids: list[int]) -> bool:
        selected_guest_ids = self._show_batch_automatic_selection_dialog(guest_ids)
        if selected_guest_ids is None:
            return False

        unique_guest_ids = self._unique_guest_ids(selected_guest_ids)
        if not unique_guest_ids:
            QMessageBox.information(
                self,
                "Enviar para Planilha automática",
                "Nenhum registro foi marcado para envio.",
            )
            return False

        if not self._confirm_batch_automatic_conflicts(unique_guest_ids):
            return False

        self._marked_guest_ids.clear()
        self._marked_filter_group_keys.clear()
        updated_rows = self._view_model.set_page_selected(unique_guest_ids, True)
        self._refresh_automatic_tab_label()
        self.status_label.setText(f"{updated_rows} registros enviados para a Planilha automática.")
        self._load_table()
        return True

    def _show_batch_automatic_selection_dialog(self, guest_ids: list[int]) -> list[int] | None:
        source_rows = self._table_rows_by_guest_id()
        review_rows: list[dict[str, object]] = []

        for group_index, guest_id in enumerate(self._unique_guest_ids(guest_ids), start=1):
            candidates = self._view_model.list_duplicate_candidates(guest_id)
            if not candidates and guest_id in source_rows:
                candidates = [source_rows[guest_id]]
            if not candidates:
                continue

            has_duplicates = len(candidates) > 1
            primary_candidate = candidates[0]
            primary_name = self._guest_value_by_headers(primary_candidate, DIALOG_NAME_WORDS)
            group_label = f"{group_index} - {primary_name or primary_candidate.verification_code}"
            for candidate in candidates:
                review_rows.append(
                    {
                        "group": guest_id,
                        "item": group_index,
                        "group_label": group_label,
                        "row": candidate,
                        "checked": False,
                        "status": "Duplicidade encontrada" if has_duplicates else "Pronto para enviar",
                    }
                )

        if not review_rows:
            return []

        dialog = QDialog(self)
        dialog.setWindowTitle("Enviar para Planilha automática")
        dialog.resize(1480, 620)
        layout = QVBoxLayout(dialog)

        message = QLabel(
            "Revise os registros antes de enviar. Quando houver duplicidade, marque uma ou mais opções "
            "do mesmo item conforme precisar. Desmarque um item se não quiser enviá-lo agora."
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        filter_layout.addWidget(QLabel("Filtro"))

        review_filter_input = QLineEdit()
        review_filter_input.setPlaceholderText("Buscar por nome, telefone, e-mail, CEP, endereço ou código")
        review_filter_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        filter_layout.addWidget(review_filter_input, 1)

        review_group_filter = QComboBox()
        review_group_filter.addItem("Todos os itens", "all")
        review_group_filter.addItem("Somente duplicidades", "duplicates")
        group_labels: dict[int, str] = {}
        for review_row in review_rows:
            group_id = int(review_row["group"])
            group_labels.setdefault(group_id, str(review_row["group_label"]))
        for group_id, group_label in group_labels.items():
            review_group_filter.addItem(group_label, f"group:{group_id}")
        filter_layout.addWidget(review_group_filter)

        select_all_checkbox = QCheckBox("Selecionar todos")
        filter_layout.addWidget(select_all_checkbox)
        layout.addLayout(filter_layout)

        table = QTableWidget(len(review_rows), 11)
        table.setItemDelegateForColumn(0, CircleCheckDelegate(table))
        table.setHorizontalHeaderLabels(
            [
                "Enviar",
                "Item",
                "Situação",
                "Código",
                "Lista",
                "Nome",
                "Telefone",
                "Celular",
                "E-mail",
                "CEP",
                "Endereço",
            ]
        )
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setWordWrap(True)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)

        candidate_role = Qt.ItemDataRole.UserRole
        group_role = Qt.ItemDataRole.UserRole + 1

        table.blockSignals(True)
        for row_index, review_row in enumerate(review_rows):
            candidate = review_row["row"]
            values = [
                "",
                str(review_row["item"]),
                str(review_row["status"]),
                candidate.verification_code,
                candidate.sheet_name,
                self._guest_value_by_headers(candidate, DIALOG_NAME_WORDS),
                self._guest_phone_value(candidate),
                self._guest_mobile_value(candidate),
                self._guest_email_value(candidate),
                self._guest_cep_value(candidate),
                self._guest_address_value(candidate),
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                if column_index == 0:
                    item.setFlags(
                        Qt.ItemFlag.ItemIsEnabled
                        | Qt.ItemFlag.ItemIsSelectable
                        | Qt.ItemFlag.ItemIsUserCheckable
                    )
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if bool(review_row["checked"])
                        else Qt.CheckState.Unchecked
                    )
                    item.setData(candidate_role, candidate.id)
                    item.setData(group_role, review_row["group"])
                elif column_index == 2 and str(review_row["status"]).startswith("Duplicidade"):
                    item.setForeground(QBrush(QColor("#9a4d00")))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                table.setItem(row_index, column_index, item)
        table.blockSignals(False)

        layout.addWidget(table, 1)

        def apply_review_filters() -> None:
            search_text = review_filter_input.text().strip().casefold()
            selected_filter = str(review_group_filter.currentData())
            for table_row in range(table.rowCount()):
                review_row = review_rows[table_row]
                candidate = review_row["row"]
                row_text = " ".join(
                    str(table.item(table_row, column_index).text())
                    for column_index in range(table.columnCount())
                    if table.item(table_row, column_index) is not None
                ).casefold()
                matches_search = not search_text or search_text in row_text
                if selected_filter == "duplicates":
                    matches_filter = candidate.duplicate_count > 1
                elif selected_filter.startswith("group:"):
                    matches_filter = str(review_row["group"]) == selected_filter.split(":", 1)[1]
                else:
                    matches_filter = True
                table.setRowHidden(table_row, not (matches_search and matches_filter))

        def set_all_review_rows_checked(checked: bool) -> None:
            state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            table.blockSignals(True)
            for table_row in range(table.rowCount()):
                item = table.item(table_row, 0)
                if item is None:
                    continue
                item.setCheckState(state)
            table.blockSignals(False)
            table.viewport().update()
            update_select_all_checkbox()

        def update_select_all_checkbox() -> None:
            total_rows = table.rowCount()
            checked_rows = 0
            for table_row in range(total_rows):
                item = table.item(table_row, 0)
                if item is not None and item.checkState() == Qt.CheckState.Checked:
                    checked_rows += 1

            select_all_checkbox.blockSignals(True)
            select_all_checkbox.setChecked(total_rows > 0 and checked_rows == total_rows)
            select_all_checkbox.blockSignals(False)

        review_filter_input.textChanged.connect(apply_review_filters)
        review_group_filter.currentIndexChanged.connect(apply_review_filters)
        select_all_checkbox.toggled.connect(set_all_review_rows_checked)
        table.itemChanged.connect(lambda _item: update_select_all_checkbox())
        update_select_all_checkbox()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText("Enviar marcados")
        if cancel_button is not None:
            cancel_button.setText("Cancelar")

        def checked_candidate_ids() -> list[int]:
            selected_ids: list[int] = []
            for table_row in range(table.rowCount()):
                item = table.item(table_row, 0)
                if item is None or item.checkState() != Qt.CheckState.Checked:
                    continue
                selected_ids.append(int(item.data(candidate_role)))
            return selected_ids

        def accept_if_valid() -> None:
            if not checked_candidate_ids():
                QMessageBox.information(
                    dialog,
                    "Enviar para Planilha automática",
                    "Marque pelo menos um registro para enviar.",
                )
                return
            dialog.accept()

        buttons.accepted.connect(accept_if_valid)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        table.setColumnWidth(0, 70)
        table.setColumnWidth(1, 60)
        table.setColumnWidth(2, 150)
        table.setColumnWidth(3, 90)
        table.setColumnWidth(4, 140)
        table.setColumnWidth(5, 240)
        table.setColumnWidth(6, 130)
        table.setColumnWidth(7, 130)
        table.setColumnWidth(8, 190)
        table.setColumnWidth(9, 110)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return checked_candidate_ids()

    def _show_filter_group_detail_dialog(self, group: GuestGroupDTO) -> None:
        rows = list(group.rows)
        if not rows:
            return

        columns = self._grouped_filter_source_columns
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{self._grouped_filter_header_label(self._grouped_filter_kind or '')}: {group.label}")
        dialog.resize(1500, 650)
        layout = QVBoxLayout(dialog)

        message = QLabel("Marque os contatos deste grupo que deseja enviar para a Planilha automatica.")
        message.setWordWrap(True)
        layout.addWidget(message)

        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        filter_layout.addWidget(QLabel("Filtro"))

        search_input = QLineEdit(dialog)
        search_input.setPlaceholderText("Buscar dentro deste grupo")
        search_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        filter_layout.addWidget(search_input, 1)

        select_all_checkbox = QCheckBox("Selecionar visiveis", dialog)
        filter_layout.addWidget(select_all_checkbox)
        layout.addLayout(filter_layout)

        headers = ["Enviar", "Situacao", *columns]
        table = QTableWidget(len(rows), len(headers), dialog)
        table.setItemDelegateForColumn(0, CircleCheckDelegate(table))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setWordWrap(True)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)

        guest_id_role = Qt.ItemDataRole.UserRole
        selectable_role = Qt.ItemDataRole.UserRole + 1

        table.blockSignals(True)
        for row_index, row in enumerate(rows):
            can_send = row.selectable and not row.selected
            status = "Pronto para enviar" if can_send else "Ja esta na lista final"
            values = ["", status]
            values.extend(str(row.data.get(column_name, "")) for column_name in columns)

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                if column_index == 0:
                    flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                    if can_send:
                        flags |= Qt.ItemFlag.ItemIsUserCheckable
                    item.setFlags(flags)
                    item.setCheckState(Qt.CheckState.Unchecked)
                    item.setData(guest_id_role, row.id)
                    item.setData(selectable_role, can_send)
                elif column_index == 1 and not can_send:
                    item.setForeground(QBrush(QColor("#64748b")))
                table.setItem(row_index, column_index, item)
        table.blockSignals(False)
        layout.addWidget(table, 1)

        def row_matches_search(table_row: int, search_text: str) -> bool:
            if not search_text:
                return True
            row_text = " ".join(
                str(table.item(table_row, column_index).text())
                for column_index in range(table.columnCount())
                if table.item(table_row, column_index) is not None
            ).casefold()
            return search_text in row_text

        def apply_group_filter() -> None:
            search_text = search_input.text().strip().casefold()
            for table_row in range(table.rowCount()):
                table.setRowHidden(table_row, not row_matches_search(table_row, search_text))
            update_select_all_checkbox()

        def set_visible_rows_checked(checked: bool) -> None:
            state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            table.blockSignals(True)
            for table_row in range(table.rowCount()):
                if table.isRowHidden(table_row):
                    continue
                item = table.item(table_row, 0)
                if item is None or not bool(item.data(selectable_role)):
                    continue
                item.setCheckState(state)
            table.blockSignals(False)
            table.viewport().update()
            update_select_all_checkbox()

        def update_select_all_checkbox() -> None:
            visible_selectable_rows = 0
            checked_rows = 0
            for table_row in range(table.rowCount()):
                if table.isRowHidden(table_row):
                    continue
                item = table.item(table_row, 0)
                if item is None or not bool(item.data(selectable_role)):
                    continue
                visible_selectable_rows += 1
                if item.checkState() == Qt.CheckState.Checked:
                    checked_rows += 1

            select_all_checkbox.blockSignals(True)
            select_all_checkbox.setChecked(
                visible_selectable_rows > 0 and checked_rows == visible_selectable_rows
            )
            select_all_checkbox.blockSignals(False)

        def checked_guest_ids() -> list[int]:
            guest_ids: list[int] = []
            for table_row in range(table.rowCount()):
                item = table.item(table_row, 0)
                if (
                    item is None
                    or not bool(item.data(selectable_role))
                    or item.checkState() != Qt.CheckState.Checked
                ):
                    continue
                guest_ids.append(int(item.data(guest_id_role)))
            return guest_ids

        search_input.textChanged.connect(apply_group_filter)
        select_all_checkbox.toggled.connect(set_visible_rows_checked)
        table.itemChanged.connect(lambda _item: update_select_all_checkbox())
        update_select_all_checkbox()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText("Enviar marcados")
        if cancel_button is not None:
            cancel_button.setText("Cancelar")

        def accept_if_valid() -> None:
            if not checked_guest_ids():
                QMessageBox.information(
                    dialog,
                    "Enviar grupo",
                    "Marque pelo menos um contato para enviar.",
                )
                return
            dialog.accept()

        buttons.accepted.connect(accept_if_valid)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        table.setColumnWidth(0, 76)
        table.setColumnWidth(1, 150)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._send_filter_group_guest_ids(checked_guest_ids())

    def _send_filter_group_guest_ids(self, guest_ids: list[int]) -> None:
        unique_guest_ids = self._unique_guest_ids(guest_ids)
        if not unique_guest_ids:
            return
        if not self._confirm_batch_automatic_conflicts(unique_guest_ids):
            return

        try:
            updated_rows = self._view_model.set_page_selected(unique_guest_ids, True)
            self._marked_guest_ids.difference_update(unique_guest_ids)
            self._marked_filter_group_keys.clear()
            self._refresh_automatic_tab_label()
            self.status_label.setText(f"{updated_rows} registros enviados para a Planilha automatica.")
            self._load_table()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao enviar grupo", str(exc))

    def _confirm_batch_automatic_conflicts(self, guest_ids: list[int]) -> bool:
        conflicts: list[GuestRowDTO] = []
        seen: set[int] = set()
        for guest_id in guest_ids:
            for conflict in self._view_model.list_automatic_conflicts(guest_id):
                if conflict.id in seen:
                    continue
                conflicts.append(conflict)
                seen.add(conflict.id)

        if not conflicts:
            return True

        selected_candidate = self._show_guest_review_dialog(
            title="Conferir Planilha automática",
            message=(
                "Já existem dados parecidos na Planilha automática. "
                "Confira os registros abaixo antes de adicionar o lote."
            ),
            rows=conflicts,
            accept_text="Adicionar lote mesmo assim",
            cancel_text="Cancelar",
            selectable=False,
        )
        return selected_candidate is not None

    def _highlighted_guest_ids_for_batch(self, current_guest_id: int) -> list[int]:
        if (
            self._table_model is None
            or self.table.selectionModel() is None
            or self._automatic_mode
            or self._duplicates_mode
            or not self._current_sheet_selectable
        ):
            return [current_guest_id]

        row_indexes = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        guest_ids: list[int] = []
        seen: set[int] = set()
        for row_index in row_indexes:
            row = self._table_model.row_at(row_index)
            if row is None or not row.selectable or row.id in seen:
                continue
            if row.id != current_guest_id and row.selected:
                continue
            guest_ids.append(row.id)
            seen.add(row.id)

        if current_guest_id not in seen:
            guest_ids.append(current_guest_id)
        return guest_ids

    def _table_rows_by_guest_id(self) -> dict[int, GuestRowDTO]:
        if self._table_model is None:
            return {}

        if isinstance(self._table_model, GroupedGuestTableModel):
            return {
                row.id: row
                for row in self._table_model.all_guest_rows()
            }

        rows: dict[int, GuestRowDTO] = {}
        for row_index in range(self._table_model.rowCount()):
            row = self._table_model.row_at(row_index)
            if row is not None:
                rows[row.id] = row
        return rows

    def _unique_guest_ids(self, guest_ids: list[int]) -> list[int]:
        unique_guest_ids: list[int] = []
        seen: set[int] = set()
        for guest_id in guest_ids:
            if guest_id in seen:
                continue
            unique_guest_ids.append(guest_id)
            seen.add(guest_id)
        return unique_guest_ids

    def _review_duplicate_selection(self, guest_id: int) -> int | None:
        candidates = self._view_model.list_duplicate_candidates(guest_id)
        if len(candidates) <= 1:
            return guest_id

        selected_candidate = self._show_guest_review_dialog(
            title="Duplicidade encontrada",
            message="Encontrei registros parecidos. Selecione qual deve ir para a Planilha automática.",
            rows=candidates,
            accept_text="Enviar selecionado",
            cancel_text="Cancelar",
            selectable=True,
        )
        if selected_candidate is None:
            return None
        return selected_candidate

    def _confirm_automatic_conflicts(self, guest_id: int) -> bool:
        conflicts = self._view_model.list_automatic_conflicts(guest_id)
        if not conflicts:
            return True

        selected_candidate = self._show_guest_review_dialog(
            title="Conferir Planilha automática",
            message=(
                "Já existem dados parecidos na Planilha automática. "
                "Confira nome, telefone, celular, e-mail, CEP e endereço antes de adicionar."
            ),
            rows=conflicts,
            accept_text="Adicionar mesmo assim",
            cancel_text="Cancelar",
            selectable=False,
        )
        return selected_candidate is not None

    def _show_duplicate_candidates_for_row(self, row_index: int) -> None:
        if self._table_model is None:
            return
        row = self._table_model.row_at(row_index)
        if row is None or row.duplicate_count <= 1:
            self.status_label.setText("Esta linha não possui duplicidade identificada.")
            return

        candidates = self._view_model.list_duplicate_candidates(row.id)
        if len(candidates) <= 1:
            self.status_label.setText("Nenhuma duplicidade encontrada para esta linha.")
            return

        self._show_guest_review_dialog(
            title="Duplicidades da linha",
            message="Registros parecidos encontrados para esta linha.",
            rows=candidates,
            accept_text="Fechar",
            cancel_text="",
            selectable=False,
        )

    def _show_guest_review_dialog(
        self,
        title: str,
        message: str,
        rows: list[GuestRowDTO],
        accept_text: str,
        cancel_text: str,
        selectable: bool,
    ) -> int | None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(1320, 520)
        layout = QVBoxLayout(dialog)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        table = self._build_guest_review_table(rows)
        layout.addWidget(table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        if cancel_text:
            buttons.addButton(QDialogButtonBox.StandardButton.Cancel)

        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText(accept_text)
        if cancel_button is not None:
            cancel_button.setText(cancel_text)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if selectable:
            table.itemDoubleClicked.connect(lambda _: dialog.accept())

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        if not selectable:
            return rows[0].id if rows else 0

        selected_ranges = table.selectedRanges()
        if not selected_ranges:
            return None
        selected_row = selected_ranges[0].topRow()
        item = table.item(selected_row, 0)
        if item is None:
            return None
        return int(item.data(Qt.ItemDataRole.UserRole))

    def _build_guest_review_table(self, rows: list[GuestRowDTO]) -> QTableWidget:
        table = QTableWidget(len(rows), 9)
        table.setHorizontalHeaderLabels(
            ["Código", "Duplicidade", "Lista", "Nome", "Telefone", "Celular", "E-mail", "CEP", "Endereço"]
        )
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setWordWrap(True)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)

        for row_index, row in enumerate(rows):
            values = [
                row.verification_code,
                self._format_duplicate_label(row),
                row.sheet_name,
                self._guest_value_by_headers(row, DIALOG_NAME_WORDS),
                self._guest_phone_value(row),
                self._guest_mobile_value(row),
                self._guest_email_value(row),
                self._guest_cep_value(row),
                self._guest_address_value(row),
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row.id)
                if column_index == 1 and row.duplicate_count > 1:
                    item.setForeground(QBrush(QColor("#9a4d00")))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                item.setToolTip(str(value))
                table.setItem(row_index, column_index, item)

        if rows:
            table.selectRow(0)
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        table.setColumnWidth(0, 90)
        table.setColumnWidth(1, 120)
        table.setColumnWidth(2, 140)
        table.setColumnWidth(3, 240)
        table.setColumnWidth(4, 130)
        table.setColumnWidth(5, 130)
        table.setColumnWidth(6, 190)
        table.setColumnWidth(7, 120)
        table.setMinimumHeight(300)
        return table

    def _format_duplicate_label(self, row: GuestRowDTO) -> str:
        if row.duplicate_count <= 1:
            return ""
        return f"{row.duplicate_reason} ({row.duplicate_count})"

    def _guest_value_by_headers(self, row: GuestRowDTO, header_words: tuple[str, ...]) -> str:
        normalized_words = {self._normalize_dialog_text(word) for word in header_words}
        for column_name, value in row.data.items():
            normalized_column = self._normalize_dialog_text(column_name)
            clean_value = str(value).strip()
            if clean_value and any(word and word in normalized_column for word in normalized_words):
                return clean_value
        return ""

    def _guest_phone_value(self, row: GuestRowDTO) -> str:
        return self._guest_phone_value_by_kind(row, "phone")

    def _guest_mobile_value(self, row: GuestRowDTO) -> str:
        return self._guest_phone_value_by_kind(row, "mobile")

    def _guest_phone_value_by_kind(self, row: GuestRowDTO, expected_kind: str) -> str:
        values: list[str] = []
        for _, candidate in self._dialog_phone_source_items(row, expected_kind):
            for phone in DIALOG_PHONE_PATTERN.findall(str(candidate)):
                if self._dialog_phone_kind(phone) == expected_kind:
                    self._append_unique_dialog_value(values, phone, digits_only=True)
        return "\n".join(values)

    def _guest_email_value(self, row: GuestRowDTO) -> str:
        values: list[str] = []
        for candidate in row.data.values():
            for email in DIALOG_EMAIL_PATTERN.findall(str(candidate)):
                self._append_unique_dialog_value(values, email)
        return "\n".join(values)

    def _guest_cep_value(self, row: GuestRowDTO) -> str:
        for column_name, candidate in row.data.items():
            if not self._dialog_column_matches(column_name, DIALOG_CEP_WORDS):
                continue
            match = DIALOG_CEP_PATTERN.search(str(candidate))
            if match:
                return match.group(0)
        return ""

    def _guest_address_value(self, row: GuestRowDTO) -> str:
        return self._guest_value_by_headers(row, DIALOG_ADDRESS_WORDS)

    def _dialog_phone_kind(self, value: str) -> str:
        digits = re.sub(r"\D+", "", value)
        if digits.startswith("55") and len(digits) > 11:
            digits = digits[2:]
        local_number = digits[-9:] if len(digits) in (9, 11) else digits[-8:]
        if len(local_number) == 9 and local_number.startswith("9"):
            return "mobile"
        if len(local_number) == 8 and local_number.startswith(("7", "8", "9")):
            return "mobile"
        return "phone"

    def _append_unique_dialog_value(
        self,
        values: list[str],
        value: str,
        digits_only: bool = False,
    ) -> None:
        clean_value = str(value).strip()
        if not clean_value:
            return
        if digits_only:
            normalized_value = re.sub(r"\D+", "", clean_value)
            existing_values = {re.sub(r"\D+", "", item) for item in values}
        else:
            normalized_value = clean_value.casefold()
            existing_values = {item.casefold() for item in values}
        if normalized_value in existing_values:
            return
        values.append(clean_value)

    def _dialog_column_matches(self, column_name: str, header_words: tuple[str, ...]) -> bool:
        normalized_column = self._normalize_dialog_text(column_name)
        return any(self._normalize_dialog_text(word) in normalized_column for word in header_words)

    def _dialog_phone_source_items(self, row: GuestRowDTO, expected_kind: str) -> list[tuple[str, str]]:
        header_words = DIALOG_MOBILE_WORDS if expected_kind == "mobile" else DIALOG_PHONE_WORDS
        explicit_items = [
            (column_name, str(value))
            for column_name, value in row.data.items()
            if self._dialog_column_matches(column_name, header_words)
        ]
        if explicit_items:
            return explicit_items

        return [
            (column_name, str(value))
            for column_name, value in row.data.items()
            if self._dialog_generic_contact_column(column_name)
        ]

    def _dialog_generic_contact_column(self, column_name: str) -> bool:
        normalized_column = self._normalize_dialog_text(column_name)
        non_contact_words = {self._normalize_dialog_text(word) for word in DIALOG_NON_CONTACT_WORDS}
        if any(word and word in normalized_column for word in non_contact_words):
            return False
        contact_words = {self._normalize_dialog_text(word) for word in DIALOG_GENERIC_CONTACT_WORDS}
        return any(word and word in normalized_column for word in contact_words)

    def _normalize_dialog_text(self, value: str) -> str:
        normalized = normalize("NFD", str(value).casefold())
        return "".join(character for character in normalized if not combining(character))

    def _on_cell_changed(self, guest_id: int, column_name: str, value: str) -> bool:
        try:
            self._view_model.update_guest_data(
                guest_id,
                column_name,
                value,
                automatic=self._automatic_mode,
            )
            self.status_label.setText("Dado atualizado.")
            if not self._automatic_mode:
                self._update_duplicates_button()
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao editar", str(exc))
            return False

    def _on_invitation_status_changed(self, guest_id: int, status: str) -> bool:
        try:
            self._view_model.set_automatic_guest_status(guest_id, status)
            messages = {
                "sent": "E-mail marcado como enviado.",
                "waiting": "E-mail marcado em aguardo.",
                "not_sent": "E-mail marcado como nao enviado.",
            }
            message = messages.get(status, "Status do e-mail atualizado.")
            self.status_label.setText(message)
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao atualizar convite", str(exc))
            return False

    def _on_contact_status_changed(self, guest_id: int, channel: str, status: str) -> bool:
        try:
            self._view_model.set_automatic_contact_status(guest_id, channel, status)
            messages = {
                ("call", "done"): "Tel/Cel marcado como contato efetuado.",
                ("call", "missed"): "Tel/Cel marcado como não atendido.",
                ("call", "not_done"): "Tel/Cel marcado como contato não efetuado.",
                ("call", ""): "Tel/Cel limpo.",
                ("phone", "done"): "Telefone marcado como contato efetuado.",
                ("phone", "not_done"): "Telefone marcado como contato não efetuado.",
                ("phone", ""): "Telefone limpo.",
                ("mobile", "done"): "Celular marcado como contato efetuado.",
                ("mobile", "not_done"): "Celular marcado como contato não efetuado.",
                ("mobile", ""): "Celular limpo.",
                ("email", "done"): "E-mail marcado como enviado.",
                ("email", "not_done"): "E-mail marcado como não enviado.",
                ("email", ""): "E-mail limpo.",
            }
            self.status_label.setText(messages.get((channel, status), "Acompanhamento atualizado."))
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao atualizar acompanhamento", str(exc))
            return False

    def _remove_guest_from_automatic(self, guest_id: int) -> bool:
        try:
            self._view_model.set_guest_selected(guest_id, False)
            self._refresh_automatic_tab_label()
            self.status_label.setText("Convidado removido da Planilha automÃ¡tica.")
            self._load_table()
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao remover convidado", str(exc))
            return False

    def _on_table_clicked(self, index: QModelIndex) -> None:
        if not index.isValid() or self._table_model is None:
            return
        if self._is_grouped_filter_mode():
            return
        column_identifier = self._table_model.column_identifier(index.column())
        if column_identifier in {"system:selection", "system:contact_tracking"}:
            return
        if column_identifier == "system:duplicate":
            self._show_duplicate_candidates_for_row(index.row())

    def _on_table_double_clicked(self, index: QModelIndex) -> None:
        if not index.isValid() or not isinstance(self._table_model, GroupedGuestTableModel):
            return

        column_identifier = self._table_model.column_identifier(index.column())
        if column_identifier not in {"group:value", "group:quantity"}:
            return

        group = self._table_model.group_at(index.row())
        if group is None:
            return
        self._show_filter_group_detail_dialog(group)

    def _show_table_context_menu(self, position: object) -> None:
        if self._table_model is None:
            return

        index = self.table.indexAt(position)
        if not index.isValid():
            return

        if self.table.selectionModel() is not None and not self.table.selectionModel().isSelected(index):
            self.table.selectRow(index.row())

        if isinstance(self._table_model, GroupedGuestTableModel):
            group = self._table_model.group_at(index.row())
            if group is None:
                return
            menu = QMenu(self)
            open_action = menu.addAction("Visualizar contatos do grupo")
            send_action = menu.addAction("Enviar grupos selecionados para a Planilha automatica")
            send_action.setEnabled(bool(self._selected_table_guest_ids(selected_state=False)))
            selected_action = menu.exec(self.table.viewport().mapToGlobal(position))
            if selected_action == open_action:
                self._show_filter_group_detail_dialog(group)
            elif selected_action == send_action:
                self._send_highlighted_rows_to_automatic()
            return

        menu = QMenu(self)
        row = self._table_model.row_at(index.row())
        if row is not None and row.duplicate_count > 1:
            view_duplicates_action = menu.addAction("Ver duplicidades da linha")
            menu.addSeparator()
        else:
            view_duplicates_action = None

        can_send = (
            self._current_sheet_selectable
            and not self._automatic_mode
            and not self._duplicates_mode
            and bool(self._selected_table_guest_ids(selected_state=False))
        )
        can_remove = bool(self._selected_table_guest_ids(selected_state=True))
        send_action = menu.addAction("Enviar linhas selecionadas para a Planilha automática")
        send_action.setEnabled(can_send)
        remove_action = menu.addAction("Remover linhas selecionadas da Planilha automática")
        remove_action.setEnabled(can_remove)

        selected_action = menu.exec(self.table.viewport().mapToGlobal(position))
        if view_duplicates_action is not None and selected_action == view_duplicates_action:
            self._show_duplicate_candidates_for_row(index.row())
        elif selected_action == send_action:
            self._send_highlighted_rows_to_automatic()
        elif selected_action == remove_action:
            self._clear_highlighted_rows_from_automatic()

    def _show_table_header_filter_menu(self, logical_column: int) -> None:
        if self._table_model is None or logical_column < 0:
            return
        if self.table.horizontalHeader().isSectionHidden(logical_column):
            return

        column_identifier = self._table_model.column_identifier(logical_column)
        if not column_identifier:
            return

        available_values = self._filter_values_for_table_column(logical_column, column_identifier)
        active_values = set(self._active_table_column_value_filters().get(column_identifier, set()))
        available_values.update(active_values)
        values = sorted(available_values, key=self._filter_value_sort_key)
        if not values:
            values = [FILTER_EMPTY_VALUE_LABEL]

        header_label = str(
            self._table_model.headerData(
                logical_column,
                Qt.Orientation.Horizontal,
                Qt.ItemDataRole.DisplayRole,
            )
            or ""
        ).replace("\u25be", "").strip()

        menu = QMenu(self)
        container = QWidget(menu)
        container.setMinimumWidth(320)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        label = QLabel(f"Filtrar {header_label}", container)
        label.setObjectName("SmallLabel")
        layout.addWidget(label)

        search_input = QLineEdit(container)
        search_input.setPlaceholderText("Buscar valor neste filtro")
        layout.addWidget(search_input)

        value_list = QListWidget(container)
        value_list.setMinimumHeight(210)
        value_list.setMaximumHeight(320)
        checked_values = active_values or set(values)
        for value in values:
            item = QListWidgetItem(value)
            item.setData(Qt.ItemDataRole.UserRole, value)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if value in checked_values
                else Qt.CheckState.Unchecked
            )
            value_list.addItem(item)
        layout.addWidget(value_list)

        def apply_value_search() -> None:
            search_text = self._normalize_dialog_text(search_input.text())
            for item_index in range(value_list.count()):
                item = value_list.item(item_index)
                item_text = self._normalize_dialog_text(item.text())
                item.setHidden(bool(search_text) and search_text not in item_text)

        quick_buttons_layout = QHBoxLayout()
        quick_buttons_layout.setContentsMargins(0, 0, 0, 0)
        quick_buttons_layout.setSpacing(8)
        check_all_button = QPushButton("Marcar todos", container)
        uncheck_all_button = QPushButton("Desmarcar todos", container)
        quick_buttons_layout.addWidget(check_all_button)
        quick_buttons_layout.addWidget(uncheck_all_button)
        quick_buttons_layout.addStretch(1)
        layout.addLayout(quick_buttons_layout)

        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(8)
        clear_filter_button = QPushButton("Limpar filtro", container)
        cancel_button = QPushButton("Cancelar", container)
        apply_button = QPushButton("Aplicar", container)
        apply_button.setDefault(True)
        buttons_layout.addWidget(clear_filter_button)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(cancel_button)
        buttons_layout.addWidget(apply_button)
        layout.addLayout(buttons_layout)

        widget_action = QWidgetAction(menu)
        widget_action.setDefaultWidget(container)
        menu.addAction(widget_action)

        check_all_button.clicked.connect(lambda: self._set_all_filter_value_items_checked(value_list, True))
        uncheck_all_button.clicked.connect(lambda: self._set_all_filter_value_items_checked(value_list, False))
        search_input.textChanged.connect(apply_value_search)
        clear_filter_button.clicked.connect(lambda: self._clear_table_header_filter(column_identifier, menu))
        cancel_button.clicked.connect(menu.close)
        apply_button.clicked.connect(
            lambda: self._apply_table_header_filter(column_identifier, values, value_list, menu)
        )

        header = self.table.horizontalHeader()
        section_x = header.sectionViewportPosition(logical_column)
        position = header.mapToGlobal(header.rect().topLeft())
        position.setX(position.x() + max(section_x, 0))
        position.setY(position.y() + header.height())
        menu.exec(position)

    def _filter_values_for_table_column(self, logical_column: int, column_identifier: str) -> set[str]:
        values: set[str] = set()
        if isinstance(self._table_model, GroupedGuestTableModel):
            for row_index in range(self._table_model.rowCount()):
                group = self._table_model.group_at(row_index)
                if group is None:
                    continue
                values.update(self._filter_values_for_group(group, column_identifier))
            return values

        if not isinstance(self._table_model, GuestTableModel):
            return values

        for row_index in range(self._table_model.rowCount()):
            row = self._table_model.row_at(row_index)
            if row is None:
                continue
            values.update(self._filter_values_for_row(row, column_identifier))
        return values

    def _filter_value_sort_key(self, value: str) -> tuple[int, str]:
        return (1 if value == FILTER_EMPTY_VALUE_LABEL else 0, self._normalize_dialog_text(value))

    def _set_all_filter_value_items_checked(self, value_list: QListWidget, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for index in range(value_list.count()):
            item = value_list.item(index)
            if item.isHidden():
                continue
            item.setCheckState(state)

    def _clear_table_header_filter(self, column_identifier: str, menu: QMenu) -> None:
        self._set_table_column_value_filter(column_identifier, None)
        menu.close()
        self._current_page = 0
        self._load_table()

    def _apply_table_header_filter(
        self,
        column_identifier: str,
        all_values: list[str],
        value_list: QListWidget,
        menu: QMenu,
    ) -> None:
        selected_values = {
            str(value_list.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(value_list.count())
            if value_list.item(index).checkState() == Qt.CheckState.Checked
        }
        if not selected_values:
            QMessageBox.information(
                self,
                "Filtro da coluna",
                "Marque pelo menos um valor para aplicar o filtro.",
            )
            return

        if selected_values == set(all_values):
            self._set_table_column_value_filter(column_identifier, None)
        else:
            self._set_table_column_value_filter(column_identifier, selected_values)
        menu.close()
        self._marked_guest_ids.clear()
        self._current_page = 0
        self._load_table()

    def _show_table_header_context_menu(self, position: object) -> None:
        if self._table_model is None:
            return
        if self._is_grouped_filter_mode():
            return

        header = self.table.horizontalHeader()
        logical_column = header.logicalIndexAt(position)
        if logical_column < 0:
            return

        data_column = self._table_model.data_column_name(logical_column)
        header_label = str(
            self._table_model.headerData(
                logical_column,
                Qt.Orientation.Horizontal,
                Qt.ItemDataRole.DisplayRole,
            )
            or ""
        )

        menu = QMenu(self)
        column_identifier = self._table_model.column_identifier(logical_column)
        can_hide_system_column = column_identifier == "system:duplicate"
        if data_column is None and not can_hide_system_column:
            hide_action = menu.addAction("Coluna fixa do sistema")
            hide_action.setEnabled(False)
        else:
            hide_action = menu.addAction(f"Excluir coluna '{header_label}' da visualização")
        restore_action = menu.addAction("Restaurar colunas ocultas")
        restore_action.setEnabled(self._has_hidden_table_columns())

        selected_action = menu.exec(header.mapToGlobal(position))
        if data_column is not None and selected_action == hide_action:
            self._hide_table_data_column(data_column, header_label)
        elif can_hide_system_column and selected_action == hide_action:
            self._hide_table_system_column(column_identifier, header_label)
        elif selected_action == restore_action:
            self._restore_hidden_table_columns()

    def _hide_table_data_column(self, column_name: str, header_label: str) -> None:
        if not self._available_columns:
            return

        context_key = self._column_filter_context_key()
        visible_columns = self._visible_columns_for_current_context(self._available_columns)
        if column_name not in visible_columns:
            return
        if len(visible_columns) <= 1:
            QMessageBox.warning(
                self,
                "Coluna da tabela",
                "A tabela precisa manter pelo menos uma coluna visível.",
            )
            return

        visible_columns.discard(column_name)
        self._visible_columns_by_context[context_key] = visible_columns
        self.status_label.setText(f"Coluna '{header_label}' removida da visualização.")
        self._load_table()

    def _hide_table_system_column(self, column_identifier: str, header_label: str) -> None:
        context_key = self._column_filter_context_key()
        hidden_columns = set(self._hidden_system_columns_by_context.get(context_key, set()))
        hidden_columns.add(column_identifier)
        self._hidden_system_columns_by_context[context_key] = hidden_columns
        self.status_label.setText(f"Coluna '{header_label}' removida da visualização.")
        self._load_table()

    def _restore_hidden_table_columns(self) -> None:
        context_key = self._column_filter_context_key()
        self._visible_columns_by_context.pop(context_key, None)
        self._hidden_system_columns_by_context.pop(context_key, None)
        self.status_label.setText("Colunas restauradas.")
        self._load_table()

    def _create_column(self) -> None:
        if self._duplicates_mode:
            QMessageBox.information(
                self,
                "Criar coluna",
                "A visualização de possíveis repetidos é apenas para conferência.",
            )
            return
        if not self._automatic_mode and self._current_workbook_id is None:
            QMessageBox.information(
                self,
                "Criar coluna",
                "Importe ou abra uma planilha antes de criar uma coluna.",
            )
            return

        column_name, accepted = QInputDialog.getText(
            self,
            "Criar coluna",
            "Nome da nova coluna:",
        )
        if not accepted:
            return

        clean_column_name = str(column_name or "").strip()
        if not clean_column_name:
            return

        if self._visible_column_exists(clean_column_name):
            QMessageBox.information(
                self,
                "Criar coluna",
                f"A coluna '{clean_column_name}' já existe na tabela atual.",
            )
            return

        context_key = self._column_filter_context_key()
        try:
            updated_lists = self._view_model.create_column(
                clean_column_name,
                import_id=None if self._automatic_mode else self._current_import_id,
                workbook_id=None if self._automatic_mode else self._current_workbook_id,
                automatic=self._automatic_mode,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao criar coluna", str(exc))
            return

        self._remember_forced_visible_column(context_key, clean_column_name)
        if context_key in self._visible_columns_by_context:
            self._visible_columns_by_context[context_key].add(clean_column_name)
        self.status_label.setText(f"Coluna '{clean_column_name}' criada em {updated_lists} lista(s).")
        self._load_table()

    def _visible_column_exists(self, column_name: str) -> bool:
        normalized_target = self._normalize_dialog_text(column_name)
        visible_columns = set(self._available_columns)
        if self._table_model is not None:
            for logical_column in range(self._table_model.columnCount()):
                data_column = self._table_model.data_column_name(logical_column)
                if data_column:
                    visible_columns.add(data_column)
        return any(self._normalize_dialog_text(column) == normalized_target for column in visible_columns)

    def _remember_forced_visible_column(self, context_key: str, column_name: str) -> None:
        forced_columns = self._forced_visible_columns_by_context.setdefault(context_key, [])
        if not any(
            self._normalize_dialog_text(existing_column) == self._normalize_dialog_text(column_name)
            for existing_column in forced_columns
        ):
            forced_columns.append(column_name)

    def _include_forced_visible_columns(
        self,
        rows: list[GuestRowDTO],
        columns: tuple[str, ...],
        editable_columns: tuple[str, ...],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        forced_columns = self._forced_visible_columns_by_context.get(self._column_filter_context_key(), [])
        if not forced_columns:
            return columns, editable_columns

        next_columns = list(columns)
        next_editable_columns = list(editable_columns)
        normalized_columns = {self._normalize_dialog_text(column) for column in next_columns}
        normalized_editable_columns = {self._normalize_dialog_text(column) for column in next_editable_columns}

        for column_name in forced_columns:
            normalized_column = self._normalize_dialog_text(column_name)
            if normalized_column not in normalized_columns:
                next_columns.append(column_name)
                normalized_columns.add(normalized_column)
            if normalized_column not in normalized_editable_columns:
                next_editable_columns.append(column_name)
                normalized_editable_columns.add(normalized_column)
            for row in rows:
                row.data.setdefault(column_name, "")

        return tuple(next_columns), tuple(next_editable_columns)

    def _order_columns_for_display(
        self,
        columns: tuple[str, ...],
        editable_columns: tuple[str, ...],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        ordered_columns = tuple(
            sorted(
                columns,
                key=lambda column_name: self._column_display_sort_key(column_name, columns.index(column_name)),
            )
        )
        editable_set = set(editable_columns)
        ordered_editable_columns = tuple(
            column_name
            for column_name in ordered_columns
            if column_name in editable_set
        )
        return ordered_columns, ordered_editable_columns

    def _column_display_sort_key(self, column_name: str, original_index: int) -> tuple[int, int, str]:
        normalized_column = self._normalize_dialog_text(column_name)
        for priority_index, words in enumerate(COLUMN_DISPLAY_PRIORITY_WORDS):
            if any(word and word in normalized_column for word in words):
                return priority_index, original_index, normalized_column
        return len(COLUMN_DISPLAY_PRIORITY_WORDS), original_index, normalized_column

    def _apply_default_table_column_widths(self) -> None:
        if self._table_model is None or self._is_grouped_filter_mode():
            return

        for logical_column in range(self._table_model.columnCount()):
            data_column = self._table_model.data_column_name(logical_column)
            if not data_column:
                continue
            width = self._default_data_column_width(data_column)
            if width is not None:
                self.table.setColumnWidth(logical_column, width)

    def _default_data_column_width(self, column_name: str) -> int | None:
        normalized_column = self._normalize_dialog_text(column_name)
        width_rules = (
            (("lista",), 150),
            (("selecao",), 120),
            (("tratamento",), 140),
            (("nome", "name", "convidado", "pessoa", "cliente", "participante"), 230),
            (("categoria", "category", "grupo", "tipo"), 170),
            (("endereco", "address", "logradouro", "rua", "avenida"), 240),
            (("edificio", "edif", "predio"), 220),
            (("cep", "codigo postal", "postal code", "zip"), 110),
            (("estado", "cidade", "uf", "city", "municipio"), 150),
            (("telefone", "phone", "fone", "tel"), 140),
            (("celular", "whatsapp", "mobile", "cell"), 140),
            (("email", "e-mail", "mail"), 220),
            (("obs", "observacao", "observacoes"), 220),
        )
        for words, width in width_rules:
            if any(word and word in normalized_column for word in words):
                return width
        return 170

    def _has_hidden_table_columns(self) -> bool:
        context_key = self._column_filter_context_key()
        return (
            context_key in self._visible_columns_by_context
            or bool(self._hidden_system_columns_by_context.get(context_key))
        )

    def _on_table_header_section_moved(
        self,
        logical_index: int,
        old_visual_index: int,
        new_visual_index: int,
    ) -> None:
        if self._restoring_table_header_layout or self._table_model is None or self._is_grouped_filter_mode():
            return

        header = self.table.horizontalHeader()
        ordered_columns: list[str] = []
        for visual_index in range(header.count()):
            logical_column = header.logicalIndex(visual_index)
            column_identifier = self._table_model.column_identifier(logical_column)
            if column_identifier:
                ordered_columns.append(column_identifier)

        self._table_column_order_by_context[self._column_filter_context_key()] = ordered_columns

    def _restore_table_header_layout(self) -> None:
        if self._table_model is None:
            return

        saved_order = self._table_column_order_by_context.get(self._column_filter_context_key())
        if not saved_order:
            return

        current_identifiers = {
            self._table_model.column_identifier(logical_column): logical_column
            for logical_column in range(self._table_model.columnCount())
        }
        desired_order = [
            column_identifier
            for column_identifier in saved_order
            if column_identifier in current_identifiers
        ]
        desired_order.extend(
            column_identifier
            for column_identifier in current_identifiers
            if column_identifier not in desired_order
        )

        header = self.table.horizontalHeader()
        self._restoring_table_header_layout = True
        try:
            for target_visual_index, column_identifier in enumerate(desired_order):
                logical_column = current_identifiers[column_identifier]
                current_visual_index = header.visualIndex(logical_column)
                if current_visual_index != target_visual_index:
                    header.moveSection(current_visual_index, target_visual_index)
        finally:
            self._restoring_table_header_layout = False

    def _apply_hidden_system_columns(self) -> None:
        if self._table_model is None:
            return

        hidden_columns = self._hidden_system_columns_by_context.get(self._column_filter_context_key(), set())
        for logical_column in range(self._table_model.columnCount()):
            column_identifier = self._table_model.column_identifier(logical_column)
            should_hide = column_identifier in hidden_columns
            if column_identifier == "system:duplicate" and not self._duplicates_mode:
                should_hide = True
            self.table.setColumnHidden(logical_column, should_hide)

    def _send_highlighted_rows_to_automatic(self) -> None:
        if self._table_model is None:
            return
        if self._automatic_mode:
            QMessageBox.information(
                self,
                "Planilha automática",
                "Você já está visualizando a Planilha automática.",
            )
            return
        if self._duplicates_mode or not self._current_sheet_selectable:
            QMessageBox.information(
                self,
                "Enviar selecionados",
                "Abra uma aba de contatos antes de enviar registros para a Planilha automática.",
            )
            return

        guest_ids = self._selected_table_guest_ids(selected_state=False)
        if not guest_ids:
            QMessageBox.information(
                self,
                "Enviar selecionados",
                "Selecione uma ou mais linhas ainda não marcadas antes de enviar.",
            )
            return

        try:
            self._review_and_send_guest_batch(guest_ids)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao enviar selecionados", str(exc))

    def _send_marked_rows_to_automatic(self) -> None:
        if self._automatic_mode:
            QMessageBox.information(
                self,
                "Planilha automática",
                "Você já está visualizando a Planilha automática.",
            )
            return
        if self._duplicates_mode or not self._current_sheet_selectable:
            QMessageBox.information(
                self,
                "Enviar marcados",
                "Abra uma aba de contatos antes de enviar registros para a Planilha automática.",
            )
            return

        guest_ids = sorted(self._marked_guest_ids)
        if not guest_ids:
            QMessageBox.information(
                self,
                "Enviar marcados",
                "Marque uma ou mais caixinhas antes de enviar.",
            )
            return

        try:
            self._review_and_send_guest_batch(guest_ids)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao enviar marcados", str(exc))

    def _clear_highlighted_rows_from_automatic(self) -> None:
        if self._table_model is None:
            return

        guest_ids = self._selected_table_guest_ids(selected_state=True)
        if not guest_ids:
            QMessageBox.information(
                self,
                "Remover selecionados",
                "Selecione uma ou mais linhas marcadas antes de remover.",
            )
            return

        try:
            updated_rows = self._view_model.set_page_selected(guest_ids, False)
            self._refresh_automatic_tab_label()
            self.status_label.setText(f"{updated_rows} registros removidos da Planilha automática.")
            self._load_table()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao remover selecionados", str(exc))

    def _selected_table_guest_ids(self, selected_state: bool | None = None) -> list[int]:
        if self._table_model is None or self.table.selectionModel() is None:
            return []

        row_indexes = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        guest_ids: list[int] = []
        seen: set[int] = set()
        if isinstance(self._table_model, GroupedGuestTableModel):
            for row_index in row_indexes:
                group = self._table_model.group_at(row_index)
                if group is None:
                    continue
                for row in group.rows:
                    if row.id in seen or not row.selectable:
                        continue
                    if selected_state is not None and row.selected != selected_state:
                        continue
                    guest_ids.append(row.id)
                    seen.add(row.id)
            return guest_ids

        for row_index in row_indexes:
            row = self._table_model.row_at(row_index)
            if row is None or not row.selectable or row.id in seen:
                continue
            if selected_state is not None and row.selected != selected_state:
                continue
            guest_ids.append(row.id)
            seen.add(row.id)
        return guest_ids

    def _set_page_selection(self, selected: bool) -> None:
        if self._table_model is None:
            return

        if isinstance(self._table_model, GroupedGuestTableModel):
            grouped_guest_ids = {
                row.id
                for group in self._grouped_filter_groups_by_key.values()
                for row in group.rows
            }
            if selected:
                self._marked_filter_group_keys = set(self._grouped_filter_groups_by_key)
                self._rebuild_group_marked_guest_ids()
                self.status_label.setText(f"{len(self._marked_guest_ids)} registros marcados nesta pagina.")
            else:
                self._marked_filter_group_keys.clear()
                self._marked_guest_ids.difference_update(grouped_guest_ids)
                self.status_label.setText("Marcacoes do resumo removidas.")
            self._table_model.refresh_selection_states()
            self._update_actions()
            return

        if selected and not self._automatic_mode and not self._duplicates_mode:
            marked_rows = 0
            for row_index in range(self._table_model.rowCount()):
                row = self._table_model.row_at(row_index)
                if row is None or not row.selectable or row.selected:
                    continue
                if self._table_model.set_row_selection(row_index, True):
                    marked_rows += 1
            self.status_label.setText(f"{marked_rows} registros marcados nesta página.")
            self._update_actions()
            return

        page_rows = [
            self._table_model.row_at(row_index)
            for row_index in range(self._table_model.rowCount())
        ]
        page_guest_ids = [row.id for row in page_rows if row is not None and row.selectable]
        selected_guest_ids = [row.id for row in page_rows if row is not None and row.selectable and row.selected]
        for guest_id in page_guest_ids:
            self._marked_guest_ids.discard(guest_id)

        if not selected_guest_ids:
            self._load_table()
            return

        try:
            self._view_model.set_page_selected(selected_guest_ids, False)
            self._refresh_automatic_tab_label()
            self._load_table()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao atualizar seleção", str(exc))

    def _set_all_filtered_selection(self, selected: bool) -> None:
        if self._automatic_mode:
            if selected:
                return
            answer = QMessageBox.question(
                self,
                "Limpar planilha automática",
                "Deseja remover todos os registros filtrados da Planilha automática?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                updated_rows = self._view_model.set_all_filtered_selected(
                    import_id=None,
                    workbook_id=None,
                    selected=False,
                    search=self._current_search,
                )
                self.status_label.setText(f"{updated_rows} registros atualizados.")
                self._refresh_automatic_tab_label()
                self._load_table()
            except Exception as exc:
                QMessageBox.critical(self, "Erro ao atualizar seleção", str(exc))
            return

        if not self._current_sheet_selectable:
            return

        action = "selecionar" if selected else "limpar"
        sheet_name = self.sheet_tabs.tabText(self.sheet_tabs.currentIndex())
        answer = QMessageBox.question(
            self,
            "Confirmar seleção",
            f"Deseja {action} todos os registros de '{sheet_name}' usando a busca atual?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            updated_rows = self._view_model.set_all_filtered_selected(
                import_id=self._current_import_id,
                workbook_id=self._current_workbook_id,
                selected=selected,
                search=self._current_search,
            )
            self.status_label.setText(f"{updated_rows} registros atualizados.")
            self._refresh_automatic_tab_label()
            self._load_table()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao atualizar seleção", str(exc))

    def _show_workbook_context_menu(self, position: object) -> None:
        index = self.workbook_tabs.tabAt(position)
        if index < 0:
            return
        tab_data = self.workbook_tabs.tabData(index)
        if not tab_data:
            return
        if tab_data["kind"] == "duplicates":
            return

        if tab_data["kind"] == "automatic":
            menu = QMenu(self)
            rename_action = menu.addAction("Renomear planilha")
            delete_action = menu.addAction("Excluir planilha")
            selected_action = menu.exec(self.workbook_tabs.mapToGlobal(position))
            if selected_action == rename_action:
                self._rename_automatic_sheet()
            elif selected_action == delete_action:
                self._delete_automatic_sheet()
            return

        if tab_data["kind"] != "workbook":
            return

        menu = QMenu(self)
        rename_action = menu.addAction("Renomear planilha")
        merge_action = menu.addAction("Unificar com outra planilha...")
        merge_action.setEnabled(len(self._view_model.list_workbooks()) > 1)
        delete_action = menu.addAction("Excluir planilha")
        selected_action = menu.exec(self.workbook_tabs.mapToGlobal(position))

        workbook_id = int(tab_data["workbook_id"])
        workbook_name = self.workbook_tabs.tabText(index)
        if selected_action == rename_action:
            self._rename_workbook(workbook_id, workbook_name)
        elif selected_action == merge_action:
            self._merge_workbook(workbook_id)
        elif selected_action == delete_action:
            self._delete_workbook(workbook_id, workbook_name)

    def _rename_workbook(self, workbook_id: int, current_name: str) -> None:
        clean_current_name = current_name.rsplit(" (", 1)[0]
        new_name, accepted = QInputDialog.getText(
            self,
            "Renomear planilha",
            "Nome da planilha:",
            text=clean_current_name,
        )
        if not accepted:
            return
        try:
            self._view_model.rename_workbook(workbook_id, new_name)
            self.status_label.setText("Planilha renomeada.")
            self._load_workbooks(preferred_workbook_id=workbook_id)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao renomear", str(exc))

    def _merge_workbook(self, source_workbook_id: int) -> None:
        workbooks = self._view_model.list_workbooks()
        source_workbook = next((workbook for workbook in workbooks if workbook.id == source_workbook_id), None)
        target_workbooks = [workbook for workbook in workbooks if workbook.id != source_workbook_id]
        if source_workbook is None or not target_workbooks:
            QMessageBox.information(
                self,
                "Unificar planilhas",
                "Importe pelo menos duas planilhas para usar a unificação.",
            )
            return

        label_by_id = self._workbook_merge_labels(target_workbooks)
        target_label, accepted = QInputDialog.getItem(
            self,
            "Unificar planilhas",
            (
                f"As abas de '{source_workbook.display_name}' serão movidas para a planilha escolhida.\n"
                "Escolha a planilha de destino:"
            ),
            list(label_by_id.values()),
            0,
            False,
        )
        if not accepted or not target_label:
            return

        target_workbook_id = next(
            workbook_id
            for workbook_id, label in label_by_id.items()
            if label == target_label
        )
        target_workbook = next(workbook for workbook in target_workbooks if workbook.id == target_workbook_id)
        answer = QMessageBox.question(
            self,
            "Confirmar unificação",
            (
                f"Deseja unificar '{source_workbook.display_name}' em '{target_workbook.display_name}'?\n\n"
                "As abas da origem serão movidas para o destino e a aba superior da origem sairá da lista."
            ),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self._view_model.merge_workbooks(
                source_workbook_id=source_workbook_id,
                target_workbook_id=target_workbook_id,
            )
            self.status_label.setText(
                f"{result.moved_sheets} abas e {result.moved_rows} linhas unificadas."
            )
            self._load_workbooks(preferred_workbook_id=target_workbook_id)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao unificar", str(exc))

    def _workbook_merge_labels(self, workbooks: list[object]) -> dict[int, str]:
        base_labels = [self._workbook_merge_label(workbook) for workbook in workbooks]
        return {
            workbook.id: (
                f"{base_label} - ID {workbook.id}"
                if base_labels.count(base_label) > 1
                else base_label
            )
            for workbook, base_label in zip(workbooks, base_labels)
        }

    def _workbook_merge_label(self, workbook: object) -> str:
        return f"{workbook.display_name} ({workbook.total_rows})"

    def _rename_automatic_sheet(self) -> None:
        new_name, accepted = QInputDialog.getText(
            self,
            "Renomear planilha automática",
            "Nome da planilha:",
            text=self._view_model.automatic_sheet_name(),
        )
        if not accepted:
            return
        try:
            self._view_model.rename_automatic_sheet(new_name)
            self.status_label.setText("Planilha automática renomeada.")
            self._refresh_automatic_tab_label()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao renomear", str(exc))

    def _delete_workbook(self, workbook_id: int, workbook_name: str) -> None:
        answer = QMessageBox.question(
            self,
            "Excluir planilha",
            f"Deseja excluir '{workbook_name}' do sistema?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._view_model.delete_workbook(workbook_id)
            self.status_label.setText("Planilha excluída.")
            self._load_workbooks()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao excluir", str(exc))

    def _delete_automatic_sheet(self) -> None:
        answer = QMessageBox.question(
            self,
            "Excluir planilha automática",
            "Deseja excluir a Planilha automática? Os convidados selecionados serão removidos da lista final.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            updated_rows = self._view_model.clear_automatic_sheet()
            self._current_search = ""
            self._reset_filter_inputs()
            self._filter_options_context_key = None
            self._current_page = 0
            self.status_label.setText(
                f"Planilha automática excluída. {updated_rows} registros removidos da lista final."
            )
            self._load_workbooks()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao excluir", str(exc))

    def _export_selected(self) -> None:
        workbook_id = self._current_workbook_id
        if workbook_id is None:
            workbooks = self._view_model.list_workbooks()
            workbook_id = workbooks[0].id if len(workbooks) == 1 else None

        if workbook_id is not None:
            final_count = self._view_model.load_guests(
                import_id=None,
                workbook_id=workbook_id,
                page=0,
                page_size=50,
                selected_only=True,
            ).total_rows
            unified_count = self._view_model.load_guests(
                import_id=None,
                workbook_id=workbook_id,
                page=0,
                page_size=50,
                selected_only=False,
            ).total_rows
        elif self._automatic_mode:
            final_count = self._selected_rows
            unified_count = 0
        else:
            return

        if final_count == 0 and unified_count == 0:
            QMessageBox.warning(
                self,
                "Nada para exportar",
                "Importe uma planilha ou selecione convidados antes de exportar.",
            )
            return

        export_choice = self._choose_export_mode(final_count, unified_count)
        if export_choice is None:
            return
        export_scope, export_mode, export_format, default_file_name = export_choice
        output_filter = "PDF (*.pdf)" if export_format == "pdf" else "Planilhas Excel (*.xlsx)"

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar exportação",
            str(Path.home() / default_file_name),
            output_filter,
        )
        if not output_path:
            return

        export_workbook_id = workbook_id if export_scope == "unified" or not self._automatic_mode else None
        try:
            result = self._view_model.export_selected(
                import_id=None,
                workbook_id=export_workbook_id,
                output_path=output_path,
                export_mode=export_mode,
                export_scope=export_scope,
                export_format=export_format,
            )
            self.status_label.setText(f"{result.total_rows} convidados exportados.")
            QMessageBox.information(
                self,
                "Exportação concluída",
                f"{result.total_rows} convidados exportados para {result.file_name}.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))

    def _choose_export_mode(self, final_count: int, unified_count: int) -> tuple[str, str, str, str] | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Exportar planilha")
        dialog.resize(480, 390)
        layout = QVBoxLayout(dialog)

        label = QLabel("Escolha o conteúdo e o formato da exportação.")
        label.setWordWrap(True)
        layout.addWidget(label)

        source_label = QLabel("O que exportar")
        source_label.setObjectName("SmallLabel")
        layout.addWidget(source_label)

        source_panel = QWidget(dialog)
        source_layout = QVBoxLayout(source_panel)
        source_layout.setContentsMargins(0, 0, 0, 0)
        final_radio = QRadioButton(f"Lista final ({final_count} convidados)")
        unified_radio = QRadioButton(f"Lista unificada ({unified_count} registros)")
        final_radio.setEnabled(final_count > 0)
        unified_radio.setEnabled(unified_count > 0)
        if final_count > 0:
            final_radio.setChecked(True)
        elif unified_count > 0:
            unified_radio.setChecked(True)
        source_layout.addWidget(final_radio)
        source_layout.addWidget(unified_radio)
        layout.addWidget(source_panel)

        file_type_label = QLabel("Tipo de arquivo")
        file_type_label.setObjectName("SmallLabel")
        layout.addWidget(file_type_label)

        file_type_panel = QWidget(dialog)
        file_type_layout = QVBoxLayout(file_type_panel)
        file_type_layout.setContentsMargins(0, 0, 0, 0)
        xlsx_radio = QRadioButton("Excel (.xlsx)")
        pdf_radio = QRadioButton("PDF - lista de presença")
        xlsx_radio.setChecked(True)
        file_type_layout.addWidget(xlsx_radio)
        file_type_layout.addWidget(pdf_radio)
        layout.addWidget(file_type_panel)

        format_label = QLabel("Formato")
        format_label.setObjectName("SmallLabel")
        layout.addWidget(format_label)

        format_panel = QWidget(dialog)
        format_layout = QVBoxLayout(format_panel)
        format_layout.setContentsMargins(0, 0, 0, 0)
        complete_radio = QRadioButton("Planilha completa")
        names_radio = QRadioButton("Apenas nomes")
        category_radio = QRadioButton("Separar por categoria")
        complete_radio.setChecked(True)
        format_layout.addWidget(complete_radio)
        format_layout.addWidget(names_radio)
        format_layout.addWidget(category_radio)
        layout.addWidget(format_panel)

        def update_format_options() -> None:
            pdf_selected = pdf_radio.isChecked()
            complete_radio.setEnabled(not pdf_selected)
            category_radio.setEnabled(not pdf_selected)
            if pdf_selected:
                names_radio.setChecked(True)

        xlsx_radio.toggled.connect(update_format_options)
        pdf_radio.toggled.connect(update_format_options)
        update_format_options()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText("Continuar")
        if cancel_button is not None:
            cancel_button.setText("Cancelar")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        export_scope = "unified" if unified_radio.isChecked() else "final"
        scope_file_part = "lista_unificada" if export_scope == "unified" else "lista_final"
        export_format = "pdf" if pdf_radio.isChecked() else "xlsx"
        if export_format == "pdf":
            return export_scope, "names", export_format, f"mala_direta_{scope_file_part}_presenca.pdf"
        if names_radio.isChecked():
            return export_scope, "names", export_format, f"mala_direta_{scope_file_part}_nomes.xlsx"
        if category_radio.isChecked():
            return export_scope, "category", export_format, f"mala_direta_{scope_file_part}_por_categoria.xlsx"
        return export_scope, "complete", export_format, f"mala_direta_{scope_file_part}.xlsx"

    def _go_first_page(self) -> None:
        self._marked_guest_ids.clear()
        self._current_page = 0
        self._load_table()

    def _go_previous_page(self) -> None:
        self._marked_guest_ids.clear()
        self._current_page = max(self._current_page - 1, 0)
        self._load_table()

    def _go_next_page(self) -> None:
        self._marked_guest_ids.clear()
        self._current_page += 1
        self._load_table()

    def _go_last_page(self) -> None:
        self._marked_guest_ids.clear()
        self._current_page = max(ceil(self._total_rows / max(self._page_size, 1)) - 1, 0)
        self._load_table()

    def _set_busy(self, busy: bool) -> None:
        widgets = (
            self.register_button,
            self.import_button,
            self.export_button,
            self.options_button,
            self.workbook_tabs,
            self.sheet_tabs,
            self.filter_button,
            self.column_filter_button,
            self.create_column_button,
            self.search_input,
            self.clear_search_button,
            self.table_send_button,
            self.select_page_button,
            self.clear_page_button,
        )
        for widget in widgets:
            widget.setEnabled(not busy)

        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    def _update_actions(self) -> None:
        has_workbook = self._current_workbook_id is not None
        has_workspace = has_workbook or self._automatic_mode or self._duplicates_mode
        grouped_filter_mode = self._is_grouped_filter_mode()
        can_select = (
            has_workbook
            and self._current_sheet_selectable
            and not self._automatic_mode
            and not self._duplicates_mode
            and self._total_rows > 0
        )
        has_next = self._total_rows > (self._current_page + 1) * max(self._page_size, 1)

        self.filter_button.setEnabled(has_workspace)
        self.column_filter_button.setEnabled(
            has_workspace and bool(self._available_columns) and not grouped_filter_mode
        )
        self.create_column_button.setEnabled(
            has_workspace and not self._duplicates_mode and not grouped_filter_mode
        )
        self.search_input.setEnabled(has_workspace)
        self.clear_search_button.setEnabled(has_workspace and bool(self.search_input.text().strip()))
        self.options_button.setEnabled(has_workspace)
        self.export_button.setEnabled(has_workbook or self._automatic_mode)
        self.table_send_button.setVisible(can_select)
        self.table_send_button.setEnabled(can_select and bool(self._marked_guest_ids))
        self.select_page_button.setEnabled(can_select)
        if grouped_filter_mode:
            self.clear_page_button.setEnabled(can_select and bool(self._marked_guest_ids))
        else:
            self.clear_page_button.setEnabled(
                can_select
                and self._table_model is not None
                and bool(self._table_model.guest_ids())
            )
        self.first_page_button.setEnabled(self._current_page > 0)
        self.previous_page_button.setEnabled(self._current_page > 0)
        self.next_page_button.setEnabled(has_next)
        self.last_page_button.setEnabled(has_next)
