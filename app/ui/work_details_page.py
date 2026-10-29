from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget
)

from app.ui.icons import icon
from app.ui.widgets import PageHeader, TagChip
from app.utils.dates import iso_to_br
from app.utils.releases import release_description


class WorkDetailsPage(QWidget):
    backRequested = Signal()
    editRequested = Signal(str)
    dataChanged = Signal()

    def __init__(self, repository, work_id: str, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.work_id = work_id
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll)
        self.page = QWidget()
        scroll.setWidget(self.page)
        self.layout = QVBoxLayout(self.page)
        self.layout.setContentsMargins(28, 22, 28, 32)
        self.layout.setSpacing(15)

    def _clear(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            child_layout = item.layout()
            if child_layout:
                while child_layout.count():
                    sub = child_layout.takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

    def refresh(self):
        self._clear()
        self.work = self.repository.get_by_id(self.work_id)
        if not self.work:
            self.backRequested.emit()
            return
        release_state = self.repository.get_release_state(self.work_id)

        nav = QHBoxLayout()
        back = QPushButton("Voltar")
        back.setObjectName("ghost")
        back.setIcon(icon("arrow-left", color="#F4EFEA"))
        back.clicked.connect(self.backRequested)
        nav.addWidget(back)
        nav.addStretch()
        self.layout.addLayout(nav)

        hero = QFrame()
        hero.setObjectName("panel")
        h = QGridLayout(hero)
        h.setContentsMargins(22, 22, 22, 22)
        h.setHorizontalSpacing(20)
        h.setVerticalSpacing(9)
        h.setColumnStretch(1, 1)

        cover = QLabel("CAPA")
        cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover.setFixedSize(230, 322)
        cover.setStyleSheet("background:#0F1012; border:1px solid #2B2E34; border-radius:4px; color:#756E64; font-weight:650;")
        if self.work.cover_path and Path(self.work.cover_path).is_file():
            pix = QPixmap(self.work.cover_path)
            if not pix.isNull():
                cover.setPixmap(pix.scaled(224, 316, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        h.addWidget(cover, 0, 0, 8, 1, Qt.AlignmentFlag.AlignTop)

        title_row = QHBoxLayout()
        title = QLabel(self.work.name)
        title.setObjectName("pageTitle")
        title.setWordWrap(True)
        title_row.addWidget(title)
        pub = QLabel(self.work.publication_status)
        pub.setObjectName("publicationStatus")
        title_row.addWidget(pub, 0, Qt.AlignmentFlag.AlignVCenter)
        title_row.addStretch()
        fav = QPushButton()
        fav.setObjectName("favorite")
        fav.setIcon(icon("star-filled" if self.work.favorite else "star"))
        fav.setToolTip("Remover dos favoritos" if self.work.favorite else "Adicionar aos favoritos")
        fav.clicked.connect(self._toggle_favorite)
        title_row.addWidget(fav)
        h.addLayout(title_row, 0, 1)

        chips = QHBoxLayout()
        chips.addWidget(TagChip(self.work.status, accent=self.work.status == "Lendo"))
        if self.work.category:
            chip = TagChip(self.work.category.upper())
            chip.setStyleSheet("padding:4px 9px; border-radius:10px; font-size:10px; font-weight:650; background:#2A2045; color:#C8B8FF;")
            chips.addWidget(chip)
        for tag in self.repository.get_tags(self.work_id)[:5]:
            chips.addWidget(TagChip(tag))
        chips.addStretch()
        h.addLayout(chips, 1, 1)

        rating = QLabel(self._rating_text())
        rating.setObjectName("rating" if self.work.rating is not None else "dim")
        h.addWidget(rating, 2, 1)

        progress_box = QFrame()
        progress_box.setObjectName("subPanel")
        pg = QHBoxLayout(progress_box)
        pg.setContentsMargins(17, 15, 17, 15)
        left = QVBoxLayout()
        caption = QLabel("ÚLTIMO CAPÍTULO LIDO" if self.work.progress_unit == "Capítulo" else "ÚLTIMA PÁGINA LIDA")
        caption.setObjectName("progressCaption")
        left.addWidget(caption)
        valrow = QHBoxLayout()
        val = QLabel(str(self.work.progress_current))
        val.setObjectName("progressValue")
        valrow.addWidget(val)
        if self.work.progress_total:
            suffix = QLabel(f"de {self.work.progress_total}")
            suffix.setObjectName("progressUnit")
            valrow.addWidget(suffix, 0, Qt.AlignmentFlag.AlignBottom)
        valrow.addStretch()
        left.addLayout(valrow)
        pg.addLayout(left, 1)
        right = QVBoxLayout()
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pending = int(release_state.get("pending_count") or 0)
        if pending:
            label = QLabel("1 capítulo pendente" if pending == 1 else f"{pending} capítulos pendentes")
            label.setObjectName("pending")
            label.setAlignment(Qt.AlignmentFlag.AlignRight)
            right.addWidget(label)
            if release_state.get("oldest_pending"):
                sub = QLabel(f"Pendente desde {iso_to_br(release_state['oldest_pending'])}")
                sub.setObjectName("dim")
                sub.setAlignment(Qt.AlignmentFlag.AlignRight)
                right.addWidget(sub)
        elif self.work.publication_status == "Em lançamento" and release_state.get("next_release"):
            sub = QLabel(f"Próximo lançamento: {iso_to_br(release_state['next_release'])}")
            sub.setObjectName("muted")
            sub.setAlignment(Qt.AlignmentFlag.AlignRight)
            right.addWidget(sub)
        pg.addLayout(right)
        h.addWidget(progress_box, 3, 1)

        actions = QHBoxLayout()
        for amount in (-1, 1, 5, 10):
            btn = QPushButton(str(amount) if amount < 0 else f"+{amount}")
            btn.setFixedWidth(52)
            btn.clicked.connect(lambda _=False, a=amount: self._progress(a))
            actions.addWidget(btn)
        read = QPushButton("Ler")
        read.setIcon(icon("external", color="#17130A"))
        read.setObjectName("primary")
        read.setEnabled(bool(self.work.reading_url))
        read.clicked.connect(self._open_reading_url)
        actions.addWidget(read)
        edit = QPushButton("Editar cadastro")
        edit.setIcon(icon("edit", color="#F4EFEA"))
        edit.clicked.connect(lambda: self.editRequested.emit(self.work_id))
        actions.addWidget(edit)
        if self.work.publication_status == "Em lançamento":
            hiatus = QPushButton("Colocar em hiato")
            hiatus.setIcon(icon("pause", color="#F4EFEA"))
            hiatus.clicked.connect(lambda: self._publication_status("Em hiato"))
            actions.addWidget(hiatus)
        elif self.work.publication_status == "Em hiato":
            resume = QPushButton("Retomar lançamento")
            resume.setIcon(icon("sync", color="#F4EFEA"))
            resume.clicked.connect(lambda: self._publication_status("Em lançamento"))
            actions.addWidget(resume)
        actions.addStretch()
        h.addLayout(actions, 4, 1)

        meta = []
        if self.work.start_date:
            meta.append(f"Início: {iso_to_br(self.work.start_date)}")
        if self.work.end_date:
            meta.append(f"Conclusão: {iso_to_br(self.work.end_date)}")
        if self.work.publication_status in ("Em lançamento", "Em hiato"):
            meta.append(release_description(self.work.release_schedule_type, self.work.release_days, self.work.release_month_day))
        meta_label = QLabel("  •  ".join(meta))
        meta_label.setObjectName("dim")
        meta_label.setWordWrap(True)
        h.addWidget(meta_label, 5, 1)
        self.layout.addWidget(hero)

        if self.work.progress_total:
            bar_panel = QFrame()
            bar_panel.setObjectName("panel")
            bl = QVBoxLayout(bar_panel)
            bl.setContentsMargins(20, 16, 20, 16)
            ratio = min(self.work.progress_current / self.work.progress_total, 1)
            top = QHBoxLayout()
            t = QLabel("Progresso total")
            t.setObjectName("sectionTitle")
            top.addWidget(t)
            top.addStretch()
            pct = QLabel(f"{ratio*100:.1f}%".replace(".", ","))
            pct.setObjectName("pending")
            top.addWidget(pct)
            bl.addLayout(top)
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(int(ratio * 1000))
            bl.addWidget(bar)
            self.layout.addWidget(bar_panel)

        edit_panel = QFrame()
        edit_panel.setObjectName("panel")
        ep = QGridLayout(edit_panel)
        ep.setContentsMargins(20, 18, 20, 20)
        ep.setHorizontalSpacing(16)
        ep.setVerticalSpacing(8)
        ep.setColumnStretch(1, 1)
        title = QLabel("Atualização rápida")
        title.setObjectName("sectionTitle")
        ep.addWidget(title, 0, 0, 1, 2)
        label = QLabel("STATUS DE LEITURA")
        label.setObjectName("fieldLabel")
        ep.addWidget(label, 1, 0)
        self.status_combo = QComboBox()
        self.status_combo.addItems(list(self.repository.STATUS_OPTIONS))
        self.status_combo.setCurrentText(self.work.status)
        ep.addWidget(self.status_combo, 2, 0)
        status_save = QPushButton("Salvar status")
        status_save.clicked.connect(self._save_status)
        ep.addWidget(status_save, 3, 0, Qt.AlignmentFlag.AlignLeft)

        notes_label = QLabel("NOTAS PESSOAIS")
        notes_label.setObjectName("fieldLabel")
        ep.addWidget(notes_label, 1, 1)
        self.notes = QTextEdit()
        self.notes.setPlainText(self.work.personal_notes or "")
        self.notes.setMinimumHeight(110)
        ep.addWidget(self.notes, 2, 1)
        notes_save = QPushButton("Salvar notas")
        notes_save.clicked.connect(self._save_notes)
        ep.addWidget(notes_save, 3, 1, Qt.AlignmentFlag.AlignRight)
        self.layout.addWidget(edit_panel)

        synopsis = QFrame()
        synopsis.setObjectName("panel")
        sl = QVBoxLayout(synopsis)
        sl.setContentsMargins(20, 18, 20, 20)
        st = QLabel("Sinopse")
        st.setObjectName("sectionTitle")
        sl.addWidget(st)
        text = QLabel(self.work.synopsis or "Nenhuma sinopse cadastrada.")
        text.setWordWrap(True)
        text.setObjectName("muted" if not self.work.synopsis else "")
        sl.addWidget(text)
        self.layout.addWidget(synopsis)
        self.layout.addStretch()

    def _rating_text(self):
        if self.work.rating is None:
            return "☆ Sem avaliação"
        value = float(self.work.rating)
        full = int(value)
        half = abs(value - full - .5) < 1e-9
        stars = "★" * full + ("½" if half else "") + "☆" * max(0, 5 - full - (1 if half else 0))
        return f"{stars}   {value:.1f} / 5".replace(".", ",")

    def _progress(self, amount):
        try:
            self.repository.increment_progress(self.work_id, amount)
        except Exception as exc:
            QMessageBox.critical(self, "Progresso", str(exc))
            return
        self.dataChanged.emit()
        self.refresh()

    def _toggle_favorite(self):
        try:
            self.repository.set_favorite(self.work_id, not self.work.favorite)
        except Exception as exc:
            QMessageBox.critical(self, "Favorito", str(exc))
            return
        self.dataChanged.emit()
        self.refresh()

    def _save_status(self):
        try:
            self.repository.set_reading_status(self.work_id, self.status_combo.currentText())
        except Exception as exc:
            QMessageBox.critical(self, "Status", str(exc))
            return
        self.dataChanged.emit()
        self.refresh()

    def _save_notes(self):
        try:
            self.repository.set_notes(self.work_id, self.notes.toPlainText().strip())
        except Exception as exc:
            QMessageBox.critical(self, "Notas", str(exc))
            return
        self.dataChanged.emit()
        QMessageBox.information(self, "Notas", "Notas pessoais salvas.")

    def _publication_status(self, value):
        try:
            self.repository.set_publication_status(self.work_id, value)
        except Exception as exc:
            QMessageBox.critical(self, "Status da obra", str(exc))
            return
        self.dataChanged.emit()
        self.refresh()

    def _open_reading_url(self):
        if self.work.reading_url:
            QDesktopServices.openUrl(QUrl(self.work.reading_url))
