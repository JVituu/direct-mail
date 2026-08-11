from collections.abc import Callable, Sequence
import hashlib
import re
from unicodedata import combining, normalize

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont

from app.application.dtos.guest_dto import GuestRowDTO


CATEGORY_BACKGROUND_COLORS = (
    "#dbeafe",
    "#dcfce7",
    "#fef3c7",
    "#ede9fe",
    "#fae8ff",
    "#cffafe",
    "#ffe4e6",
    "#e0f2fe",
    "#f3e8ff",
    "#ccfbf1",
    "#ffedd5",
    "#e2e8f0",
)
CATEGORY_FOREGROUND_COLOR = "#0f172a"
AUTOMATIC_SENT_BACKGROUND_COLOR = "#e9f8ef"
AUTOMATIC_PENDING_BACKGROUND_COLOR = "#fff8df"
DEFAULT_ROW_HEIGHT = 28
MULTILINE_ROW_PADDING = 10
MULTILINE_LINE_HEIGHT = 19
FIXED_COLUMN_COUNT = 3
EMAIL_COLUMN_WORDS = ("email", "e-mail", "mail")


class GuestTableModel(QAbstractTableModel):
    def __init__(
        self,
        rows: Sequence[GuestRowDTO],
        columns: Sequence[str],
        editable_columns: Sequence[str],
        marked_guest_ids: set[int],
        selection_changed: Callable[[int, bool], None],
        cell_changed: Callable[[int, str, str], bool],
        highlight_selected_rows: bool = True,
        automatic_mode: bool = False,
        invitation_status_changed: Callable[[int, str], bool] | None = None,
        automatic_remove_requested: Callable[[int], bool] | None = None,
    ) -> None:
        super().__init__()
        self._rows = list(rows)
        self._columns = list(columns)
        self._editable_columns = set(editable_columns)
        self._marked_guest_ids = marked_guest_ids
        self._selection_changed = selection_changed
        self._cell_changed = cell_changed
        self._highlight_selected_rows = highlight_selected_rows
        self._automatic_mode = automatic_mode
        self._invitation_status_changed = invitation_status_changed
        self._automatic_remove_requested = automatic_remove_requested
        self._category_column_indexes = self._find_category_column_indexes()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._columns) + FIXED_COLUMN_COUNT

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None

        row = self._rows[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column < FIXED_COLUMN_COUNT:
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft

        if (
            role == Qt.ItemDataRole.CheckStateRole
            and column == 0
            and row.selectable
            and not self._automatic_mode
        ):
            return Qt.CheckState.Checked if self._is_row_checked(row) else Qt.CheckState.Unchecked

        if role == Qt.ItemDataRole.UserRole and column == 0 and self._automatic_mode:
            return row.invitation_status

        if role == Qt.ItemDataRole.ToolTipRole and column == 2 and row.duplicate_count > 1:
            return "Clique para visualizar os registros parecidos."

        if role == Qt.ItemDataRole.ToolTipRole and column == 0 and self._automatic_mode:
            return "Verde: convite enviado. Amarelo: em espera. Vermelho: remover da lista final."

        if role == Qt.ItemDataRole.SizeHintRole:
            line_count = self._cell_line_count(row, column)
            if line_count <= 1:
                return None
            height = max(DEFAULT_ROW_HEIGHT, line_count * MULTILINE_LINE_HEIGHT + MULTILINE_ROW_PADDING)
            return QSize(-1, height)

        if role == Qt.ItemDataRole.FontRole and column == 0 and self._is_row_checked(row):
            font = QFont()
            font.setBold(True)
            return font

        if role == Qt.ItemDataRole.ForegroundRole and column == 0 and self._is_row_checked(row):
            return QBrush(QColor("#111827"))

        if role == Qt.ItemDataRole.FontRole and column == 2 and row.duplicate_count > 1:
            font = QFont()
            font.setBold(True)
            return font

        if role == Qt.ItemDataRole.ForegroundRole and column == 2 and row.duplicate_count > 1:
            return QBrush(QColor("#9a4d00"))

        if role == Qt.ItemDataRole.BackgroundRole and self._automatic_mode:
            if row.invitation_status == "sent":
                return QBrush(QColor(AUTOMATIC_SENT_BACKGROUND_COLOR))
            if row.invitation_status == "waiting":
                return QBrush(QColor(AUTOMATIC_PENDING_BACKGROUND_COLOR))

        if role == Qt.ItemDataRole.BackgroundRole and self._highlight_selected_rows and self._is_row_checked(row):
            return QBrush(QColor("#e1f5e8"))

        if role == Qt.ItemDataRole.BackgroundRole and column == 2 and row.duplicate_count > 1:
            return QBrush(QColor("#fff4df"))

        if role == Qt.ItemDataRole.BackgroundRole and column in self._category_column_indexes:
            category_value = self._category_value(row, column)
            if category_value:
                return QBrush(QColor(self._category_color(category_value)))

        if role == Qt.ItemDataRole.ForegroundRole and column in self._category_column_indexes:
            if self._category_value(row, column):
                return QBrush(QColor(CATEGORY_FOREGROUND_COLOR))

        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return None

        if column == 0:
            return ""
        if column == 1:
            return row.verification_code
        if column == 2:
            if row.duplicate_count > 1:
                return f"{row.duplicate_reason} ({row.duplicate_count})"
            return ""
        data_column = self._columns[column - FIXED_COLUMN_COUNT]
        value = row.data.get(data_column, "")
        if role == Qt.ItemDataRole.EditRole:
            return value
        return self._format_display_value(data_column, value)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Vertical:
            return str(section + 1)

        if section == 0:
            return "Enviado" if self._automatic_mode else "Selecionado"
        if section == 1:
            return "Código"
        if section == 2:
            return "Duplicidade"
        return self._format_header_text(self._columns[section - FIXED_COLUMN_COUNT])

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == 0 and self._rows[index.row()].selectable and not self._automatic_mode:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        if self._is_editable_data_cell(index):
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(
        self,
        index: QModelIndex,
        value: object,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if not index.isValid():
            return False

        if index.column() == 0:
            if self._automatic_mode:
                return self._set_invitation_status_data(index, value, role)
            return self._set_selection_data(index, value, role)

        if not self._is_editable_data_cell(index) or role != Qt.ItemDataRole.EditRole:
            return False

        row = self._rows[index.row()]
        column_name = self._columns[index.column() - FIXED_COLUMN_COUNT]
        new_value = "" if value is None else str(value).strip()
        if row.data.get(column_name, "") == new_value:
            return True
        if not self._cell_changed(row.id, column_name, new_value):
            return False

        row.data[column_name] = new_value
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
        return True

    def _set_selection_data(
        self,
        index: QModelIndex,
        value: object,
        role: int,
    ) -> bool:
        row = self._rows[index.row()]
        if not row.selectable:
            return False
        if role not in (Qt.ItemDataRole.EditRole, Qt.ItemDataRole.CheckStateRole):
            return False
        if role == Qt.ItemDataRole.CheckStateRole:
            selected = value in (
                Qt.CheckState.Checked,
                Qt.CheckState.Checked.value,
            )
        else:
            selected = bool(value)

        self._set_row_checked(index, selected)
        return True

    def _set_invitation_status_data(
        self,
        index: QModelIndex,
        value: object,
        role: int,
    ) -> bool:
        if role not in (Qt.ItemDataRole.EditRole, Qt.ItemDataRole.UserRole):
            return False

        row = self._rows[index.row()]
        action = str(value or "").strip().casefold()
        if action == "remove":
            if self._automatic_remove_requested is None:
                return False
            return self._automatic_remove_requested(row.id)

        status = "sent" if action == "sent" else "waiting" if action in {"pending", "waiting"} else ""
        if not status:
            return False
        if row.invitation_status == status:
            return True
        if self._invitation_status_changed is not None and not self._invitation_status_changed(row.id, status):
            return False

        row.invitation_status = status
        first_index = self.index(index.row(), 0)
        last_index = self.index(index.row(), self.columnCount() - 1)
        self.dataChanged.emit(
            first_index,
            last_index,
            [
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.UserRole,
                Qt.ItemDataRole.ToolTipRole,
                Qt.ItemDataRole.BackgroundRole,
            ],
        )
        return True

    def _is_editable_data_cell(self, index: QModelIndex) -> bool:
        if not index.isValid() or index.column() < FIXED_COLUMN_COUNT:
            return False
        column_name = self._columns[index.column() - FIXED_COLUMN_COUNT]
        return column_name in self._editable_columns

    def toggle_selection(self, row_index: int) -> bool:
        if self._automatic_mode:
            return False
        if row_index < 0 or row_index >= len(self._rows):
            return False

        index = self.index(row_index, 0)
        row = self._rows[row_index]
        if not row.selectable:
            return False

        self._set_row_checked(index, not self._is_row_checked(row))
        return True

    def set_row_selection(self, row_index: int, selected: bool) -> bool:
        if self._automatic_mode:
            return False
        if row_index < 0 or row_index >= len(self._rows):
            return False

        row = self._rows[row_index]
        if not row.selectable:
            return False

        self._set_row_checked(self.index(row_index, 0), selected)
        return True

    def row_at(self, row_index: int) -> GuestRowDTO | None:
        if row_index < 0 or row_index >= len(self._rows):
            return None
        return self._rows[row_index]

    def _set_row_checked(self, index: QModelIndex, selected: bool) -> None:
        row = self._rows[index.row()]
        if self._is_row_checked(row) == selected:
            return

        if row.selected and selected:
            return
        if row.selected and not selected:
            self._selection_changed(row.id, False)
            return

        if selected:
            self._marked_guest_ids.add(row.id)
        else:
            self._marked_guest_ids.discard(row.id)
        self.dataChanged.emit(
            index,
            index,
            [
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.FontRole,
                Qt.ItemDataRole.ForegroundRole,
                Qt.ItemDataRole.BackgroundRole,
                Qt.ItemDataRole.CheckStateRole,
            ],
        )
        self._selection_changed(row.id, selected)

    def _is_row_checked(self, row: GuestRowDTO) -> bool:
        return row.selected or row.id in self._marked_guest_ids

    def guest_ids(self, selectable_only: bool = True) -> list[int]:
        if not selectable_only:
            return [row.id for row in self._rows]
        return [row.id for row in self._rows if row.selectable]

    def has_multiline_cells(self) -> bool:
        for row in self._rows:
            if any("\n" in str(row.data.get(column, "")) for column in self._columns):
                return True
        return False

    def _cell_line_count(self, row: GuestRowDTO, table_column: int) -> int:
        if table_column < FIXED_COLUMN_COUNT:
            return 1
        column_name = self._columns[table_column - FIXED_COLUMN_COUNT]
        value = str(row.data.get(column_name, ""))
        return max(value.count("\n") + 1, 1)

    def _find_category_column_indexes(self) -> set[int]:
        indexes: set[int] = set()
        for column_index, column_name in enumerate(self._columns, start=FIXED_COLUMN_COUNT):
            normalized_column = self._normalize_text(column_name)
            if "categoria" in normalized_column or "category" in normalized_column:
                indexes.add(column_index)
        return indexes

    def _category_value(self, row: GuestRowDTO, table_column: int) -> str:
        if table_column < FIXED_COLUMN_COUNT:
            return ""
        column_name = self._columns[table_column - FIXED_COLUMN_COUNT]
        return str(row.data.get(column_name, "")).strip()

    def _category_color(self, value: str) -> str:
        normalized_value = self._normalize_text(value)
        digest = hashlib.sha1(normalized_value.encode("utf-8")).hexdigest()
        color_index = int(digest[:8], 16) % len(CATEGORY_BACKGROUND_COLORS)
        return CATEGORY_BACKGROUND_COLORS[color_index]

    def _format_header_text(self, value: object) -> str:
        text = str(value or "").strip().casefold()
        if not text:
            return ""
        return re.sub(
            r"(^|[\s/])([^\W\d_])",
            lambda match: f"{match.group(1)}{match.group(2).upper()}",
            text,
        )

    def _format_display_value(self, column_name: str, value: object) -> str:
        text = "" if value is None else str(value)
        if self._is_email_column(column_name):
            return text.casefold()
        return text.upper()

    def _is_email_column(self, column_name: str) -> bool:
        normalized_column = self._normalize_text(column_name)
        return any(word and word in normalized_column for word in EMAIL_COLUMN_WORDS)

    def _normalize_text(self, value: str) -> str:
        normalized = normalize("NFD", str(value).casefold())
        return "".join(character for character in normalized if not combining(character))
