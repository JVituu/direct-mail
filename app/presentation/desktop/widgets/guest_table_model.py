from collections.abc import Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont

from app.application.dtos.guest_dto import GuestRowDTO


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

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._columns) + 2

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None

        row = self._rows[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in (0, 1):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft

        if role == Qt.ItemDataRole.FontRole and column == 0 and row.selected:
            font = QFont()
            font.setBold(True)
            return font

        if role == Qt.ItemDataRole.ForegroundRole and column == 0 and row.selected:
            return QBrush(QColor("#126c50"))

        if role == Qt.ItemDataRole.BackgroundRole and self._highlight_selected_rows and row.selected:
            return QBrush(QColor("#e1f5e8"))

        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return None

        if column == 0:
            return "X" if row.selected and row.selectable else ""
        if column == 1:
            return str(row.row_number)

        data_column = self._columns[column - 2]
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
            return "Linha"
        return self._columns[section - 2]

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
        column_name = self._columns[index.column() - 2]
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
        if not index.isValid() or index.column() < 2:
            return False
        column_name = self._columns[index.column() - 2]
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
