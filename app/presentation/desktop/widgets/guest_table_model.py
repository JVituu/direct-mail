from collections.abc import Callable, Sequence
import hashlib
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
DEFAULT_ROW_HEIGHT = 28
MULTILINE_ROW_PADDING = 10
MULTILINE_LINE_HEIGHT = 19


class GuestTableModel(QAbstractTableModel):
    def __init__(
        self,
        rows: Sequence[GuestRowDTO],
        columns: Sequence[str],
        editable_columns: Sequence[str],
        selection_changed: Callable[[int, bool], None],
        cell_changed: Callable[[int, str, str], bool],
        highlight_selected_rows: bool = True,
    ) -> None:
        super().__init__()
        self._rows = list(rows)
        self._columns = list(columns)
        self._editable_columns = set(editable_columns)
        self._selection_changed = selection_changed
        self._cell_changed = cell_changed
        self._highlight_selected_rows = highlight_selected_rows
        self._category_column_indexes = self._find_category_column_indexes()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._columns) + 4

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None

        row = self._rows[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in (0, 1, 2, 3):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft

        if role == Qt.ItemDataRole.SizeHintRole:
            line_count = self._cell_line_count(row, column)
            if line_count <= 1:
                return None
            height = max(DEFAULT_ROW_HEIGHT, line_count * MULTILINE_LINE_HEIGHT + MULTILINE_ROW_PADDING)
            return QSize(-1, height)

        if role == Qt.ItemDataRole.FontRole and column == 0 and row.selected:
            font = QFont()
            font.setBold(True)
            return font

        if role == Qt.ItemDataRole.ForegroundRole and column == 0 and row.selected:
            return QBrush(QColor("#126c50"))

        if role == Qt.ItemDataRole.FontRole and column == 2 and row.duplicate_count > 1:
            font = QFont()
            font.setBold(True)
            return font

        if role == Qt.ItemDataRole.ForegroundRole and column == 2 and row.duplicate_count > 1:
            return QBrush(QColor("#9a4d00"))

        if role == Qt.ItemDataRole.BackgroundRole and self._highlight_selected_rows and row.selected:
            return QBrush(QColor("#e1f5e8"))

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
            return "X" if row.selected and row.selectable else ""
        if column == 1:
            return row.verification_code
        if column == 2:
            if row.duplicate_count > 1:
                return f"{row.duplicate_reason} ({row.duplicate_count})"
            return ""
        if column == 3:
            return str(row.row_number)

        data_column = self._columns[column - 4]
        return row.data.get(data_column, "")

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
            return "Selecionado"
        if section == 1:
            return "Código"
        if section == 2:
            return "Duplicidade"
        if section == 3:
            return "Linha"
        return self._columns[section - 4]

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
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
            return self._set_selection_data(index, value, role)

        if not self._is_editable_data_cell(index) or role != Qt.ItemDataRole.EditRole:
            return False

        row = self._rows[index.row()]
        column_name = self._columns[index.column() - 4]
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

        self._set_row_selected(index, selected)
        return True

    def _is_editable_data_cell(self, index: QModelIndex) -> bool:
        if not index.isValid() or index.column() < 4:
            return False
        column_name = self._columns[index.column() - 4]
        return column_name in self._editable_columns

    def toggle_selection(self, row_index: int) -> bool:
        if row_index < 0 or row_index >= len(self._rows):
            return False

        index = self.index(row_index, 0)
        row = self._rows[row_index]
        if not row.selectable:
            return False

        self._set_row_selected(index, not row.selected)
        return True

    def _set_row_selected(self, index: QModelIndex, selected: bool) -> None:
        row = self._rows[index.row()]
        if row.selected == selected:
            return

        row.selected = selected
        self.dataChanged.emit(
            index,
            index,
            [
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.FontRole,
                Qt.ItemDataRole.ForegroundRole,
                Qt.ItemDataRole.BackgroundRole,
            ],
        )
        self._selection_changed(row.id, selected)

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
        if table_column < 4:
            return 1
        column_name = self._columns[table_column - 4]
        value = str(row.data.get(column_name, ""))
        return max(value.count("\n") + 1, 1)

    def _find_category_column_indexes(self) -> set[int]:
        indexes: set[int] = set()
        for column_index, column_name in enumerate(self._columns, start=4):
            normalized_column = self._normalize_text(column_name)
            if "categoria" in normalized_column or "category" in normalized_column:
                indexes.add(column_index)
        return indexes

    def _category_value(self, row: GuestRowDTO, table_column: int) -> str:
        if table_column < 4:
            return ""
        column_name = self._columns[table_column - 4]
        return str(row.data.get(column_name, "")).strip()

    def _category_color(self, value: str) -> str:
        normalized_value = self._normalize_text(value)
        digest = hashlib.sha1(normalized_value.encode("utf-8")).hexdigest()
        color_index = int(digest[:8], 16) % len(CATEGORY_BACKGROUND_COLORS)
        return CATEGORY_BACKGROUND_COLORS[color_index]

    def _normalize_text(self, value: str) -> str:
        normalized = normalize("NFD", str(value).casefold())
        return "".join(character for character in normalized if not combining(character))
