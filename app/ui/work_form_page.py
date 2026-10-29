from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget
)

from app.ui.date_field import DateField
from app.ui.icons import icon
from app.ui.widgets import NumericStepper, PageHeader, RatingSlider
from app.utils.dates import WEEKDAYS_PT


class WorkFormPage(QWidget):
    saved = Signal(str)
    cancelled = Signal()
    deleted = Signal()

    def __init__(self, repository, work=None, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.work = work
        self._cover_source = None
        self._remove_cover = False
        self._build()
        self._refresh_category_options()
        self._load()
        self._refresh_visibility()

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setObjectName("fieldLabel")
        return label

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll)
        page = QWidget()
        scroll.setWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 22, 28, 32)
        layout.setSpacing(16)

        header_row = QHBoxLayout()
        back = QPushButton("Voltar")
        back.setObjectName("ghost")
        back.setIcon(icon("arrow-left", color="#F4EFEA"))
        back.clicked.connect(self.cancelled)
        header_row.addWidget(back)
        header_row.addStretch()
        layout.addLayout(header_row)
        layout.addWidget(PageHeader(
            "Editar obra" if self.work else "Nova obra",
            "Organize leitura, publicação, progresso, agenda e acesso à obra em um único cadastro.",
            "Cadastro" if self.work else "Nova entrada",
        ))

        columns = QHBoxLayout()
        columns.setSpacing(16)
        layout.addLayout(columns)

        left = QFrame()
        left.setObjectName("panel")
        left.setFixedWidth(310)
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(18, 18, 18, 18)
        left_l.setSpacing(12)
        left_l.addWidget(self._field_label("Capa"))
        self.cover = QLabel("Adicionar capa")
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover.setFixedSize(274, 382)
        self.cover.setStyleSheet("background:#0F1012; border:1px solid #2B2E34; border-radius:4px; color:#756E64; font-weight:650;")
        left_l.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignHCenter)
        cover_btn = QPushButton("Selecionar capa")
        cover_btn.setIcon(icon("folder", color="#F4EFEA"))
        cover_btn.clicked.connect(self._select_cover)
        left_l.addWidget(cover_btn)
        remove_cover = QPushButton("Remover capa")
        remove_cover.setObjectName("ghost")
        remove_cover.clicked.connect(self._remove_cover_clicked)
        left_l.addWidget(remove_cover)
        self.favorite = QCheckBox("Marcar como favorito")
        left_l.addWidget(self.favorite)
        hint = QLabel("A capa é copiada para os dados locais e incluída nos backups completos.")
        hint.setObjectName("dim")
        hint.setWordWrap(True)
        left_l.addWidget(hint)
        left_l.addStretch()
        columns.addWidget(left)

        right = QVBoxLayout()
        right.setSpacing(14)
        columns.addLayout(right, 1)

        basic = QFrame()
        basic.setObjectName("panel")
        grid = QGridLayout(basic)
        grid.setContentsMargins(20, 18, 20, 20)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(7)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        grid.addWidget(self._field_label("Título da obra *"), 0, 0, 1, 2)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Ex.: Nano Machine")
        grid.addWidget(self.name, 1, 0, 1, 2)

        grid.addWidget(self._field_label("Categoria"), 2, 0)
        grid.addWidget(self._field_label("Meu status de leitura"), 2, 1)
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.currentTextChanged.connect(self._sync_category_unit)
        grid.addWidget(self.category, 3, 0)
        self.reading_status = QComboBox()
        self.reading_status.addItems(list(self.repository.STATUS_OPTIONS))
        grid.addWidget(self.reading_status, 3, 1)

        grid.addWidget(self._field_label("Status da obra / publicação"), 4, 0)
        grid.addWidget(self._field_label("Tipo de progresso"), 4, 1)
        self.publication_status = QComboBox()
        self.publication_status.addItems(list(self.repository.PUBLICATION_STATUS_OPTIONS))
        self.publication_status.currentTextChanged.connect(self._refresh_visibility)
        grid.addWidget(self.publication_status, 5, 0)
        self.progress_unit = QComboBox()
        self.progress_unit.addItems(list(self.repository.PROGRESS_UNITS))
        self.progress_unit.currentTextChanged.connect(self._refresh_visibility)
        grid.addWidget(self.progress_unit, 5, 1)

        grid.addWidget(self._field_label("Tags (separadas por vírgula)"), 6, 0, 1, 2)
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("manhwa, ação, ficção")
        grid.addWidget(self.tags, 7, 0, 1, 2)

        grid.addWidget(self._field_label("Link de leitura"), 8, 0, 1, 2)
        self.reading_url = QLineEdit()
        self.reading_url.setPlaceholderText("https://...")
        grid.addWidget(self.reading_url, 9, 0, 1, 2)
        right.addWidget(basic)

        progress = QFrame()
        progress.setObjectName("panel")
        pg = QGridLayout(progress)
        pg.setContentsMargins(20, 18, 20, 20)
        pg.setHorizontalSpacing(14)
        pg.setVerticalSpacing(7)
        title = QLabel("Progresso de leitura")
        title.setObjectName("sectionTitle")
        pg.addWidget(title, 0, 0, 1, 2)
        self.current_label = self._field_label("Última página lida")
        pg.addWidget(self.current_label, 1, 0)
        self.total_label = self._field_label("Total de páginas")
        pg.addWidget(self.total_label, 1, 1)
        self.current = NumericStepper(minimum=0, maximum=10_000_000, value=0)
        pg.addWidget(self.current, 2, 0)
        self.total = NumericStepper(minimum=0, maximum=10_000_000, value=0, special_value_text="Não definido")
        pg.addWidget(self.total, 2, 1)
        right.addWidget(progress)

        self.release_panel = QFrame()
        self.release_panel.setObjectName("panel")
        rg = QGridLayout(self.release_panel)
        rg.setContentsMargins(20, 18, 20, 20)
        rg.setHorizontalSpacing(14)
        rg.setVerticalSpacing(8)
        release_title = QLabel("Agenda de publicação")
        release_title.setObjectName("sectionTitle")
        rg.addWidget(release_title, 0, 0, 1, 2)
        intro = QLabel("Use uma agenda previsível quando a obra estiver em lançamento. O sistema destaca ontem, hoje, amanhã e capítulos ainda pendentes.")
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        rg.addWidget(intro, 1, 0, 1, 2)
        rg.addWidget(self._field_label("Frequência"), 2, 0, 1, 2)
        self.schedule_type = QComboBox()
        self.schedule_type.addItems(list(self.repository.RELEASE_SCHEDULE_OPTIONS))
        self.schedule_type.currentTextChanged.connect(self._refresh_schedule_fields)
        rg.addWidget(self.schedule_type, 3, 0, 1, 2)

        self.weekdays_box = QWidget()
        wd = QGridLayout(self.weekdays_box)
        wd.setContentsMargins(0, 0, 0, 0)
        wd.setSpacing(7)
        self.weekday_checks = []
        for index, day in enumerate(WEEKDAYS_PT):
            cb = QCheckBox(day.replace("-feira", ""))
            self.weekday_checks.append((day, cb))
            wd.addWidget(cb, index // 4, index % 4)
        rg.addWidget(self.weekdays_box, 4, 0, 1, 2)

        self.anchor_box = QWidget()
        al = QVBoxLayout(self.anchor_box)
        al.setContentsMargins(0, 0, 0, 0)
        al.addWidget(self._field_label("Data de um lançamento conhecido"))
        self.release_anchor = DateField()
        al.addWidget(self.release_anchor)
        rg.addWidget(self.anchor_box, 5, 0, 1, 2)

        self.month_box = QWidget()
        ml = QHBoxLayout(self.month_box)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.addWidget(self._field_label("Dia do mês"))
        self.month_day = NumericStepper(minimum=1, maximum=31, value=1)
        ml.addWidget(self.month_day)
        ml.addStretch()
        rg.addWidget(self.month_box, 6, 0, 1, 2)
        right.addWidget(self.release_panel)

        dates = QFrame()
        dates.setObjectName("panel")
        dg = QGridLayout(dates)
        dg.setContentsMargins(20, 18, 20, 20)
        dg.setHorizontalSpacing(14)
        dg.setVerticalSpacing(8)
        dg.addWidget(self._field_label("Data de início"), 0, 0)
        dg.addWidget(self._field_label("Data de conclusão"), 0, 1)
        self.start_date = DateField()
        self.end_date = DateField()
        dg.addWidget(self.start_date, 1, 0)
        dg.addWidget(self.end_date, 1, 1)
        dg.addWidget(self._field_label("Avaliação"), 2, 0, 1, 2)
        self.rating = RatingSlider()
        dg.addWidget(self.rating, 3, 0, 1, 2)
        right.addWidget(dates)

        text = QFrame()
        text.setObjectName("panel")
        tl = QVBoxLayout(text)
        tl.setContentsMargins(20, 18, 20, 20)
        tl.setSpacing(7)
        tl.addWidget(self._field_label("Sinopse"))
        self.synopsis = QTextEdit()
        self.synopsis.setMinimumHeight(110)
        tl.addWidget(self.synopsis)
        tl.addWidget(self._field_label("Notas pessoais"))
        self.notes = QTextEdit()
        self.notes.setMinimumHeight(110)
        tl.addWidget(self.notes)
        right.addWidget(text)

        actions = QHBoxLayout()
        if self.work:
            delete = QPushButton("Excluir obra")
            delete.setObjectName("dangerButton")
            delete.setIcon(icon("trash", color="#FF9A9A"))
            delete.clicked.connect(self._delete)
            actions.addWidget(delete)
        actions.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.cancelled)
        actions.addWidget(cancel)
        save = QPushButton("Salvar obra")
        save.setObjectName("primary")
        save.setIcon(icon("check", color="#17130A"))
        save.clicked.connect(self._save)
        actions.addWidget(save)
        layout.addLayout(actions)

    def _refresh_category_options(self):
        current = self.category.currentText().strip() if hasattr(self, "category") else ""
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItems([item["name"] for item in self.repository.list_categories()])
        self.category.setCurrentText(current)
        self.category.blockSignals(False)

    def _sync_category_unit(self, category_name):
        category_name = (category_name or "").strip()
        if not category_name:
            return
        data = self.repository.get_category(category_name)
        if not data:
            return
        self.progress_unit.blockSignals(True)
        self.progress_unit.setCurrentText(data.get("progress_unit") or "Página")
        self.progress_unit.blockSignals(False)
        self._refresh_visibility()

    def _load(self):
        if not self.work:
            self.reading_status.setCurrentText("Quero ler")
            self.progress_unit.setCurrentText("Página")
            self.publication_status.setCurrentText("Completo")
            self.schedule_type.setCurrentText("Sem calendário")
            self.rating.setValue(None)
            return
        work = self.work
        self.name.setText(work.name)
        self.category.setCurrentText(work.category or "")
        self.reading_status.setCurrentText(work.status)
        self.publication_status.setCurrentText(work.publication_status)
        self.progress_unit.setCurrentText(work.progress_unit)
        self.tags.setText(", ".join(self.repository.get_tags(work.id)))
        self.reading_url.setText(work.reading_url or "")
        self.current.setValue(int(work.progress_current or 0))
        self.total.setValue(int(work.progress_total or 0))
        self.schedule_type.setCurrentText(work.release_schedule_type or "Sem calendário")
        selected_days = {d.strip() for d in (work.release_days or "").split(",") if d.strip()}
        for day, cb in self.weekday_checks:
            cb.setChecked(day in selected_days)
        self.month_day.setValue(int(work.release_month_day or 1))
        self.release_anchor.set_iso(work.release_anchor_date)
        self.start_date.set_iso(work.start_date)
        self.end_date.set_iso(work.end_date)
        self.rating.setValue(work.rating)
        self.favorite.setChecked(bool(work.favorite))
        self.synopsis.setPlainText(work.synopsis or "")
        self.notes.setPlainText(work.personal_notes or "")
        if work.cover_path and Path(work.cover_path).is_file():
            self._show_cover(work.cover_path)

    def _refresh_visibility(self, *_):
        unit = self.progress_unit.currentText() if hasattr(self, "progress_unit") else "Página"
        pub = self.publication_status.currentText() if hasattr(self, "publication_status") else "Completo"
        chapters = unit == "Capítulo"
        self.current_label.setText("ÚLTIMO CAPÍTULO LIDO" if chapters else "ÚLTIMA PÁGINA LIDA")
        self.total_label.setText("TOTAL DE CAPÍTULOS" if chapters else "TOTAL DE PÁGINAS")
        # For ongoing serialized works, the total is unknown by design.
        show_total = (not chapters) or pub == "Completo"
        self.total_label.setVisible(show_total)
        self.total.setVisible(show_total)
        self.release_panel.setVisible(chapters and pub in ("Em lançamento", "Em hiato"))
        if chapters and pub != "Completo":
            self.total.setValue(0)
        self._refresh_schedule_fields()

    def _refresh_schedule_fields(self, *_):
        kind = self.schedule_type.currentText() if hasattr(self, "schedule_type") else "Sem calendário"
        self.weekdays_box.setVisible(kind == "Semanal")
        self.anchor_box.setVisible(kind == "Quinzenal")
        self.month_box.setVisible(kind == "Mensal")

    def _select_cover(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar capa", "", "Imagens (*.png *.jpg *.jpeg *.webp *.gif)")
        if path:
            self._cover_source = path
            self._remove_cover = False
            self._show_cover(path)

    def _show_cover(self, path):
        pix = QPixmap(str(path))
        if not pix.isNull():
            self.cover.setPixmap(pix.scaled(268, 376, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _remove_cover_clicked(self):
        self._cover_source = None
        self._remove_cover = True
        self.cover.clear()
        self.cover.setText("Adicionar capa")

    def _save(self):
        try:
            unit = self.progress_unit.currentText()
            pub = self.publication_status.currentText()
            total = self.total.value() or None
            if unit == "Capítulo" and pub != "Completo":
                total = None
            if unit == "Capítulo" and pub == "Completo" and not total:
                raise ValueError("Informe o total de capítulos para uma obra completa.")
            start_date = self.start_date.iso_value()
            end_date = self.end_date.iso_value()
            if start_date and end_date and end_date < start_date:
                raise ValueError("A data de conclusão não pode ser anterior à data de início.")
            days = [day for day, cb in self.weekday_checks if cb.isChecked()]
            data = dict(
                name=self.name.text().strip(),
                category=self.category.currentText().strip(),
                progress_unit=unit,
                progress_current=self.current.value(),
                progress_total=total,
                status=self.reading_status.currentText(),
                publication_status=pub,
                release_schedule_type=self.schedule_type.currentText() if pub in ("Em lançamento", "Em hiato") and unit == "Capítulo" else "Sem calendário",
                release_days=days,
                release_month_day=self.month_day.value(),
                release_anchor_date=self.release_anchor.iso_value(),
                reading_url=self.reading_url.text().strip(),
                synopsis=self.synopsis.toPlainText().strip(),
                rating=self.rating.value(),
                favorite=self.favorite.isChecked(),
                personal_notes=self.notes.toPlainText().strip(),
                start_date=start_date,
                end_date=end_date,
            )
            if self.work:
                self.repository.update_work(self.work.id, **data)
                work_id = self.work.id
            else:
                work_id = self.repository.create(**data).id
            self.repository.set_tags(work_id, [t.strip() for t in self.tags.text().split(",") if t.strip()])
            if self._remove_cover:
                self.repository.remove_cover(work_id)
            elif self._cover_source:
                self.repository.set_cover(work_id, self._cover_source)
        except Exception as exc:
            QMessageBox.critical(self, "Não foi possível salvar", str(exc))
            return
        self.saved.emit(work_id)

    def _delete(self):
        if not self.work:
            return
        answer = QMessageBox.question(
            self, "Excluir obra", f"Deseja excluir '{self.work.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.repository.delete_work(self.work.id)
            self.deleted.emit()
