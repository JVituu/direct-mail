from collections.abc import Callable, Sequence
from dataclasses import dataclass
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
AUTOMATIC_CONTACT_FAILED_BACKGROUND_COLOR = "#fff1f2"
DEFAULT_ROW_HEIGHT = 28
MULTILINE_ROW_PADDING = 10
MULTILINE_LINE_HEIGHT = 19
BASE_SYSTEM_COLUMN_IDENTIFIERS = ("selection", "duplicate")
AUTOMATIC_SYSTEM_COLUMN_IDENTIFIERS = ("selection", "contact_tracking", "duplicate")
EMAIL_COLUMN_WORDS = ("email", "e-mail", "mail")
CONTACT_TRACKING_CHANNELS = ("call",)
CONTACT_TRACKING_STATUS_VALUES = {"done", "missed", "not_done"}
HEADER_FILTER_SUFFIX = " \u25be"


@dataclass(frozen=True, slots=True)
class GuestGroupDTO:
    key: str
    label: str
    rows: tuple[GuestRowDTO, ...]

    @property
    def quantity(self) -> int:
        return len(self.rows)


class GroupedGuestTableModel(QAbstractTableModel):
    def __init__(
        self,
        groups: Sequence[GuestGroupDTO],
        value_header: str,
        selected_group_keys: set[str],
        selection_changed: Callable[[str, bool], None],
    ) -> None:
        super().__init__()
        self._groups = list(groups)
        self._value_header = value_header
        self._selected_group_keys = selected_group_keys
        self._selection_changed = selection_changed

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._groups)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return 3

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None

        group = self._groups[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in (0, 2):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft

        if role == Qt.ItemDataRole.CheckStateRole and column == 0:
            return (
                Qt.CheckState.Checked
                if group.key in self._selected_group_keys
                else Qt.CheckState.Unchecked
            )

        if role == Qt.ItemDataRole.ToolTipRole:
            if column == 0:
                return "Marcar este grupo para enviar para a Planilha automatica."
            if column == 2:
                return "De dois cliques para visualizar os contatos deste grupo."
            return group.label

        if role == Qt.ItemDataRole.FontRole and column == 2:
            font = QFont()
            font.setBold(True)
            return font

        if role == Qt.ItemDataRole.ForegroundRole and column == 2:
            return QBrush(QColor("#245783"))

        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if column == 0:
            return ""
        if column == 1:
            return group.label
        if column == 2:
            return str(group.quantity)
        return ""

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

        headers = ("Selecionado", self._value_header, "Quantidade")
        if 0 <= section < len(headers):
            return f"{headers[section]}{HEADER_FILTER_SUFFIX}"
        return ""

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
        if not index.isValid() or index.column() != 0 or role != Qt.ItemDataRole.CheckStateRole:
            return False

        group = self._groups[index.row()]
        selected = value in (
            Qt.CheckState.Checked,
            Qt.CheckState.Checked.value,
        )
        self._selection_changed(group.key, selected)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        return True

    def column_identifier(self, table_column: int) -> str:
        identifiers = ("group:selection", "group:value", "group:quantity")
        if 0 <= table_column < len(identifiers):
            return identifiers[table_column]
        return ""

    def data_column_name(self, table_column: int) -> str | None:
        return None

    def system_column_index(self, identifier: str) -> int | None:
        return None

    def has_multiline_cells(self) -> bool:
        return False

    def row_at(self, row_index: int) -> GuestRowDTO | None:
        return None

    def group_at(self, row_index: int) -> GuestGroupDTO | None:
        if row_index < 0 or row_index >= len(self._groups):
            return None
        return self._groups[row_index]

    def all_guest_rows(self) -> list[GuestRowDTO]:
        rows_by_id: dict[int, GuestRowDTO] = {}
        for group in self._groups:
            for row in group.rows:
                rows_by_id.setdefault(row.id, row)
        return list(rows_by_id.values())

    def guest_ids(self, selectable_only: bool = True) -> list[int]:
        return [
            row.id
            for row in self.all_guest_rows()
            if not selectable_only or row.selectable
        ]

    def refresh_selection_states(self) -> None:
        if not self._groups:
            return
        top_left = self.index(0, 0)
        bottom_right = self.index(len(self._groups) - 1, 0)
        self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.CheckStateRole])


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
        contact_status_changed: Callable[[int, str, str], bool] | None = None,
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
        self._contact_status_changed = contact_status_changed
        self._category_column_indexes = self._find_category_column_indexes()
        self._has_multiline_cells = any(
            "\n" in str(row.data.get(column, ""))
            for row in self._rows
            for column in self._columns
        )

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._columns) + self._data_column_offset()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None

        row = self._rows[index.row()]
        column = index.column()
        system_identifier = self._system_column_identifier(column)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if system_identifier is not None:
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft

        if (
            role == Qt.ItemDataRole.CheckStateRole
            and system_identifier == "selection"
            and row.selectable
            and not self._automatic_mode
        ):
            return Qt.CheckState.Checked if self._is_row_checked(row) else Qt.CheckState.Unchecked

        if role == Qt.ItemDataRole.UserRole and system_identifier == "selection" and self._automatic_mode:
            return row.invitation_status

        if role == Qt.ItemDataRole.UserRole and system_identifier == "contact_tracking" and self._automatic_mode:
            return self._contact_tracking_statuses(row)

        if role == Qt.ItemDataRole.ToolTipRole and system_identifier == "duplicate" and row.duplicate_count > 1:
            return "Clique para visualizar os registros parecidos."

        if role == Qt.ItemDataRole.ToolTipRole and system_identifier == "selection" and self._automatic_mode:
            return "Verde: e-mail enviado. Amarelo: e-mail em aguardo. Vermelho: e-mail nao enviado."

        if role == Qt.ItemDataRole.ToolTipRole and system_identifier == "contact_tracking" and self._automatic_mode:
            return "Controle de chamadas por telefone e celular."

        if role == Qt.ItemDataRole.SizeHintRole:
            if system_identifier == "contact_tracking":
                return QSize(-1, 34)
            line_count = self._cell_line_count(row, column)
            if line_count <= 1:
                return None
            height = max(DEFAULT_ROW_HEIGHT, line_count * MULTILINE_LINE_HEIGHT + MULTILINE_ROW_PADDING)
            return QSize(-1, height)

        if role == Qt.ItemDataRole.FontRole and system_identifier == "selection" and self._is_row_checked(row):
            font = QFont()
            font.setBold(True)
            return font

        if role == Qt.ItemDataRole.ForegroundRole and system_identifier == "selection" and self._is_row_checked(row):
            return QBrush(QColor("#111827"))

        if role == Qt.ItemDataRole.FontRole and system_identifier == "duplicate" and row.duplicate_count > 1:
            font = QFont()
            font.setBold(True)
            return font

        if role == Qt.ItemDataRole.ForegroundRole and system_identifier == "duplicate" and row.duplicate_count > 1:
            return QBrush(QColor("#9a4d00"))

        if role == Qt.ItemDataRole.BackgroundRole and self._automatic_mode and system_identifier == "contact_tracking":
            call_status = self._contact_tracking_status(row, "call")
            if call_status == "done":
                return QBrush(QColor(AUTOMATIC_SENT_BACKGROUND_COLOR))
            if call_status == "missed":
                return QBrush(QColor(AUTOMATIC_PENDING_BACKGROUND_COLOR))
            if call_status == "not_done":
                return QBrush(QColor(AUTOMATIC_CONTACT_FAILED_BACKGROUND_COLOR))

        if role == Qt.ItemDataRole.BackgroundRole and self._automatic_mode:
            if row.invitation_status == "sent":
                return QBrush(QColor(AUTOMATIC_SENT_BACKGROUND_COLOR))
            if row.invitation_status == "waiting":
                return QBrush(QColor(AUTOMATIC_PENDING_BACKGROUND_COLOR))
            if row.invitation_status == "not_sent":
                return QBrush(QColor(AUTOMATIC_CONTACT_FAILED_BACKGROUND_COLOR))

        if role == Qt.ItemDataRole.BackgroundRole and self._highlight_selected_rows and self._is_row_checked(row):
            return QBrush(QColor("#e1f5e8"))

        if role == Qt.ItemDataRole.BackgroundRole and system_identifier == "duplicate" and row.duplicate_count > 1:
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

        if system_identifier == "selection":
            return ""
        if system_identifier == "contact_tracking":
            return ""
        if system_identifier == "code":
            return row.verification_code
        if system_identifier == "duplicate":
            if row.duplicate_count > 1:
                return f"{row.duplicate_reason} ({row.duplicate_count})"
            return ""
        data_column = self._data_column_for_table_column(column)
        if data_column is None:
            return ""
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

        system_identifier = self._system_column_identifier(section)
        if system_identifier == "selection":
            label = "E-mail enviado" if self._automatic_mode else "Selecionado"
            return f"{label}{HEADER_FILTER_SUFFIX}"
        if system_identifier == "contact_tracking":
            return f"Chamadas{HEADER_FILTER_SUFFIX}"
        if system_identifier == "code":
            return "Código"
        if system_identifier == "duplicate":
            return f"Duplicidade{HEADER_FILTER_SUFFIX}"
        data_column = self._data_column_for_table_column(section)
        return f"{self._format_header_text(data_column or '')}{HEADER_FILTER_SUFFIX}"

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        system_identifier = self._system_column_identifier(index.column())
        if system_identifier == "selection" and self._rows[index.row()].selectable and not self._automatic_mode:
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

        system_identifier = self._system_column_identifier(index.column())
        if system_identifier == "selection":
            if self._automatic_mode:
                return self._set_invitation_status_data(index, value, role)
            return self._set_selection_data(index, value, role)
        if system_identifier == "contact_tracking":
            return self._set_contact_tracking_data(index, value, role)

        if not self._is_editable_data_cell(index) or role != Qt.ItemDataRole.EditRole:
            return False

        row = self._rows[index.row()]
        column_name = self._data_column_for_table_column(index.column())
        if column_name is None:
            return False
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
        status_by_action = {
            "sent": "sent",
            "waiting": "waiting",
            "pending": "waiting",
            "not_sent": "not_sent",
        }
        status = status_by_action.get(action, "")
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

    def _set_contact_tracking_data(
        self,
        index: QModelIndex,
        value: object,
        role: int,
    ) -> bool:
        if not self._automatic_mode or role not in (Qt.ItemDataRole.EditRole, Qt.ItemDataRole.UserRole):
            return False

        action = str(value or "").strip().casefold()
        if ":" not in action:
            return False
        channel, status = action.split(":", 1)
        if channel not in CONTACT_TRACKING_CHANNELS or status not in CONTACT_TRACKING_STATUS_VALUES:
            return False

        row = self._rows[index.row()]
        current_status = self._contact_tracking_status(row, channel)
        next_status = "" if current_status == status else status
        if self._contact_status_changed is not None and not self._contact_status_changed(
            row.id,
            channel,
            next_status,
        ):
            return False

        self._set_local_contact_tracking_status(row, channel, next_status)
        self.dataChanged.emit(
            index,
            index,
            [
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.UserRole,
                Qt.ItemDataRole.ToolTipRole,
                Qt.ItemDataRole.BackgroundRole,
            ],
        )
        return True

    def _contact_tracking_statuses(self, row: GuestRowDTO) -> dict[str, str]:
        return {
            "call": self._contact_tracking_status(row, "call"),
        }

    def _contact_tracking_status(self, row: GuestRowDTO, channel: str) -> str:
        if channel == "call":
            phone_status = str(row.contact_statuses.get("phone", "")).strip().casefold()
            mobile_status = str(row.contact_statuses.get("mobile", "")).strip().casefold()
            if phone_status and mobile_status and phone_status != mobile_status:
                return phone_status
            return phone_status or mobile_status
        return str(row.contact_statuses.get(channel, "")).strip().casefold()

    def _set_local_contact_tracking_status(self, row: GuestRowDTO, channel: str, status: str) -> None:
        if channel == "call":
            row.contact_statuses["phone"] = status
            row.contact_statuses["mobile"] = status
            return
        row.contact_statuses[channel] = status

    def _is_editable_data_cell(self, index: QModelIndex) -> bool:
        if not index.isValid():
            return False
        column_name = self._data_column_for_table_column(index.column())
        return column_name in self._editable_columns if column_name is not None else False

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

    def column_identifier(self, table_column: int) -> str:
        if table_column < 0 or table_column >= self.columnCount():
            return ""
        system_identifier = self._system_column_identifier(table_column)
        if system_identifier is not None:
            return f"system:{system_identifier}"
        data_column = self._data_column_for_table_column(table_column)
        return f"data:{data_column}" if data_column is not None else ""

    def data_column_name(self, table_column: int) -> str | None:
        return self._data_column_for_table_column(table_column)

    def system_column_index(self, identifier: str) -> int | None:
        try:
            return self._system_column_identifiers().index(identifier)
        except ValueError:
            return None

    def _system_column_identifiers(self) -> tuple[str, ...]:
        return AUTOMATIC_SYSTEM_COLUMN_IDENTIFIERS if self._automatic_mode else BASE_SYSTEM_COLUMN_IDENTIFIERS

    def _data_column_offset(self) -> int:
        return len(self._system_column_identifiers())

    def _system_column_identifier(self, table_column: int) -> str | None:
        if table_column < 0:
            return None
        identifiers = self._system_column_identifiers()
        if table_column >= len(identifiers):
            return None
        return identifiers[table_column]

    def _data_column_for_table_column(self, table_column: int) -> str | None:
        data_index = table_column - self._data_column_offset()
        if data_index < 0 or data_index >= len(self._columns):
            return None
        return self._columns[data_index]

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
        return self._has_multiline_cells

    def _cell_line_count(self, row: GuestRowDTO, table_column: int) -> int:
        column_name = self._data_column_for_table_column(table_column)
        if column_name is None:
            return 1
        value = str(row.data.get(column_name, ""))
        return max(value.count("\n") + 1, 1)

    def _find_category_column_indexes(self) -> set[int]:
        indexes: set[int] = set()
        for column_index, column_name in enumerate(self._columns, start=self._data_column_offset()):
            normalized_column = self._normalize_text(column_name)
            if "categoria" in normalized_column or "category" in normalized_column:
                indexes.add(column_index)
        return indexes

    def _category_value(self, row: GuestRowDTO, table_column: int) -> str:
        column_name = self._data_column_for_table_column(table_column)
        if column_name is None:
            return ""
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
