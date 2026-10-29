from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider, QSizePolicy,
    QProgressBar, QToolButton, QVBoxLayout, QWidget
)

from app.ui.icons import icon
from app.utils.dates import iso_to_br


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", eyebrow: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 18)
        layout.setSpacing(4)
        if eyebrow:
            eyebrow_label = QLabel(eyebrow.upper())
            eyebrow_label.setObjectName("pageEyebrow")
            layout.addWidget(eyebrow_label)
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("pageSubtitle")
            sub.setWordWrap(True)
            layout.addWidget(sub)


class MetricCard(QFrame):
    def __init__(self, label: str, value: str, icon_name: str, parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setMinimumHeight(116)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        top = QHBoxLayout()
        caption = QLabel(label.upper())
        caption.setObjectName("heroStatLabel")
        top.addWidget(caption)
        top.addStretch()
        icon_label = QLabel()
        icon_label.setPixmap(icon(icon_name, color="#E5A93C").pixmap(16, 16))
        top.addWidget(icon_label)
        layout.addLayout(top)

        number = QLabel(str(value))
        number.setObjectName("heroStatValue")
        layout.addWidget(number)

        foot = QLabel(self._footnote(label, value))
        foot.setObjectName("muted")
        foot.setWordWrap(True)
        layout.addWidget(foot)
        layout.addStretch()

    @staticmethod
    def _footnote(label: str, value) -> str:
        text = str(label).lower()
        if "acervo" in text:
            return "Catálogo ativo"
        if "lendo" in text:
            return "Em progresso"
        if "conclu" in text:
            return "Volumes finais"
        if "favorit" in text:
            return "Marca especial"
        return str(value)


class TagChip(QLabel):
    def __init__(self, text: str, accent=False, category=False, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bg = "#2F271A" if accent else "#24272C"
        fg = "#E5A93C" if accent else ("#CBB8A1" if category else "#9E9B95")
        self.setStyleSheet(
            f"padding: 4px 9px; border-radius: 999px; font-size: 10px; font-weight: 650; "
            f"background: {bg}; color: {fg};"
        )


class WorkCard(QFrame):
    favoriteChanged = Signal(str, bool)
    progressChanged = Signal(str, int)
    detailsRequested = Signal(str)
    readRequested = Signal(str)

    def __init__(self, work, tags=None, release_state=None, parent=None):
        super().__init__(parent)
        self.work = work
        self.tags = tags or []
        self.release_state = release_state or {}
        self.setObjectName("workCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(250)
        self._build()

    def _build(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(18)

        cover_holder = QFrame()
        cover_holder.setObjectName("subPanel")
        cover_holder.setFixedWidth(168)
        cover_l = QVBoxLayout(cover_holder)
        cover_l.setContentsMargins(8, 8, 8, 8)
        cover_l.setSpacing(0)
        cover = QLabel("CAPA")
        cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover.setFixedSize(150, 222)
        cover.setStyleSheet(
            "background:#0F1012; border:1px solid #2B2E34; border-radius:3px; color:#756E64; font-weight:650;"
        )
        if self.work.cover_path:
            path = Path(self.work.cover_path)
            if path.is_file():
                pix = QPixmap(str(path))
                if not pix.isNull():
                    pix = pix.scaled(146, 218, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    cover.setPixmap(pix)
        cover_l.addWidget(cover, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        outer.addWidget(cover_holder, 0, Qt.AlignmentFlag.AlignTop)

        content = QVBoxLayout()
        content.setSpacing(10)
        outer.addLayout(content, 1)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel(self.work.name)
        title.setObjectName("workTitle")
        title.setWordWrap(True)
        title_box.addWidget(title)
        pub_text = self.work.publication_status or ""
        pub = QLabel(f"• {pub_text}" if pub_text else "")
        pub.setObjectName("publicationStatus")
        title_box.addWidget(pub)
        title_row.addLayout(title_box, 1)
        fav = QPushButton()
        fav.setObjectName("favorite")
        fav.setIcon(icon("star-filled" if self.work.favorite else "star", color="#E5A93C" if self.work.favorite else "#9E9B95"))
        fav.setIconSize(QSize(18, 18))
        fav.setToolTip("Remover dos favoritos" if self.work.favorite else "Adicionar aos favoritos")
        fav.clicked.connect(lambda: self.favoriteChanged.emit(self.work.id, not self.work.favorite))
        title_row.addWidget(fav, 0, Qt.AlignmentFlag.AlignTop)
        content.addLayout(title_row)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(TagChip(self.work.status.upper(), accent=self.work.status == "Lendo"))
        if self.work.category:
            chips.addWidget(TagChip(self.work.category.upper(), category=True))
        for tag in self.tags[:3]:
            chips.addWidget(TagChip(tag.upper()))
        chips.addStretch()
        content.addLayout(chips)

        rating = QLabel(self._rating_text())
        rating.setObjectName("rating" if self.work.rating is not None else "dim")
        content.addWidget(rating)

        progress_box = QFrame()
        progress_box.setObjectName("subPanel")
        pg = QVBoxLayout(progress_box)
        pg.setContentsMargins(14, 12, 14, 12)
        pg.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        left = QHBoxLayout()
        left.setSpacing(6)
        cap = QLabel("ÚLTIMO CAPÍTULO LIDO:" if self.work.progress_unit == "Capítulo" else "ÚLTIMA PÁGINA LIDA:")
        cap.setObjectName("progressCaption")
        left.addWidget(cap)
        value = QLabel(
            f"Capítulo {self.work.progress_current}" if self.work.progress_unit == "Capítulo" else f"Página {self.work.progress_current}"
        )
        value.setObjectName("progressValue")
        left.addWidget(value)
        if self.work.progress_total is not None:
            suffix_text = (
                f"de {self.work.progress_total} disponíveis"
                if self.work.progress_unit == "Capítulo"
                else f"de {self.work.progress_total}"
            )
            suffix = QLabel(suffix_text)
            suffix.setObjectName("progressUnit")
            left.addWidget(suffix)
        left.addStretch()
        top_row.addLayout(left, 1)

        pending_count = int(self.release_state.get("pending_count") or 0)
        if pending_count:
            text = "1 capítulo pendente" if pending_count == 1 else f"{pending_count} capítulos pendentes"
            pending = QLabel(text)
            pending.setObjectName("pending")
            pending.setAlignment(Qt.AlignmentFlag.AlignRight)
            top_row.addWidget(pending)
        elif self.work.publication_status == "Em lançamento" and self.release_state.get("next_release"):
            nxt = QLabel(f"Próximo: {iso_to_br(self.release_state['next_release'])}")
            nxt.setObjectName("muted")
            top_row.addWidget(nxt)
        pg.addLayout(top_row)

        if self.work.progress_total:
            bar = QProgressBar()
            pct = min(int((self.work.progress_current / self.work.progress_total) * 100), 100)
            bar.setRange(0, 100)
            bar.setValue(pct)
            pg.addWidget(bar)

        meta_row = QHBoxLayout()
        meta_left = QLabel(self._meta_left())
        meta_left.setObjectName("dim")
        meta_row.addWidget(meta_left)
        meta_row.addStretch()
        meta_right = QLabel(self._meta_right())
        meta_right.setObjectName("dim")
        meta_row.addWidget(meta_right)
        pg.addLayout(meta_row)
        content.addWidget(progress_box)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        minus = QPushButton("−1")
        minus.setFixedWidth(50)
        minus.clicked.connect(lambda: self.progressChanged.emit(self.work.id, -1))
        actions.addWidget(minus)
        plus = QPushButton("+1")
        plus.setFixedWidth(50)
        plus.clicked.connect(lambda: self.progressChanged.emit(self.work.id, 1))
        actions.addWidget(plus)
        actions.addStretch()
        read = QPushButton("Ler agora")
        read.setIcon(icon("external", color="#F4EFEA"))
        read.setEnabled(bool(self.work.reading_url))
        read.setToolTip("Abrir link de leitura" if self.work.reading_url else "Adicione um link de leitura no cadastro")
        read.clicked.connect(lambda: self.readRequested.emit(self.work.id))
        actions.addWidget(read)
        details = QPushButton("Ver detalhes")
        details.setObjectName("primary")
        details.setIcon(icon("chevron-right", color="#17130A"))
        details.clicked.connect(lambda: self.detailsRequested.emit(self.work.id))
        actions.addWidget(details)
        content.addLayout(actions)

    def _meta_left(self):
        meta = []
        if self.work.start_date:
            meta.append(f"Início: {iso_to_br(self.work.start_date)}")
        if self.work.release_schedule_type and self.work.publication_status == "Em lançamento":
            summary = self._schedule_summary()
            if summary:
                meta.append(summary)
        return "  •  ".join(filter(None, meta))

    def _meta_right(self):
        since = self.release_state.get("oldest_pending")
        if since and int(self.release_state.get("pending_count") or 0):
            return f"Pendência desde {iso_to_br(since)}"
        return ""

    def _rating_text(self):
        if self.work.rating is None:
            return "☆ Sem avaliação"
        value = float(self.work.rating)
        full = int(value)
        half = abs(value - full - 0.5) < 1e-9
        stars = "★" * full + ("½" if half else "") + "☆" * max(0, 5 - full - (1 if half else 0))
        return f"{stars}   {value:.1f}".replace(".", ",")

    def _schedule_summary(self):
        kind = self.work.release_schedule_type
        if kind == "Semanal" and self.work.release_days:
            return self.work.release_days.replace(",", ", ")
        if kind == "Quinzenal":
            return "Quinzenal"
        if kind == "Mensal" and self.work.release_month_day:
            return f"Mensal, dia {self.work.release_month_day}"
        if kind == "Irregular":
            return "Lançamento irregular"
        return ""


class ReleaseMiniCard(QFrame):
    opened = Signal(str)

    def __init__(self, work_id: str, title: str, label: str, accent: str = "muted", parent=None):
        super().__init__(parent)
        self.setObjectName("releaseCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(13, 11, 13, 11)
        layout.setSpacing(10)
        dot = QLabel("•")
        dot.setObjectName("pending" if accent == "pending" else accent)
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
        left = QVBoxLayout()
        left.setSpacing(2)
        name = QLabel(title)
        name.setStyleSheet("font-weight:700;")
        left.addWidget(name)
        sub = QLabel(label)
        sub.setObjectName(accent)
        left.addWidget(sub)
        layout.addLayout(left, 1)
        button = QPushButton()
        button.setObjectName("ghost")
        button.setIcon(icon("chevron-right", color="#E5A93C"))
        button.setFixedWidth(38)
        button.clicked.connect(lambda: self.opened.emit(work_id))
        layout.addWidget(button)


class NumericStepper(QWidget):
    valueChanged = Signal(int)

    def __init__(self, minimum=0, maximum=10_000_000, value=0, special_value_text="", parent=None):
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = max(minimum, maximum)
        self._value = minimum
        self._special_value_text = special_value_text

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.decrease_button = QToolButton()
        self.decrease_button.setObjectName("stepperButton")
        self.decrease_button.setText("◀")
        self.decrease_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.decrease_button.setFixedWidth(40)
        self.decrease_button.clicked.connect(lambda: self.setValue(self._value - 1))
        layout.addWidget(self.decrease_button)

        self.line_edit = QLineEdit()
        self.line_edit.setObjectName("stepperField")
        self.line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.line_edit.editingFinished.connect(self._commit_text)
        layout.addWidget(self.line_edit, 1)

        self.increase_button = QToolButton()
        self.increase_button.setObjectName("stepperButton")
        self.increase_button.setText("▶")
        self.increase_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.increase_button.setFixedWidth(40)
        self.increase_button.clicked.connect(lambda: self.setValue(self._value + 1))
        layout.addWidget(self.increase_button)

        self.setValue(value)

    def setRange(self, minimum, maximum):
        self._minimum = int(minimum)
        self._maximum = max(int(maximum), self._minimum)
        self.setValue(self._value)

    def setSpecialValueText(self, text):
        self._special_value_text = str(text or "")
        self._sync_text()

    def value(self):
        return int(self._value)

    def setValue(self, value):
        value = max(self._minimum, min(self._maximum, int(value)))
        if value == self._value and self.line_edit.text() and self.line_edit.text() != str(value):
            self._sync_text()
            return
        changed = value != self._value
        self._value = value
        self._sync_text()
        if changed:
            self.valueChanged.emit(self._value)

    def _sync_text(self):
        if self._special_value_text and self._value == self._minimum:
            self.line_edit.blockSignals(True)
            self.line_edit.setText("")
            self.line_edit.blockSignals(False)
            self.line_edit.setPlaceholderText(self._special_value_text)
        else:
            self.line_edit.setPlaceholderText("")
            self.line_edit.blockSignals(True)
            self.line_edit.setText(str(self._value))
            self.line_edit.blockSignals(False)

    def _commit_text(self):
        raw = self.line_edit.text().strip()
        if not raw:
            self.setValue(self._minimum)
            return
        try:
            self.setValue(int(raw))
        except ValueError:
            self._sync_text()

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self.decrease_button.setEnabled(enabled)
        self.line_edit.setEnabled(enabled)
        self.increase_button.setEnabled(enabled)


class RatingSlider(QWidget):
    valueChanged = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 10)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(1)
        self.slider.valueChanged.connect(self._emit_value)
        layout.addWidget(self.slider)
        self.label = QLabel()
        self.label.setObjectName("dim")
        layout.addWidget(self.label)
        self.setValue(None)

    def value(self):
        points = self.slider.value()
        return None if points == 0 else points / 2

    def setValue(self, value):
        points = 0 if value in (None, "", 0) else int(round(float(value) * 2))
        self.slider.blockSignals(True)
        self.slider.setValue(points)
        self.slider.blockSignals(False)
        self._refresh_label()

    def _emit_value(self, _):
        self._refresh_label()
        self.valueChanged.emit(0.0 if self.value() is None else float(self.value()))

    def _refresh_label(self):
        value = self.value()
        if value is None:
            self.label.setText("Sem avaliação")
            return
        full = int(value)
        half = abs(value - full - 0.5) < 1e-9
        stars = "★" * full + ("½" if half else "") + "☆" * max(0, 5 - full - (1 if half else 0))
        self.label.setText(f"{stars}   {value:.1f} / 5".replace(".", ","))
