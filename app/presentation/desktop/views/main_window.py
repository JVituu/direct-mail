from math import ceil
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.application.dtos.guest_dto import ImportResultDTO
from app.presentation.desktop.viewmodels.main_view_model import MainViewModel
from app.presentation.desktop.widgets.guest_table_model import GuestTableModel


class ImportWorker(QObject):
    progress = Signal(int)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        view_model: MainViewModel,
        file_path: str,
        sheet_name: str,
    ) -> None:
        super().__init__()
        self._view_model = view_model
        self._file_path = file_path
        self._sheet_name = sheet_name

    @Slot()
    def run(self) -> None:
        try:
            result = self._view_model.import_spreadsheet(
                file_path=self._file_path,
                sheet_name=self._sheet_name,
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
        self._current_page = 0
        self._current_search = ""
        self._table_model: GuestTableModel | None = None
        self._import_thread: QThread | None = None
        self._import_worker: ImportWorker | None = None

        self.setWindowTitle("Mala Direta")
        self.resize(1200, 760)
        self._build_ui()
        self._load_imports()

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)

        top_bar = QHBoxLayout()
        self.import_button = QPushButton("Importar XLSX")
        self.import_button.clicked.connect(self._choose_file)
        top_bar.addWidget(self.import_button)

        self.export_button = QPushButton("Exportar selecionados")
        self.export_button.clicked.connect(self._export_selected)
        top_bar.addWidget(self.export_button)

        self.import_combo = QComboBox()
        self.import_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.import_combo.currentIndexChanged.connect(self._on_import_changed)
        top_bar.addWidget(self.import_combo)
        layout.addLayout(top_bar)

        filter_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar em qualquer coluna")
        self.search_input.returnPressed.connect(self._apply_search)
        filter_bar.addWidget(self.search_input)

        self.search_button = QPushButton("Buscar")
        self.search_button.clicked.connect(self._apply_search)
        filter_bar.addWidget(self.search_button)

        self.clear_search_button = QPushButton("Limpar")
        self.clear_search_button.clicked.connect(self._clear_search)
        filter_bar.addWidget(self.clear_search_button)

        filter_bar.addWidget(QLabel("Linhas por página"))
        self.page_size_input = QSpinBox()
        self.page_size_input.setRange(50, 5000)
        self.page_size_input.setSingleStep(50)
        self.page_size_input.setValue(500)
        self.page_size_input.valueChanged.connect(self._change_page_size)
        filter_bar.addWidget(self.page_size_input)
        layout.addLayout(filter_bar)

        selection_bar = QHBoxLayout()
        self.select_page_button = QPushButton("Selecionar página")
        self.select_page_button.clicked.connect(lambda: self._set_page_selection(True))
        selection_bar.addWidget(self.select_page_button)

        self.clear_page_button = QPushButton("Limpar página")
        self.clear_page_button.clicked.connect(lambda: self._set_page_selection(False))
        selection_bar.addWidget(self.clear_page_button)

        self.select_all_button = QPushButton("Selecionar todos filtrados")
        self.select_all_button.clicked.connect(lambda: self._set_all_filtered_selection(True))
        selection_bar.addWidget(self.select_all_button)

        self.clear_all_button = QPushButton("Limpar todos filtrados")
        self.clear_all_button.clicked.connect(lambda: self._set_all_filtered_selection(False))
        selection_bar.addWidget(self.clear_all_button)

        selection_bar.addStretch()
        layout.addLayout(selection_bar)

        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setDefaultSectionSize(160)
        self.table.verticalHeader().setDefaultSectionSize(26)
        layout.addWidget(self.table)

        page_bar = QHBoxLayout()
        self.first_page_button = QPushButton("Primeira")
        self.first_page_button.clicked.connect(self._go_first_page)
        page_bar.addWidget(self.first_page_button)

        self.previous_page_button = QPushButton("Anterior")
        self.previous_page_button.clicked.connect(self._go_previous_page)
        page_bar.addWidget(self.previous_page_button)

        self.next_page_button = QPushButton("Próxima")
        self.next_page_button.clicked.connect(self._go_next_page)
        page_bar.addWidget(self.next_page_button)

        self.last_page_button = QPushButton("Última")
        self.last_page_button.clicked.connect(self._go_last_page)
        page_bar.addWidget(self.last_page_button)

        self.page_label = QLabel("Nenhuma planilha importada")
        page_bar.addWidget(self.page_label)
        page_bar.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(180)
        page_bar.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        page_bar.addWidget(self.status_label)
        layout.addLayout(page_bar)

        self.setCentralWidget(root)

    def _choose_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar planilha",
            str(Path.home()),
            "Planilhas Excel (*.xlsx)",
        )
        if not file_path:
            return

        try:
            sheets = self._view_model.list_sheets(file_path)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao abrir planilha", str(exc))
            return

        if not sheets:
            QMessageBox.warning(self, "Planilha vazia", "A planilha não possui abas.")
            return

        sheet_name = sheets[0]
        if len(sheets) > 1:
            selected_sheet, accepted = QInputDialog.getItem(
                self,
                "Selecionar aba",
                "Aba da planilha:",
                sheets,
                0,
                False,
            )
            if not accepted:
                return
            sheet_name = selected_sheet

        self._start_import(file_path, sheet_name)

    def _start_import(self, file_path: str, sheet_name: str) -> None:
        self._set_busy(True)
        self.status_label.setText("Importando 0 linhas...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        thread = QThread(self)
        worker = ImportWorker(self._view_model, file_path, sheet_name)
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

    @Slot(int)
    def _on_import_progress(self, imported_rows: int) -> None:
        self.status_label.setText(f"Importando {imported_rows} linhas...")

    @Slot(object)
    def _on_import_finished(self, result: ImportResultDTO) -> None:
        self._set_busy(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.status_label.setText(f"{result.total_rows} linhas importadas.")
        self._load_imports(preferred_import_id=result.import_id)
        QMessageBox.information(
            self,
            "Importação concluída",
            f"{result.total_rows} linhas importadas da aba '{result.sheet_name}'.",
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
        self.import_combo.blockSignals(True)
        self.import_combo.clear()

        for imported_file in imports:
            label = (
                f"{imported_file.id} - {imported_file.file_name} | "
                f"{imported_file.sheet_name} | {imported_file.total_rows} linhas"
            )
            self.import_combo.addItem(label, imported_file.id)

        self.import_combo.blockSignals(False)

        if not imports:
            self._current_import_id = None
            self._set_table_page([], tuple(), 0, 0, 0)
            self._update_actions()
            return

        target_index = 0
        if preferred_import_id is not None:
            for index in range(self.import_combo.count()):
                if self.import_combo.itemData(index) == preferred_import_id:
                    target_index = index
                    break

        self.import_combo.setCurrentIndex(target_index)
        self._current_import_id = int(self.import_combo.currentData())
        self._current_page = 0
        self._load_current_page()
        self._update_actions()

    def _on_import_changed(self) -> None:
        data = self.import_combo.currentData()
        self._current_import_id = int(data) if data is not None else None
        self._current_page = 0
        self._load_current_page()

    def _apply_search(self) -> None:
        self._current_search = self.search_input.text().strip()
        self._current_page = 0
        self._load_current_page()

    def _clear_search(self) -> None:
        self.search_input.clear()
        self._current_search = ""
        self._current_page = 0
        self._load_current_page()

    def _change_page_size(self) -> None:
        self._current_page = 0
        self._load_current_page()

    def _load_current_page(self) -> None:
        if self._current_import_id is None:
            self._set_table_page([], tuple(), 0, 0, 0)
            return

        try:
            page = self._view_model.load_guests(
                import_id=self._current_import_id,
                page=self._current_page,
                page_size=self.page_size_input.value(),
                search=self._current_search,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao carregar dados", str(exc))
            return

        max_page_index = max(ceil(page.total_rows / page.page_size) - 1, 0)
        if self._current_page > max_page_index:
            self._current_page = max_page_index
            self._load_current_page()
            return

        self._set_table_page(
            rows=page.rows,
            columns=page.columns,
            total_rows=page.total_rows,
            selected_rows=page.selected_rows,
            page_size=page.page_size,
        )

    def _set_table_page(
        self,
        rows: list[object],
        columns: tuple[str, ...],
        total_rows: int,
        selected_rows: int,
        page_size: int,
    ) -> None:
        self._table_model = GuestTableModel(rows, columns, self._on_row_selection_changed)
        self.table.setModel(self._table_model)
        self.table.setColumnWidth(0, 105)
        self.table.setColumnWidth(1, 70)

        if total_rows == 0:
            self.page_label.setText("Nenhum registro encontrado")
        else:
            total_pages = max(ceil(total_rows / max(page_size, 1)), 1)
            self.page_label.setText(
            f"Página {self._current_page + 1} de {total_pages} | "
                f"{total_rows} registros | {selected_rows} selecionados"
            )
        self._update_actions(total_rows=total_rows, page_size=page_size)

    def _on_row_selection_changed(self, guest_id: int, selected: bool) -> None:
        try:
            self._view_model.set_guest_selected(guest_id, selected)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao selecionar", str(exc))

    def _set_page_selection(self, selected: bool) -> None:
        if self._table_model is None:
            return
        guest_ids = self._table_model.guest_ids()
        if not guest_ids:
            return
        try:
            self._view_model.set_page_selected(guest_ids, selected)
            self._load_current_page()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao atualizar seleção", str(exc))

    def _set_all_filtered_selection(self, selected: bool) -> None:
        if self._current_import_id is None:
            return

        action = "selecionar" if selected else "limpar"
        answer = QMessageBox.question(
            self,
            "Confirmar seleção",
            f"Deseja {action} todos os registros do filtro atual?",
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
            self._load_current_page()
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao atualizar seleção", str(exc))

    def _export_selected(self) -> None:
        if self._current_import_id is None:
            QMessageBox.warning(self, "Nenhuma planilha", "Importe uma planilha antes de exportar.")
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar lista selecionada",
            str(Path.home() / "convidados_selecionados.xlsx"),
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

    def _go_first_page(self) -> None:
        self._current_page = 0
        self._load_current_page()

    def _go_previous_page(self) -> None:
        self._current_page = max(self._current_page - 1, 0)
        self._load_current_page()

    def _go_next_page(self) -> None:
        self._current_page += 1
        self._load_current_page()

    def _go_last_page(self) -> None:
        if self._current_import_id is None:
            return
        page = self._view_model.load_guests(
            import_id=self._current_import_id,
            page=0,
            page_size=self.page_size_input.value(),
            search=self._current_search,
        )
        self._current_page = max(ceil(page.total_rows / page.page_size) - 1, 0)
        self._load_current_page()

    def _set_busy(self, busy: bool) -> None:
        self.import_button.setEnabled(not busy)
        self.export_button.setEnabled(not busy)
        self.import_combo.setEnabled(not busy)
        self.search_input.setEnabled(not busy)
        self.search_button.setEnabled(not busy)
        self.clear_search_button.setEnabled(not busy)
        self.select_page_button.setEnabled(not busy)
        self.clear_page_button.setEnabled(not busy)
        self.select_all_button.setEnabled(not busy)
        self.clear_all_button.setEnabled(not busy)
        self.page_size_input.setEnabled(not busy)
        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    def _update_actions(self, total_rows: int = 0, page_size: int = 0) -> None:
        has_import = self._current_import_id is not None
        has_rows = total_rows > 0
        self.export_button.setEnabled(has_import)
        self.search_button.setEnabled(has_import)
        self.clear_search_button.setEnabled(has_import)
        self.select_page_button.setEnabled(has_rows)
        self.clear_page_button.setEnabled(has_rows)
        self.select_all_button.setEnabled(has_rows)
        self.clear_all_button.setEnabled(has_rows)
        self.first_page_button.setEnabled(has_import and self._current_page > 0)
        self.previous_page_button.setEnabled(has_import and self._current_page > 0)
        self.next_page_button.setEnabled(has_import and total_rows > (self._current_page + 1) * page_size)
        self.last_page_button.setEnabled(has_import and total_rows > (self._current_page + 1) * page_size)
