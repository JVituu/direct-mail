from math import ceil
from pathlib import Path
import re
from unicodedata import combining, normalize

from PySide6.QtCore import QModelIndex, QObject, QThread, Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
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
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QSpinBox,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QTableView,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from app.application.dtos.guest_dto import GuestRowDTO, ImportSummaryDTO, WorkbookImportResultDTO
from app.presentation.desktop.viewmodels.main_view_model import MainViewModel
from app.presentation.desktop.widgets.guest_table_model import GuestTableModel


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
        self._page_size = 0
        self._imports: list[ImportSummaryDTO] = []
        self._available_columns: tuple[str, ...] = tuple()
        self._visible_columns_by_context: dict[str, set[str]] = {}
        self._table_model: GuestTableModel | None = None
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
        layout.setSpacing(12)

        title_box = QVBoxLayout()
        title = QLabel("Mala Direta -  Instituto Ricardo Brennand")
        title.setObjectName("Title")
        subtitle = QLabel("Arquivos Excel viram abas; cada sheet aparece como uma planilha interna.")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box, 1)

        self.import_button = QPushButton("Importar Excel")
        self.import_button.setObjectName("PrimaryButton")
        self.import_button.clicked.connect(self._choose_file)
        layout.addWidget(self.import_button)

        self.export_button = QPushButton("Exportar Excel")
        self.export_button.setObjectName("SuccessButton")
        self.export_button.clicked.connect(self._export_selected)
        layout.addWidget(self.export_button)

        return header

    def _build_workbook_tabs(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)

        label = QLabel("Arquivos")
        label.setObjectName("SmallLabel")
        layout.addWidget(label)

        self.workbook_tabs = QTabBar()
        self.workbook_tabs.setExpanding(False)
        self.workbook_tabs.setUsesScrollButtons(True)
        self.workbook_tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.workbook_tabs.currentChanged.connect(self._on_workbook_changed)
        self.workbook_tabs.customContextMenuRequested.connect(self._show_workbook_context_menu)
        layout.addWidget(self.workbook_tabs, 1)

        self.duplicates_button = QPushButton("Duplicados")
        self.duplicates_button.setToolTip("Ver possíveis registros duplicados")
        self.duplicates_button.setVisible(False)
        self.duplicates_button.clicked.connect(self._open_duplicates_view)
        layout.addWidget(self.duplicates_button)

        return frame

    def _build_filters_and_actions(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        self.filter_button = QPushButton("Filtros")
        self.filter_button.clicked.connect(self._show_column_filter_menu)
        layout.addWidget(self.filter_button)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por nome, telefone, endereço, obra ou qualquer coluna")
        self.search_input.returnPressed.connect(self._apply_search)
        self.search_input.textChanged.connect(self._schedule_live_search)
        self.search_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.search_input, 1)

        self.search_button = QPushButton("Buscar")
        self.search_button.clicked.connect(self._apply_search)
        layout.addWidget(self.search_button)

        self.clear_search_button = QPushButton("Limpar")
        self.clear_search_button.clicked.connect(self._clear_search)
        layout.addWidget(self.clear_search_button)

        layout.addWidget(QLabel("Linhas"))
        self.page_size_input = QSpinBox()
        self.page_size_input.setRange(50, 5000)
        self.page_size_input.setSingleStep(50)
        self.page_size_input.setValue(500)
        self.page_size_input.valueChanged.connect(self._change_page_size)
        layout.addWidget(self.page_size_input)

        self.select_page_button = QPushButton("Selecionar página")
        self.select_page_button.clicked.connect(lambda: self._set_page_selection(True))
        layout.addWidget(self.select_page_button)

        self.clear_page_button = QPushButton("Limpar página")
        self.clear_page_button.clicked.connect(lambda: self._set_page_selection(False))
        layout.addWidget(self.clear_page_button)

        self.select_all_button = QPushButton("Selecionar todos")
        self.select_all_button.clicked.connect(lambda: self._set_all_filtered_selection(True))
        layout.addWidget(self.select_all_button)

        self.clear_all_button = QPushButton("Limpar todos")
        self.clear_all_button.clicked.connect(lambda: self._set_all_filtered_selection(False))
        layout.addWidget(self.clear_all_button)

        return frame

    def _build_sheet_tabs(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("SheetBar")
        self.sheet_frame = frame
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        label = QLabel("Abas")
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
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setDefaultSectionSize(170)
        table.verticalHeader().setDefaultSectionSize(28)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.setWordWrap(True)
        table.clicked.connect(self._on_table_clicked)
        return table

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
            QLineEdit, QSpinBox {
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
        self.status_label.setText(f"{result.total_rows} linhas importadas.")
        self._load_workbooks(preferred_workbook_id=result.workbook_id)

        selectable_count = sum(1 for sheet in result.imported_sheets if sheet.is_selectable)
        QMessageBox.information(
            self,
            "Importação concluída",
            (
                f"Arquivo '{result.file_name}' importado.\n"
                f"{len(result.imported_sheets)} abas carregadas, "
                f"{selectable_count} listas selecionáveis."
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

    def _load_workbooks(self, preferred_workbook_id: int | None = None) -> None:
        workbooks = self._view_model.list_workbooks()

        self.workbook_tabs.blockSignals(True)
        self._clear_tab_bar(self.workbook_tabs)
        for workbook in workbooks:
            self.workbook_tabs.addTab(f"{workbook.display_name} ({workbook.total_rows})")
            self.workbook_tabs.setTabData(
                self.workbook_tabs.count() - 1,
                {"kind": "workbook", "workbook_id": workbook.id},
            )
        duplicates_count = self._duplicates_count()
        self._update_duplicates_button(duplicates_count)
        automatic_count = self._automatic_selected_count()
        if workbooks and automatic_count > 0:
            self.workbook_tabs.addTab(self._automatic_tab_text(automatic_count))
            self.workbook_tabs.setTabData(
                self.workbook_tabs.count() - 1,
                {"kind": "automatic", "workbook_id": None},
            )
        self.workbook_tabs.blockSignals(False)

        if not workbooks:
            self._current_workbook_id = None
            self._automatic_mode = False
            self._duplicates_mode = False
            self._imports = []
            self._load_sheet_tabs()
            self._update_actions()
            return

        target_index = 0
        if preferred_workbook_id is not None:
            for index in range(self.workbook_tabs.count()):
                tab_data = self.workbook_tabs.tabData(index)
                if tab_data and tab_data["kind"] == "workbook" and tab_data["workbook_id"] == preferred_workbook_id:
                    target_index = index
                    break
        self.workbook_tabs.setCurrentIndex(target_index)
        self._on_workbook_changed(target_index)

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
        self.search_input.clear()
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

        self.sheet_frame.setVisible(True)
        previous_data = self.sheet_tabs.tabData(self.sheet_tabs.currentIndex())
        self.sheet_tabs.blockSignals(True)
        self._clear_tab_bar(self.sheet_tabs)

        self._imports = self._view_model.list_imports(self._current_workbook_id) if self._current_workbook_id else []
        for imported_sheet in self._imports:
            label = imported_sheet.sheet_name
            if imported_sheet.is_selectable:
                label = f"{label} ({imported_sheet.total_rows})"
            else:
                label = f"{label} · visualização"
            self.sheet_tabs.addTab(label)
            self.sheet_tabs.setTabData(
                self.sheet_tabs.count() - 1,
                {
                    "kind": "sheet",
                    "import_id": imported_sheet.id,
                    "selectable": imported_sheet.is_selectable,
                },
            )

        self.sheet_tabs.blockSignals(False)
        target_index = self._find_matching_sheet_tab(previous_data)
        self.sheet_tabs.setCurrentIndex(target_index if target_index >= 0 else (0 if self.sheet_tabs.count() else -1))
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

        selected_action = menu.exec(self.filter_button.mapToGlobal(self.filter_button.rect().bottomLeft()))
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
        apply_button = QPushButton("Aplicar")
        cancel_button = QPushButton("Cancelar")
        show_all_button.clicked.connect(lambda: self._set_all_column_items_checked(column_list, True))
        apply_button.clicked.connect(lambda: self._apply_column_filter_from_list(column_list, menu))
        cancel_button.clicked.connect(menu.close)
        buttons_layout.addWidget(show_all_button)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(cancel_button)
        buttons_layout.addWidget(apply_button)
        layout.addLayout(buttons_layout)

        widget_action = QWidgetAction(menu)
        widget_action.setDefaultWidget(container)
        menu.addAction(widget_action)
        menu.exec(self.filter_button.mapToGlobal(self.filter_button.rect().bottomLeft()))

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

    def _apply_column_filter(
        self,
        columns: tuple[str, ...],
        editable_columns: tuple[str, ...],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        self._available_columns = columns
        if not columns:
            return tuple(), tuple()

        visible_column_names = self._visible_columns_for_current_context(columns)
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
            self.filter_button.setText("Filtros")
            return
        self.filter_button.setText(f"Filtros ({len(visible_columns)}/{len(self._available_columns)})")

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
        self.duplicates_button.setVisible(count > 0)
        self.duplicates_button.setText(f"Duplicados ({count})" if count > 0 else "Duplicados")
        self.duplicates_button.setEnabled(count > 0)

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
        self.search_input.clear()
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
        self._current_page = 0
        self._load_table()

    def _apply_search(self) -> None:
        self._search_timer.stop()
        self._apply_search_text(self.search_input.text())

    def _schedule_live_search(self) -> None:
        self._search_timer.start()

    def _apply_live_search(self) -> None:
        self._apply_search_text(self.search_input.text())

    def _apply_search_text(self, search_text: str) -> None:
        search = search_text.strip()
        if search == self._current_search:
            return
        self._current_search = search
        self._current_page = 0
        self._load_table()

    def _clear_search(self) -> None:
        self.search_input.clear()
        self._search_timer.stop()
        self._apply_search_text("")

    def _change_page_size(self) -> None:
        self._current_page = 0
        self._load_table()

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
            self._set_table_page([], tuple(), tuple(), 0, 0, 0)
            return

        try:
            page = self._view_model.load_guests(
                import_id=import_id,
                workbook_id=workbook_id,
                page=self._current_page,
                page_size=self.page_size_input.value(),
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
        rows: list[object],
        columns: tuple[str, ...],
        editable_columns: tuple[str, ...],
        total_rows: int,
        selected_rows: int,
        page_size: int,
    ) -> None:
        self._total_rows = total_rows
        self._selected_rows = selected_rows
        self._page_size = page_size
        columns, editable_columns = self._apply_column_filter(columns, editable_columns)
        self._table_model = GuestTableModel(
            rows,
            columns,
            editable_columns,
            self._on_row_selection_changed,
            self._on_cell_changed,
            highlight_selected_rows=not self._automatic_mode,
        )
        self.table.setModel(self._table_model)
        self.table.setColumnWidth(0, 110)
        self.table.setColumnWidth(1, 95)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 70)
        if self.table.model() is not None and self.table.model().columnCount() > 4:
            self.table.setColumnWidth(4, 190)
        if self._table_model.has_multiline_cells():
            self.table.resizeRowsToContents()
        self._update_filter_button_text(columns)
        self._update_page_label()
        self._update_actions()

    def _update_page_label(self) -> None:
        if self._total_rows == 0:
            if self._automatic_mode:
                message = "Nenhum convidado selecionado"
            elif self._duplicates_mode:
                message = "Nenhum duplicado encontrado"
            else:
                message = "Nenhum registro encontrado"
            self.page_label.setText(message)
            return

        total_pages = max(ceil(self._total_rows / max(self._page_size, 1)), 1)
        suffix = "na planilha automática" if self._automatic_mode else f"{self._selected_rows} selecionados"
        if self._duplicates_mode:
            suffix = "possíveis duplicados"
        self.page_label.setText(
            f"Página {self._current_page + 1} de {total_pages} | {self._total_rows} registros | {suffix}"
        )

    def _normalize_page(self, page: int, total_rows: int, page_size: int) -> int:
        max_page_index = max(ceil(total_rows / max(page_size, 1)) - 1, 0)
        return min(page, max_page_index)

    def _on_row_selection_changed(self, guest_id: int, selected: bool) -> None:
        try:
            selected_guest_id = guest_id
            if selected and not self._automatic_mode:
                reviewed_guest_id = self._review_duplicate_selection(guest_id)
                if reviewed_guest_id is None:
                    self._load_table()
                    return
                selected_guest_id = reviewed_guest_id
                if not self._confirm_automatic_conflicts(selected_guest_id):
                    self._load_table()
                    return

            self._view_model.set_guest_selected(selected_guest_id, selected)
            if selected and selected_guest_id != guest_id:
                self.status_label.setText("Registro selecionado após revisão de duplicidade.")
            self._refresh_automatic_tab_label()
            self._load_table()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao selecionar", str(exc))

    def _review_duplicate_selection(self, guest_id: int) -> int | None:
        candidates = self._view_model.list_duplicate_candidates(guest_id)
        if len(candidates) <= 1:
            return guest_id

        dialog = QDialog(self)
        dialog.setWindowTitle("Duplicidade encontrada")
        dialog.resize(1220, 440)
        layout = QVBoxLayout(dialog)

        message = QLabel(
            "Encontrei duplicidade. Selecione o registro correto para enviar para a Planilha automática."
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        table = self._build_guest_review_table(candidates)
        layout.addWidget(table, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText("Enviar selecionado")
        if cancel_button is not None:
            cancel_button.setText("Cancelar")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        table.itemDoubleClicked.connect(lambda _: dialog.accept())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        selected_ranges = table.selectedRanges()
        if not selected_ranges:
            return None
        selected_row = selected_ranges[0].topRow()
        item = table.item(selected_row, 0)
        if item is None:
            return None
        return int(item.data(Qt.ItemDataRole.UserRole))

    def _confirm_automatic_conflicts(self, guest_id: int) -> bool:
        conflicts = self._view_model.list_automatic_conflicts(guest_id)
        if not conflicts:
            return True

        dialog = QDialog(self)
        dialog.setWindowTitle("Conferir Planilha automática")
        dialog.resize(1220, 440)
        layout = QVBoxLayout(dialog)

        message = QLabel(
            "Já tem dados parecidos com esses na Planilha automática. "
            "Confira nome, telefone, celular, e-mail, CEP e endereço antes de adicionar."
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        table = self._build_guest_review_table(conflicts)
        layout.addWidget(table, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setText("Adicionar mesmo assim")
        if cancel_button is not None:
            cancel_button.setText("Cancelar")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        return dialog.exec() == QDialog.DialogCode.Accepted

    def _build_guest_review_table(self, rows: list[GuestRowDTO]) -> QTableWidget:
        table = QTableWidget(len(rows), 9)
        table.setHorizontalHeaderLabels(
            ["Código", "Duplicidade", "Lista", "Nome", "Telefone", "Celular", "E-mail", "CEP", "Endereço"]
        )
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
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
                item.setToolTip(str(value))
                table.setItem(row_index, column_index, item)

        if rows:
            table.selectRow(0)
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
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

    def _on_table_clicked(self, index: QModelIndex) -> None:
        if not index.isValid() or index.column() != 0 or self._table_model is None:
            return
        self._table_model.toggle_selection(index.row())

    def _set_page_selection(self, selected: bool) -> None:
        if self._table_model is None:
            return
        guest_ids = self._table_model.guest_ids()
        if not guest_ids:
            return
        try:
            self._view_model.set_page_selected(guest_ids, selected)
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

        menu = QMenu(self)
        rename_action = menu.addAction("Renomear planilha")
        delete_action = menu.addAction("Excluir planilha")
        selected_action = menu.exec(self.workbook_tabs.mapToGlobal(position))

        if tab_data["kind"] == "automatic":
            if selected_action == rename_action:
                self._rename_automatic_sheet()
            elif selected_action == delete_action:
                self._delete_automatic_sheet()
            return

        if tab_data["kind"] != "workbook":
            return

        workbook_id = int(tab_data["workbook_id"])
        workbook_name = self.workbook_tabs.tabText(index)
        if selected_action == rename_action:
            self._rename_workbook(workbook_id, workbook_name)
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
            self.search_input.clear()
            self._current_page = 0
            self.status_label.setText(
                f"Planilha automática excluída. {updated_rows} registros removidos da lista final."
            )
            self._load_workbooks()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao excluir", str(exc))

    def _export_selected(self) -> None:
        if self._automatic_mode:
            selected_count = self._selected_rows
            workbook_id = None
        elif self._current_workbook_id is not None:
            workbook_id = self._current_workbook_id
            selected_count = self._view_model.load_guests(
                import_id=None,
                workbook_id=workbook_id,
                page=0,
                page_size=50,
                selected_only=True,
            ).total_rows
        else:
            return

        if selected_count == 0:
            QMessageBox.warning(
                self,
                "Nenhum selecionado",
                "Selecione pelo menos um convidado antes de exportar.",
            )
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar planilha automática",
            str(Path.home() / "mala_direta_selecionados.xlsx"),
            "Planilhas Excel (*.xlsx)",
        )
        if not output_path:
            return

        try:
            result = self._view_model.export_selected(
                import_id=None,
                workbook_id=workbook_id,
                output_path=output_path,
            )
            self.status_label.setText(f"{result.total_rows} convidados exportados.")
            QMessageBox.information(
                self,
                "Exportação concluída",
                f"{result.total_rows} convidados exportados para {result.file_name}.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))

    def _go_first_page(self) -> None:
        self._current_page = 0
        self._load_table()

    def _go_previous_page(self) -> None:
        self._current_page = max(self._current_page - 1, 0)
        self._load_table()

    def _go_next_page(self) -> None:
        self._current_page += 1
        self._load_table()

    def _go_last_page(self) -> None:
        self._current_page = max(ceil(self._total_rows / max(self._page_size, 1)) - 1, 0)
        self._load_table()

    def _set_busy(self, busy: bool) -> None:
        widgets = (
            self.import_button,
            self.export_button,
            self.workbook_tabs,
            self.sheet_tabs,
            self.duplicates_button,
            self.filter_button,
            self.search_input,
            self.search_button,
            self.clear_search_button,
            self.select_page_button,
            self.clear_page_button,
            self.select_all_button,
            self.clear_all_button,
            self.page_size_input,
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
        can_select = (
            has_workbook
            and self._current_sheet_selectable
            and not self._automatic_mode
            and not self._duplicates_mode
            and self._total_rows > 0
        )
        can_clear_page = has_workspace and self._table_model is not None and bool(self._table_model.guest_ids())
        has_next = self._total_rows > (self._current_page + 1) * max(self._page_size, 1)

        self.search_button.setEnabled(has_workspace)
        self.clear_search_button.setEnabled(has_workspace)
        self.filter_button.setEnabled(has_workspace and bool(self._available_columns))
        self.export_button.setEnabled(has_workbook or self._automatic_mode)
        self.select_page_button.setEnabled(can_select)
        self.clear_page_button.setEnabled(can_clear_page)
        self.select_all_button.setEnabled(can_select)
        self.clear_all_button.setEnabled(can_select or (self._automatic_mode and self._total_rows > 0))
        self.first_page_button.setEnabled(self._current_page > 0)
        self.previous_page_button.setEnabled(self._current_page > 0)
        self.next_page_button.setEnabled(has_next)
        self.last_page_button.setEnabled(has_next)
