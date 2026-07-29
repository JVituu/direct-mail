from math import ceil
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.application.dtos.guest_dto import WorkbookImportResultDTO
from app.presentation.desktop.viewmodels.main_view_model import MainViewModel
from app.presentation.desktop.widgets.guest_table_model import GuestTableModel


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
        self._current_import_id: int | None = None
        self._current_search = ""
        self._source_page = 0
        self._selected_page = 0
        self._source_total_rows = 0
        self._source_page_size = 0
        self._selected_total_rows = 0
        self._selected_page_size = 0
        self._source_model: GuestTableModel | None = None
        self._selected_model: GuestTableModel | None = None
        self._import_thread: QThread | None = None
        self._import_worker: ImportWorker | None = None

        self.setWindowTitle("Mala Direta")
        self.resize(1280, 820)
        self._build_ui()
        self._apply_styles()
        self._load_imports()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("AppRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(12)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_filters())
        layout.addWidget(self._build_selection_actions())
        layout.addWidget(self._build_tabs(), 1)
        layout.addWidget(self._build_status_bar())

        self.setCentralWidget(root)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("Header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        title_box = QVBoxLayout()
        title = QLabel("Mala Direta")
        title.setObjectName("Title")
        subtitle = QLabel("Importe abas do Excel, filtre listas e acompanhe a planilha automática de selecionados.")
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

    def _build_filters(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Lista"))
        self.category_combo = QComboBox()
        self.category_combo.setMinimumWidth(240)
        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        layout.addWidget(self.category_combo)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por nome, telefone, endereço, obra ou qualquer coluna")
        self.search_input.returnPressed.connect(self._apply_search)
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

        return frame

    def _build_selection_actions(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        self.select_page_button = QPushButton("Selecionar página")
        self.select_page_button.clicked.connect(lambda: self._set_page_selection(True))
        layout.addWidget(self.select_page_button)

        self.clear_page_button = QPushButton("Limpar página")
        self.clear_page_button.clicked.connect(lambda: self._set_page_selection(False))
        layout.addWidget(self.clear_page_button)

        self.select_all_button = QPushButton("Selecionar todos filtrados")
        self.select_all_button.clicked.connect(lambda: self._set_all_filtered_selection(True))
        layout.addWidget(self.select_all_button)

        self.clear_all_button = QPushButton("Limpar todos filtrados")
        self.clear_all_button.clicked.connect(lambda: self._set_all_filtered_selection(False))
        layout.addWidget(self.clear_all_button)

        layout.addStretch()
        self.summary_label = QLabel("Nenhuma planilha importada")
        self.summary_label.setObjectName("Summary")
        layout.addWidget(self.summary_label)

        return frame

    def _build_tabs(self) -> QTabWidget:
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_source_tab(), "Planilhas importadas")
        self.tabs.addTab(self._build_selected_tab(), "Planilha automática")
        self.tabs.currentChanged.connect(lambda _: self._update_actions())
        return self.tabs

    def _build_source_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(8)

        self.source_table = self._create_table()
        layout.addWidget(self.source_table, 1)

        page_bar = QHBoxLayout()
        self.source_first_page_button = QPushButton("Primeira")
        self.source_first_page_button.clicked.connect(self._go_source_first_page)
        page_bar.addWidget(self.source_first_page_button)

        self.source_previous_page_button = QPushButton("Anterior")
        self.source_previous_page_button.clicked.connect(self._go_source_previous_page)
        page_bar.addWidget(self.source_previous_page_button)

        self.source_next_page_button = QPushButton("Próxima")
        self.source_next_page_button.clicked.connect(self._go_source_next_page)
        page_bar.addWidget(self.source_next_page_button)

        self.source_last_page_button = QPushButton("Última")
        self.source_last_page_button.clicked.connect(self._go_source_last_page)
        page_bar.addWidget(self.source_last_page_button)

        self.source_page_label = QLabel("Nenhuma planilha importada")
        page_bar.addWidget(self.source_page_label)
        page_bar.addStretch()
        layout.addLayout(page_bar)

        return tab

    def _build_selected_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(8)

        hint = QLabel("Esta é a planilha criada automaticamente conforme você seleciona convidados.")
        hint.setObjectName("Hint")
        layout.addWidget(hint)

        self.selected_table = self._create_table()
        layout.addWidget(self.selected_table, 1)

        page_bar = QHBoxLayout()
        self.selected_first_page_button = QPushButton("Primeira")
        self.selected_first_page_button.clicked.connect(self._go_selected_first_page)
        page_bar.addWidget(self.selected_first_page_button)

        self.selected_previous_page_button = QPushButton("Anterior")
        self.selected_previous_page_button.clicked.connect(self._go_selected_previous_page)
        page_bar.addWidget(self.selected_previous_page_button)

        self.selected_next_page_button = QPushButton("Próxima")
        self.selected_next_page_button.clicked.connect(self._go_selected_next_page)
        page_bar.addWidget(self.selected_next_page_button)

        self.selected_last_page_button = QPushButton("Última")
        self.selected_last_page_button.clicked.connect(self._go_selected_last_page)
        page_bar.addWidget(self.selected_last_page_button)

        self.selected_page_label = QLabel("Nenhum convidado selecionado")
        page_bar.addWidget(self.selected_page_label)
        page_bar.addStretch()
        layout.addLayout(page_bar)

        return tab

    def _build_status_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("StatusBar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Pronto")
        layout.addWidget(self.status_label)
        layout.addStretch()

        return frame

    def _create_table(self) -> QTableView:
        table = QTableView()
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setDefaultSectionSize(170)
        table.verticalHeader().setDefaultSectionSize(28)
        return table

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#AppRoot {
                background: #f5f7fb;
                color: #172033;
                font-size: 13px;
            }
            QFrame#Header {
                background: #ffffff;
                border: 1px solid #dde4ef;
                border-radius: 8px;
            }
            QLabel#Title {
                color: #0f2f5f;
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#Subtitle, QLabel#Hint {
                color: #607089;
            }
            QLabel#Summary {
                color: #0f2f5f;
                font-weight: 600;
            }
            QFrame#Panel {
                background: #ffffff;
                border: 1px solid #dde4ef;
                border-radius: 8px;
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
            QLineEdit, QComboBox, QSpinBox {
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
            QTabWidget::pane {
                border: 0;
            }
            QTabBar::tab {
                background: #e9eff7;
                color: #33445f;
                border: 1px solid #cfd9e8;
                border-bottom: 0;
                padding: 9px 16px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0f2f5f;
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
        self.status_label.setText("Importando workbook...")
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
        self._load_imports(preferred_import_id=None)

        skipped = ""
        if result.skipped_sheets:
            skipped = "\n\nAbas ignoradas sem tabela de contatos: " + ", ".join(result.skipped_sheets)
        QMessageBox.information(
            self,
            "Importação concluída",
            (
                f"{len(result.imported_sheets)} listas importadas de '{result.file_name}'.\n"
                f"{result.total_rows} registros disponíveis no sistema."
                f"{skipped}"
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

    def _load_imports(self, preferred_import_id: int | None = None) -> None:
        imports = self._view_model.list_imports()
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem("Todas as listas", None)

        for imported_file in imports:
            label = f"{imported_file.sheet_name} ({imported_file.total_rows})"
            self.category_combo.addItem(label, imported_file.id)

        target_index = 0
        if preferred_import_id is not None:
            for index in range(self.category_combo.count()):
                if self.category_combo.itemData(index) == preferred_import_id:
                    target_index = index
                    break

        self.category_combo.setCurrentIndex(target_index)
        self.category_combo.blockSignals(False)
        self._current_import_id = self.category_combo.currentData()
        self._source_page = 0
        self._selected_page = 0
        self._load_tables()

    def _on_category_changed(self) -> None:
        self._current_import_id = self.category_combo.currentData()
        self._source_page = 0
        self._selected_page = 0
        self._load_tables()

    def _apply_search(self) -> None:
        self._current_search = self.search_input.text().strip()
        self._source_page = 0
        self._selected_page = 0
        self._load_tables()

    def _clear_search(self) -> None:
        self.search_input.clear()
        self._current_search = ""
        self._source_page = 0
        self._selected_page = 0
        self._load_tables()

    def _change_page_size(self) -> None:
        self._source_page = 0
        self._selected_page = 0
        self._load_tables()

    def _load_tables(self) -> None:
        self._load_source_page()
        self._load_selected_page()
        self._update_actions()

    def _load_source_page(self) -> None:
        try:
            page = self._view_model.load_guests(
                import_id=self._current_import_id,
                page=self._source_page,
                page_size=self.page_size_input.value(),
                search=self._current_search,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao carregar dados", str(exc))
            return

        self._source_total_rows = page.total_rows
        self._source_page_size = page.page_size
        self._source_page = self._normalize_page(self._source_page, page.total_rows, page.page_size)
        self._source_model = GuestTableModel(page.rows, page.columns, self._on_source_selection_changed)
        self.source_table.setModel(self._source_model)
        self._configure_table_widths(self.source_table)
        self._update_source_label(page.total_rows, page.selected_rows, page.page_size)

    def _load_selected_page(self) -> None:
        try:
            page = self._view_model.load_guests(
                import_id=self._current_import_id,
                page=self._selected_page,
                page_size=self.page_size_input.value(),
                search=self._current_search,
                selected_only=True,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao carregar selecionados", str(exc))
            return

        self._selected_total_rows = page.total_rows
        self._selected_page_size = page.page_size
        self._selected_page = self._normalize_page(self._selected_page, page.total_rows, page.page_size)
        self._selected_model = GuestTableModel(page.rows, page.columns, self._on_selected_selection_changed)
        self.selected_table.setModel(self._selected_model)
        self._configure_table_widths(self.selected_table)
        self._update_selected_label(page.total_rows, page.page_size)
        self.summary_label.setText(
            f"{self._source_total_rows} registros no filtro | {self._selected_total_rows} na planilha automática"
        )

    def _configure_table_widths(self, table: QTableView) -> None:
        table.setColumnWidth(0, 110)
        table.setColumnWidth(1, 70)
        if table.model() is not None and table.model().columnCount() > 2:
            table.setColumnWidth(2, 150)

    def _normalize_page(self, page: int, total_rows: int, page_size: int) -> int:
        max_page_index = max(ceil(total_rows / max(page_size, 1)) - 1, 0)
        return min(page, max_page_index)

    def _update_source_label(self, total_rows: int, selected_rows: int, page_size: int) -> None:
        if total_rows == 0:
            self.source_page_label.setText("Nenhum registro encontrado")
            return
        total_pages = max(ceil(total_rows / max(page_size, 1)), 1)
        self.source_page_label.setText(
            f"Página {self._source_page + 1} de {total_pages} | "
            f"{total_rows} registros | {selected_rows} selecionados no filtro"
        )

    def _update_selected_label(self, total_rows: int, page_size: int) -> None:
        if total_rows == 0:
            self.selected_page_label.setText("Nenhum convidado selecionado")
            return
        total_pages = max(ceil(total_rows / max(page_size, 1)), 1)
        self.selected_page_label.setText(
            f"Página {self._selected_page + 1} de {total_pages} | "
            f"{total_rows} convidados na planilha automática"
        )

    def _on_source_selection_changed(self, guest_id: int, selected: bool) -> None:
        self._set_single_guest_selected(guest_id, selected)

    def _on_selected_selection_changed(self, guest_id: int, selected: bool) -> None:
        self._set_single_guest_selected(guest_id, selected)

    def _set_single_guest_selected(self, guest_id: int, selected: bool) -> None:
        try:
            self._view_model.set_guest_selected(guest_id, selected)
            self._load_tables()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao selecionar", str(exc))

    def _set_page_selection(self, selected: bool) -> None:
        if self._source_model is None:
            return
        guest_ids = self._source_model.guest_ids()
        if not guest_ids:
            return
        try:
            self._view_model.set_page_selected(guest_ids, selected)
            self._load_tables()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao atualizar seleção", str(exc))

    def _set_all_filtered_selection(self, selected: bool) -> None:
        action = "selecionar" if selected else "limpar"
        label = self.category_combo.currentText() or "o filtro atual"
        answer = QMessageBox.question(
            self,
            "Confirmar seleção",
            f"Deseja {action} todos os registros de '{label}' usando a busca atual?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            updated_rows = self._view_model.set_all_filtered_selected(
                import_id=self._current_import_id,
                selected=selected,
                search=self._current_search,
            )
            self.status_label.setText(f"{updated_rows} registros atualizados.")
            self._load_tables()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao atualizar seleção", str(exc))

    def _export_selected(self) -> None:
        if self._selected_total_rows == 0:
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
            result = self._view_model.export_selected(self._current_import_id, output_path)
            self.status_label.setText(f"{result.total_rows} convidados exportados.")
            QMessageBox.information(
                self,
                "Exportação concluída",
                f"{result.total_rows} convidados exportados para {result.file_name}.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))

    def _go_source_first_page(self) -> None:
        self._source_page = 0
        self._load_source_page()
        self._update_actions()

    def _go_source_previous_page(self) -> None:
        self._source_page = max(self._source_page - 1, 0)
        self._load_source_page()
        self._update_actions()

    def _go_source_next_page(self) -> None:
        self._source_page += 1
        self._load_source_page()
        self._update_actions()

    def _go_source_last_page(self) -> None:
        self._source_page = max(ceil(self._source_total_rows / max(self._source_page_size, 1)) - 1, 0)
        self._load_source_page()
        self._update_actions()

    def _go_selected_first_page(self) -> None:
        self._selected_page = 0
        self._load_selected_page()
        self._update_actions()

    def _go_selected_previous_page(self) -> None:
        self._selected_page = max(self._selected_page - 1, 0)
        self._load_selected_page()
        self._update_actions()

    def _go_selected_next_page(self) -> None:
        self._selected_page += 1
        self._load_selected_page()
        self._update_actions()

    def _go_selected_last_page(self) -> None:
        self._selected_page = max(ceil(self._selected_total_rows / max(self._selected_page_size, 1)) - 1, 0)
        self._load_selected_page()
        self._update_actions()

    def _set_busy(self, busy: bool) -> None:
        widgets = (
            self.import_button,
            self.export_button,
            self.category_combo,
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
        has_rows = self._source_total_rows > 0
        has_selected = self._selected_total_rows > 0
        self.export_button.setEnabled(has_selected)
        self.search_button.setEnabled(self.category_combo.count() > 1)
        self.clear_search_button.setEnabled(self.category_combo.count() > 1)
        self.select_page_button.setEnabled(has_rows)
        self.clear_page_button.setEnabled(has_rows)
        self.select_all_button.setEnabled(has_rows)
        self.clear_all_button.setEnabled(has_rows)

        self.source_first_page_button.setEnabled(self._source_page > 0)
        self.source_previous_page_button.setEnabled(self._source_page > 0)
        self.source_next_page_button.setEnabled(
            self._source_total_rows > (self._source_page + 1) * max(self._source_page_size, 1)
        )
        self.source_last_page_button.setEnabled(
            self._source_total_rows > (self._source_page + 1) * max(self._source_page_size, 1)
        )

        self.selected_first_page_button.setEnabled(self._selected_page > 0)
        self.selected_previous_page_button.setEnabled(self._selected_page > 0)
        self.selected_next_page_button.setEnabled(
            self._selected_total_rows > (self._selected_page + 1) * max(self._selected_page_size, 1)
        )
        self.selected_last_page_button.setEnabled(
            self._selected_total_rows > (self._selected_page + 1) * max(self._selected_page_size, 1)
        )
