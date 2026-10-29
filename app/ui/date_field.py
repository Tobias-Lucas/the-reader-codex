from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QCalendarWidget, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.ui.icons import icon
from app.utils.dates import br_to_iso, iso_to_br


class DateField(QWidget):
    """Brazilian DD/MM/YYYY input with an inline calendar, not a separate app window."""

    def __init__(self, value: str | None = None, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(5)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("DD/MM/AAAA")
        self.edit.setInputMask("00/00/0000;_")
        row.addWidget(self.edit, 1)
        self.button = QPushButton()
        self.button.setIcon(icon("calendar"))
        self.button.setFixedWidth(40)
        self.button.setToolTip("Selecionar no calendário")
        row.addWidget(self.button)
        self._layout.addLayout(row)

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(False)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.setMaximumHeight(250)
        self.calendar.hide()
        self._layout.addWidget(self.calendar)

        self.button.clicked.connect(self._toggle_calendar)
        self.calendar.clicked.connect(self._selected)
        self.set_iso(value)

    def _toggle_calendar(self):
        if self.calendar.isVisible():
            self.calendar.hide()
            return
        try:
            iso = self.iso_value()
        except ValueError:
            iso = None
        if iso:
            y, m, d = map(int, iso.split("-"))
            self.calendar.setSelectedDate(QDate(y, m, d))
        else:
            self.calendar.setSelectedDate(QDate.currentDate())
        self.calendar.show()

    def _selected(self, value: QDate):
        self.edit.setText(value.toString("dd/MM/yyyy"))
        self.calendar.hide()

    def iso_value(self) -> str | None:
        raw = self.edit.text().replace("_", "").strip()
        if raw in ("", "//"):
            return None
        return br_to_iso(raw)

    def set_iso(self, value: str | None):
        self.edit.clear()
        if value:
            self.edit.setText(iso_to_br(value))

    def clear(self):
        self.edit.clear()
        self.calendar.hide()
