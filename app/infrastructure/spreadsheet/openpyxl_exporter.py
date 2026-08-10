from collections.abc import Iterable, Sequence
from pathlib import Path
import re

from openpyxl import Workbook
from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QPageLayout,
    QPageSize,
    QPainter,
    QPdfWriter,
    QPen,
)

from app.domain.entities.guest_record import GuestRecord


class OpenpyxlSelectedGuestsExporter:
    _qt_app: QGuiApplication | None = None

    def export(
        self,
        output_path: str,
        columns: Sequence[str],
        guests: Iterable[GuestRecord],
        sheet_name: str = "Selecionados",
    ) -> int:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        workbook = Workbook(write_only=True)
        worksheet = workbook.create_sheet(self._safe_sheet_name(sheet_name, set()))
        worksheet.append(list(columns))

        count = 0
        for guest in guests:
            worksheet.append([guest.data.get(column, "") for column in columns])
            count += 1

        workbook.save(path)
        workbook.close()
        return count

    def export_by_category(
        self,
        output_path: str,
        columns: Sequence[str],
        guests: Iterable[GuestRecord],
        category_column: str,
    ) -> int:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        grouped_guests: dict[str, list[GuestRecord]] = {}
        for guest in guests:
            category = self._category_value(guest.data.get(category_column, ""))
            grouped_guests.setdefault(category, []).append(guest)

        workbook = Workbook(write_only=True)
        used_sheet_names = {"Resumo"}
        summary = workbook.create_sheet("Resumo")
        summary.append(["Categoria", "Quantidade"])

        total = 0
        for category in sorted(grouped_guests, key=str.casefold):
            category_guests = grouped_guests[category]
            summary.append([category, len(category_guests)])
            total += len(category_guests)

        for category in sorted(grouped_guests, key=str.casefold):
            worksheet = workbook.create_sheet(self._safe_sheet_name(category, used_sheet_names))
            worksheet.append(list(columns))
            for guest in grouped_guests[category]:
                worksheet.append([guest.data.get(column, "") for column in columns])

        workbook.save(path)
        workbook.close()
        return total

    def export_name_checklist_pdf(
        self,
        output_path: str,
        guests: Iterable[GuestRecord],
        title: str,
    ) -> int:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        names = [self._first_line(guest.data.get("Nome", "")) for guest in guests]
        names = [name for name in names if name]

        self._ensure_gui_application()
        writer = QPdfWriter(str(path))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageMargins(QMarginsF(14, 14, 14, 14), QPageLayout.Unit.Millimeter)
        writer.setResolution(96)

        painter = QPainter(writer)
        try:
            self._draw_name_checklist_pdf(painter, writer, title, names)
        finally:
            painter.end()
        return len(names)

    def _draw_name_checklist_pdf(
        self,
        painter: QPainter,
        writer: QPdfWriter,
        title: str,
        names: Sequence[str],
    ) -> None:
        margin = 46
        page_width = writer.width()
        page_height = writer.height()
        left = margin
        right = page_width - margin
        top = margin
        bottom = page_height - margin
        content_width = right - left

        title_font = QFont("Arial", 15)
        title_font.setBold(True)
        meta_font = QFont("Arial", 9)
        name_font = QFont("Arial", 11)
        line_pen = QPen(QColor("#d1d5db"))
        text_color = QColor("#111827")
        muted_color = QColor("#4b5563")

        page_number = 1

        def draw_header() -> float:
            painter.setPen(text_color)
            painter.setFont(title_font)
            painter.drawText(QRectF(left, top, content_width, 24), Qt.AlignmentFlag.AlignLeft, title)
            painter.setPen(muted_color)
            painter.setFont(meta_font)
            painter.drawText(
                QRectF(left, top + 28, content_width, 18),
                Qt.AlignmentFlag.AlignLeft,
                f"{len(names)} nomes para conferência",
            )
            painter.setPen(line_pen)
            painter.drawLine(left, top + 54, right, top + 54)
            return top + 74

        def draw_footer() -> None:
            painter.setPen(muted_color)
            painter.setFont(meta_font)
            painter.drawText(
                QRectF(left, bottom - 18, content_width, 16),
                Qt.AlignmentFlag.AlignRight,
                f"Página {page_number}",
            )

        y = draw_header()
        row_height = 30
        checkbox_size = 12
        checkbox_x = left
        name_x = checkbox_x + checkbox_size + 12
        name_width = content_width - checkbox_size - 12

        painter.setFont(name_font)
        metrics = QFontMetrics(name_font)

        for name in names:
            if y + row_height > bottom - 24:
                draw_footer()
                writer.newPage()
                page_number += 1
                y = draw_header()
                painter.setFont(name_font)
                metrics = QFontMetrics(name_font)

            checkbox_y = y + (row_height - checkbox_size) / 2
            painter.setPen(QPen(QColor("#111827")))
            painter.drawRect(QRectF(checkbox_x, checkbox_y, checkbox_size, checkbox_size))

            painter.setPen(text_color)
            display_name = metrics.elidedText(name, Qt.TextElideMode.ElideRight, int(name_width))
            painter.drawText(
                QRectF(name_x, y, name_width, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                display_name,
            )
            painter.setPen(line_pen)
            painter.drawLine(left, y + row_height - 1, right, y + row_height - 1)
            y += row_height

        draw_footer()

    def _ensure_gui_application(self) -> None:
        if QGuiApplication.instance() is None:
            self.__class__._qt_app = QGuiApplication([])

    def _first_line(self, value: object) -> str:
        for item in str(value or "").splitlines():
            clean_item = item.strip()
            if clean_item:
                return clean_item
        return ""

    def _category_value(self, value: object) -> str:
        for item in str(value or "").splitlines():
            clean_item = item.strip()
            if clean_item:
                return clean_item
        return "Sem categoria"

    def _safe_sheet_name(self, value: str, used_names: set[str]) -> str:
        base_name = re.sub(r"[\[\]:*?/\\]+", " ", str(value).strip())
        base_name = re.sub(r"\s{2,}", " ", base_name).strip("' ")
        if not base_name:
            base_name = "Planilha"
        base_name = base_name[:31]

        candidate = base_name
        counter = 2
        while candidate in used_names:
            suffix = f" {counter}"
            candidate = f"{base_name[:31 - len(suffix)]}{suffix}"
            counter += 1
        used_names.add(candidate)
        return candidate
