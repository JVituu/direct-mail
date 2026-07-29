from collections.abc import Callable, Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from app.application.dtos.guest_dto import GuestRowDTO


class GuestTableModel(QAbstractTableModel):
    def __init__(
        self,
        rows: Sequence[GuestRowDTO],
        columns: Sequence[str],
        selection_changed: Callable[[int, bool], None],
    ) -> None:
        super().__init__()
        self._rows = list(rows)
        self._columns = list(columns)
        self._selection_changed = selection_changed

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

        if role == Qt.ItemDataRole.CheckStateRole and column == 0:
            return Qt.CheckState.Checked if row.selected else Qt.CheckState.Unchecked

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in (0, 1):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft

        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if column == 0:
            return ""
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
        if index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def setData(
        self,
        index: QModelIndex,
        value: object,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if not index.isValid() or index.column() != 0:
            return False
        if role != Qt.ItemDataRole.CheckStateRole:
            return False

        selected = value in (
            Qt.CheckState.Checked,
            Qt.CheckState.Checked.value,
        )
        row = self._rows[index.row()]
        self._selection_changed(row.id, selected)
        row.selected = selected
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        return True

    def guest_ids(self) -> list[int]:
        return [row.id for row in self._rows]
