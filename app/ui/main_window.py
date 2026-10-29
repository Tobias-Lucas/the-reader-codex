from __future__ import annotations

import os
import threading
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer, QUrl, QSize
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QHeaderView, QAbstractItemView
)

from app.paths import APP_ICON_PATH, DATA_DIR
from app.repositories.sqlite_repository import SQLiteWorkRepository
from app.services.backup_service import BackupService
from app.services.settings_service import SettingsService
from app.services.statistics_service import StatisticsService
from app.services.sync_engine import SyncEngine
from app.ui.date_field import DateField
from app.ui.icons import icon
from app.ui.theme import AMBER, TEXT, TEXT_MUTED, app_stylesheet
from app.ui.widgets import MetricCard, NumericStepper, PageHeader, ReleaseMiniCard, WorkCard
from app.ui.work_details_page import WorkDetailsPage
from app.ui.work_form_page import WorkFormPage
from app.utils.dates import iso_to_br
from app.version import __version__


class MainWindow(QMainWindow):
    syncFinished = Signal(dict, bool)
    connectionFinished = Signal(dict)

    GOAL_LABELS = {"books": "Obras concluídas", "pages": "Páginas lidas", "chapters": "Capítulos lidos"}
    GOAL_TYPES_BY_LABEL = {v: k for k, v in GOAL_LABELS.items()}

    NAV = [
        ("home", "Início", "home"),
        ("library", "Biblioteca", "library"),
        ("reading", "Lendo agora", "book-open"),
        ("goals", "Metas e desafios", "target"),
        ("statistics", "Estatísticas", "chart"),
        ("favorites", "Favoritos", "star"),
        ("categories", "Categorias", "tags"),
        ("calendar", "Calendário", "calendar"),
        ("history", "Histórico", "history"),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"The Reader Codex {__version__}")
        if APP_ICON_PATH.is_file():
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        self.setStyleSheet(app_stylesheet())
        self.setMinimumSize(980, 640)

        self.repo = SQLiteWorkRepository()
        self.settings_service = SettingsService()
        self.backup_service = BackupService(self.repo)
        self.statistics_service = StatisticsService(self.repo)
        self.sync_engine = SyncEngine(self.repo, self.settings_service)

        self.current_view = "home"
        self.previous_view = "library"
        self.current_work_id = None
        self._first_show = True
        self._sync_running = False
        self.nav_buttons = {}
        self.library_filters = {"search": "", "category": "Todas", "status": "Todos", "publication": "Todos", "tag": "Todas"}
        self.view_scroll_positions = {}

        self._build_shell()
        self.syncFinished.connect(self._apply_sync_result)
        self.connectionFinished.connect(self._apply_connection_result)

        self._apply_inactivity_rule()
        self.show_home()
        self._update_sync_status()

        self.periodic_sync = QTimer(self)
        self.periodic_sync.setInterval(5 * 60 * 1000)
        self.periodic_sync.timeout.connect(lambda: self.sync_in_background(False))
        self.periodic_sync.start()

        self.inactivity_timer = QTimer(self)
        self.inactivity_timer.setInterval(30 * 60 * 1000)
        self.inactivity_timer.timeout.connect(self._apply_inactivity_rule)
        self.inactivity_timer.start()

        QTimer.singleShot(2500, self._startup_backup)
        if self.settings_service.load().get("sync_enabled"):
            QTimer.singleShot(1500, lambda: self.sync_in_background(False))

    def showEvent(self, event):
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            QTimer.singleShot(0, self._center_on_available_screen)

    def _center_on_available_screen(self):
        screen = self.screen() or QGuiApplication.primaryScreen()
        if not screen:
            return
        available = screen.availableGeometry()
        width = min(1440, max(980, available.width() - 80))
        height = min(900, max(640, available.height() - 70))
        width = min(width, available.width() - 20)
        height = min(height, available.height() - 20)
        self.resize(width, height)
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def _nav_icon_color(self, active=False):
        return AMBER if active else TEXT_MUTED

    def _refresh_nav_icons(self):
        for key, btn in self.nav_buttons.items():
            icon_name = btn.property("icon_name")
            if not icon_name:
                continue
            active = btn.property("active") is True
            btn.setIcon(icon(icon_name, color=self._nav_icon_color(active)))
            btn.setIconSize(QSize(18, 18))

    def _build_shell(self):
        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        grid = QGridLayout(root)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(1, 1)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(270)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(16, 18, 16, 16)
        sl.setSpacing(8)

        brand_card = QFrame()
        brand_card.setObjectName("sidebarTile")
        brand_l = QHBoxLayout(brand_card)
        brand_l.setContentsMargins(14, 14, 14, 14)
        brand_l.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(icon("library", color="#E5A93C").pixmap(28, 28))
        brand_l.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        name = QLabel("The Reader Codex")
        name.setObjectName("brand")
        brand_text.addWidget(name)
        sub = QLabel("PAINEL LITERÁRIO PESSOAL")
        sub.setObjectName("brandSub")
        brand_text.addWidget(sub)
        brand_l.addLayout(brand_text, 1)
        sl.addWidget(brand_card)

        section = QLabel("NAVEGAÇÃO")
        section.setObjectName("fieldLabel")
        sl.addWidget(section)
        for key, text_value, icon_name in self.NAV:
            btn = QPushButton(text_value)
            btn.setObjectName("nav")
            btn.setProperty("active", False)
            btn.setProperty("icon_name", icon_name)
            btn.clicked.connect(lambda _=False, k=key: self.navigate(k))
            self.nav_buttons[key] = btn
            sl.addWidget(btn)

        sl.addStretch()

        tools = QLabel("SISTEMA")
        tools.setObjectName("fieldLabel")
        sl.addWidget(tools)

        settings = QPushButton("Configurações")
        settings.setObjectName("nav")
        settings.setProperty("icon_name", "settings")
        settings.clicked.connect(self.show_settings)
        self.nav_buttons["settings"] = settings
        sl.addWidget(settings)

        backup = QPushButton("Backup")
        backup.setObjectName("nav")
        backup.setProperty("icon_name", "backup")
        backup.clicked.connect(self.show_backup)
        self.nav_buttons["backup"] = backup
        sl.addWidget(backup)

        sync_card = QFrame()
        sync_card.setObjectName("sidebarTile")
        sync_l = QVBoxLayout(sync_card)
        sync_l.setContentsMargins(14, 14, 14, 14)
        sync_l.setSpacing(10)
        sync_title = QLabel("Sincronização")
        sync_title.setObjectName("sectionTitle")
        sync_l.addWidget(sync_title)
        self.sync_label = QLabel()
        self.sync_label.setObjectName("dim")
        self.sync_label.setWordWrap(True)
        sync_l.addWidget(self.sync_label)
        self.sync_button = QPushButton("Sincronizar agora")
        self.sync_button.setIcon(icon("sync", color="#17130A"))
        self.sync_button.setObjectName("primary")
        self.sync_button.clicked.connect(lambda: self.sync_in_background(True))
        sync_l.addWidget(self.sync_button)
        sl.addWidget(sync_card)

        grid.addWidget(sidebar, 0, 0, 2, 1)

        top = QFrame()
        top.setObjectName("topbar")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(26, 14, 26, 12)
        tl.setSpacing(10)
        self.global_search = QLineEdit()
        self.global_search.setPlaceholderText("Buscar por título, categoria, tag ou status...")
        self.global_search.returnPressed.connect(self._global_search)
        tl.addWidget(self.global_search, 1)

        self.quick_status = QLabel("Coleção pessoal")
        self.quick_status.setObjectName("dim")
        tl.addWidget(self.quick_status)

        new = QPushButton("Nova obra")
        new.setObjectName("primary")
        new.setIcon(icon("plus", color="#17130A"))
        new.clicked.connect(self.open_new_work)
        tl.addWidget(new)
        grid.addWidget(top, 0, 1)

        self.stack = QStackedWidget()
        grid.addWidget(self.stack, 1, 1)

        self._refresh_nav_icons()

    def navigate(self, key):
        actions = {
            "home": self.show_home, "library": self.show_library, "reading": self.show_reading_now,
            "goals": self.show_goals, "statistics": self.show_statistics, "history": self.show_history,
            "favorites": self.show_favorites, "categories": self.show_categories,
            "calendar": self.show_calendar, "settings": self.show_settings, "backup": self.show_backup,
        }
        actions.get(key, self.show_library)()

    def _save_current_scroll_position(self):
        current = self.stack.currentWidget()
        if isinstance(current, QScrollArea):
            self.view_scroll_positions[self.current_view] = current.verticalScrollBar().value()

    def _restore_scroll_position(self, widget, view):
        if not isinstance(widget, QScrollArea):
            return
        value = self.view_scroll_positions.get(view)
        if value is None:
            return
        QTimer.singleShot(0, lambda: widget.verticalScrollBar().setValue(value))

    def _set_page(self, widget, view):
        self._save_current_scroll_position()
        old = self.stack.currentWidget()
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)
        if old:
            self.stack.removeWidget(old)
            old.deleteLater()
        self.current_view = view
        self._sync_nav()
        self._restore_scroll_position(widget, view)

    def _sync_nav(self):
        base = self.current_view
        if base in ("work_form", "work_details"):
            base = "library"
        for key, btn in self.nav_buttons.items():
            btn.setProperty("active", key == base)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._refresh_nav_icons()

    def _make_scroll(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 22, 28, 32)
        layout.setSpacing(14)
        scroll.setWidget(content)
        return scroll, layout

    def _bind_work_card(self, card):
        card.favoriteChanged.connect(self._toggle_favorite)
        card.progressChanged.connect(self._change_progress)
        card.detailsRequested.connect(self.open_details)
        card.readRequested.connect(self._open_reading_link)

    def _add_work_cards(self, layout, works):
        if not works:
            empty = QLabel("Nenhuma obra encontrada.")
            empty.setObjectName("muted")
            layout.addWidget(empty)
            return
        for work in works:
            card = WorkCard(work, self.repo.get_tags(work.id), self.repo.get_release_state(work.id))
            self._bind_work_card(card)
            layout.addWidget(card)

    def show_home(self):
        scroll, layout = self._make_scroll()
        layout.addWidget(PageHeader("Visão geral", "Leitura atual, lançamentos e o que merece sua atenção hoje.", "Painel principal"))
        summary = self.statistics_service.summary()
        metrics = QHBoxLayout()
        for label, value, ic in [
            ("Obras no acervo", summary["total_works"], "library"),
            ("Lendo agora", summary["reading"], "book-open"),
            ("Concluídas", summary["completed"], "check"),
            ("Favoritas", summary["favorites"], "star"),
        ]:
            metrics.addWidget(MetricCard(label, value, ic))
        layout.addLayout(metrics)

        digest = self.repo.list_release_digest()
        heading = QLabel("Lançamentos")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        release_grid = QGridLayout()
        release_grid.setHorizontalSpacing(10)
        columns = [("yesterday", "Ontem"), ("today", "Hoje"), ("tomorrow", "Amanhã")]
        for col, (key, title) in enumerate(columns):
            box = QFrame()
            box.setObjectName("panel")
            box_l = QVBoxLayout(box)
            box_l.setContentsMargins(13, 13, 13, 13)
            cap = QLabel(title)
            cap.setObjectName("fieldLabel")
            box_l.addWidget(cap)
            items = digest[key]
            if items:
                for item in items[:5]:
                    mini = ReleaseMiniCard(item["work_id"], item["title"], f"Capítulo previsto • {iso_to_br(item['date'])}", "pending" if key == "today" else "muted")
                    mini.opened.connect(self.open_details)
                    box_l.addWidget(mini)
            else:
                none = QLabel("Nenhum lançamento")
                none.setObjectName("dim")
                box_l.addWidget(none)
            box_l.addStretch()
            release_grid.addWidget(box, 0, col)
        release_grid.setColumnStretch(0, 1); release_grid.setColumnStretch(1, 1); release_grid.setColumnStretch(2, 1)
        layout.addLayout(release_grid)

        if digest["pending"]:
            pending_title = QLabel("Capítulos ainda não lidos")
            pending_title.setObjectName("sectionTitle")
            layout.addWidget(pending_title)
            for item in digest["pending"][:8]:
                label = f"{item['count']} pendente(s) • desde {iso_to_br(item['since'])}"
                mini = ReleaseMiniCard(item["work_id"], item["title"], label, "pending")
                mini.opened.connect(self.open_details)
                layout.addWidget(mini)

        reading = self.repo.list_filtered(status="Lendo")
        if reading:
            title = QLabel("Continue lendo")
            title.setObjectName("sectionTitle")
            layout.addWidget(title)
            self._add_work_cards(layout, reading[:4])
        layout.addStretch()
        self._set_page(scroll, "home")

    def show_library(self):
        scroll, layout = self._make_scroll()
        layout.addWidget(PageHeader("Biblioteca", "Busque e filtre seu acervo sem perder o contexto da leitura.", "Acervo"))
        filter_panel = QFrame()
        filter_panel.setObjectName("panel")
        fg = QGridLayout(filter_panel)
        fg.setContentsMargins(14, 14, 14, 14)
        fg.setHorizontalSpacing(8)
        self.lib_search = QLineEdit(self.library_filters["search"])
        self.lib_search.setPlaceholderText("Buscar no acervo...")
        fg.addWidget(self.lib_search, 0, 0, 1, 2)
        self.lib_category = QComboBox(); self.lib_category.addItems(["Todas"] + [x["name"] for x in self.repo.list_categories()])
        self.lib_category.setCurrentText(self.library_filters["category"] if self.library_filters["category"] in [self.lib_category.itemText(i) for i in range(self.lib_category.count())] else "Todas")
        fg.addWidget(self.lib_category, 0, 2)
        self.lib_status = QComboBox(); self.lib_status.addItems(["Todos"] + list(self.repo.STATUS_OPTIONS)); self.lib_status.setCurrentText(self.library_filters["status"])
        fg.addWidget(self.lib_status, 0, 3)
        self.lib_publication = QComboBox(); self.lib_publication.addItems(["Todos"] + list(self.repo.PUBLICATION_STATUS_OPTIONS)); self.lib_publication.setCurrentText(self.library_filters["publication"])
        fg.addWidget(self.lib_publication, 1, 0)
        self.lib_tag = QComboBox(); self.lib_tag.addItems(["Todas"] + self.repo.list_tags()); self.lib_tag.setCurrentText(self.library_filters["tag"] if self.library_filters["tag"] in [self.lib_tag.itemText(i) for i in range(self.lib_tag.count())] else "Todas")
        fg.addWidget(self.lib_tag, 1, 1)
        clear = QPushButton("Limpar filtros"); clear.clicked.connect(self._clear_library_filters); fg.addWidget(clear, 1, 3)
        layout.addWidget(filter_panel)
        self.library_results = QVBoxLayout()
        layout.addLayout(self.library_results)
        layout.addStretch()
        for widget in (self.lib_search, self.lib_category, self.lib_status, self.lib_publication, self.lib_tag):
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._render_library_results)
            else:
                widget.currentTextChanged.connect(self._render_library_results)
        self._render_library_results()
        self._set_page(scroll, "library")

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _render_library_results(self, *_):
        if not hasattr(self, "library_results"):
            return
        self._clear_layout(self.library_results)
        self.library_filters = {
            "search": self.lib_search.text(), "category": self.lib_category.currentText(),
            "status": self.lib_status.currentText(), "publication": self.lib_publication.currentText(),
            "tag": self.lib_tag.currentText(),
        }
        works = self.repo.list_filtered(
            search=self.library_filters["search"], category=self.library_filters["category"],
            status=self.library_filters["status"], publication_status=self.library_filters["publication"],
            tag=self.library_filters["tag"],
        )
        count = QLabel(f"{len(works)} obra(s)")
        count.setObjectName("dim")
        self.library_results.addWidget(count)
        self._add_work_cards(self.library_results, works)

    def _clear_library_filters(self):
        self.lib_search.clear(); self.lib_category.setCurrentText("Todas"); self.lib_status.setCurrentText("Todos"); self.lib_publication.setCurrentText("Todos"); self.lib_tag.setCurrentText("Todas")

    def show_reading_now(self):
        scroll, layout = self._make_scroll()
        layout.addWidget(PageHeader("Lendo agora", "Obras com seu status de leitura marcado como Lendo.", "Fila ativa"))
        self._add_work_cards(layout, self.repo.list_filtered(status="Lendo"))
        layout.addStretch()
        self._set_page(scroll, "reading")

    def show_favorites(self):
        scroll, layout = self._make_scroll()
        layout.addWidget(PageHeader("Favoritos", "Sua seleção pessoal, independente da avaliação.", "Curadoria"))
        self._add_work_cards(layout, self.repo.list_filtered(favorites_only=True))
        layout.addStretch()
        self._set_page(scroll, "favorites")

    def show_categories(self):
        scroll, layout = self._make_scroll()
        layout.addWidget(PageHeader("Categorias", "Crie e renomeie categorias definindo se o progresso será por páginas ou capítulos.", "Organização"))
        add_panel = QFrame(); add_panel.setObjectName("panel")
        al = QGridLayout(add_panel); al.setContentsMargins(14, 14, 14, 14); al.setHorizontalSpacing(10)
        new_name = QLineEdit(); new_name.setPlaceholderText("Nova categoria")
        al.addWidget(new_name, 0, 0)
        new_unit = QComboBox(); new_unit.addItems(["Página", "Capítulo"])
        al.addWidget(new_unit, 0, 1)
        add = QPushButton("Adicionar"); add.setObjectName("primary"); add.setIcon(icon("plus", color="#17130A"))
        def add_category():
            try: self.repo.create_category(new_name.text(), new_unit.currentText())
            except Exception as exc: QMessageBox.critical(self, "Categoria", str(exc)); return
            self._data_changed(); self.show_categories()
        add.clicked.connect(add_category); al.addWidget(add, 0, 2)
        layout.addWidget(add_panel)
        for item in self.repo.list_categories():
            row = QFrame(); row.setObjectName("panel")
            rl = QGridLayout(row); rl.setContentsMargins(14, 10, 14, 10); rl.setHorizontalSpacing(10)
            entry = QLineEdit(item["name"]); rl.addWidget(entry, 0, 0)
            unit = QComboBox(); unit.addItems(["Página", "Capítulo"]); unit.setCurrentText(item.get("progress_unit") or "Página"); rl.addWidget(unit, 0, 1)
            count = QLabel(f"{item['work_count']} obra(s)"); count.setObjectName("dim"); rl.addWidget(count, 0, 2)
            save = QPushButton("Salvar"); save.setIcon(icon("check", color="#F4EFEA"))
            def rename(_=False, old=item["name"], e=entry, u=unit):
                try: self.repo.rename_category(old, e.text(), u.currentText())
                except Exception as exc: QMessageBox.critical(self, "Categoria", str(exc)); return
                self._data_changed(); self.show_categories()
            save.clicked.connect(rename); rl.addWidget(save, 0, 3)
            delete = QPushButton(); delete.setIcon(icon("trash", color="#FF9A9A")); delete.setObjectName("dangerButton"); delete.setFixedWidth(42)
            def delete_cat(_=False, name=item["name"]):
                try: self.repo.delete_category(name)
                except Exception as exc: QMessageBox.critical(self, "Categoria", str(exc)); return
                self._data_changed(); self.show_categories()
            delete.clicked.connect(delete_cat); rl.addWidget(delete, 0, 4)
            layout.addWidget(row)
        layout.addStretch()
        self._set_page(scroll, "categories")

    def show_calendar(self):
        scroll, layout = self._make_scroll()
        layout.addWidget(PageHeader("Calendário", "Lançamentos previstos e marcos da sua leitura.", "Agenda"))
        digest = self.repo.list_release_digest()
        summary = QHBoxLayout()
        for key, title in (("yesterday", "Ontem"), ("today", "Hoje"), ("tomorrow", "Amanhã")):
            box = QFrame(); box.setObjectName("panel"); bl = QVBoxLayout(box); bl.setContentsMargins(13,13,13,13)
            cap = QLabel(title); cap.setObjectName("fieldLabel"); bl.addWidget(cap)
            for item in digest[key] or []:
                mini = ReleaseMiniCard(item["work_id"], item["title"], iso_to_br(item["date"]), "pending" if key == "today" else "muted")
                mini.opened.connect(self.open_details); bl.addWidget(mini)
            if not digest[key]:
                none = QLabel("Nenhum lançamento"); none.setObjectName("dim"); bl.addWidget(none)
            bl.addStretch(); summary.addWidget(box)
        layout.addLayout(summary)
        title = QLabel("Próximos eventos"); title.setObjectName("sectionTitle"); layout.addWidget(title)
        for event in self.repo.list_calendar_events(horizon_days=60):
            row = QPushButton(f"{iso_to_br(event['date'])}   •   {event['type']}   •   {event['title']}")
            row.setStyleSheet("text-align:left;")
            row.clicked.connect(lambda _=False, wid=event["work_id"]: self.open_details(wid))
            layout.addWidget(row)
        layout.addStretch()
        self._set_page(scroll, "calendar")

    def show_statistics(self):
        scroll, layout = self._make_scroll()
        layout.addWidget(PageHeader("Estatísticas", "Uma leitura rápida do seu acervo e ritmo atual.", "Análise"))
        summary = self.statistics_service.summary()
        grid = QGridLayout(); grid.setSpacing(10)
        values = [
            ("Obras cadastradas", summary["total_works"], "library"), ("Lendo agora", summary["reading"], "book-open"),
            ("Concluídas", summary["completed"], "check"), ("Favoritas", summary["favorites"], "star"),
            ("Páginas lidas", summary["pages_read"], "library"), ("Capítulos lidos", summary["chapters_read"], "book-open"),
            ("Avaliação média", str(summary["average_rating"]).replace(".", ","), "star"),
            ("Progresso médio", f"{summary['average_progress']}%".replace(".", ","), "chart"),
        ]
        for i, data in enumerate(values): grid.addWidget(MetricCard(*data), i//4, i%4)
        layout.addLayout(grid)
        box = QFrame(); box.setObjectName("panel"); bl = QVBoxLayout(box); bl.setContentsMargins(18,16,18,16)
        cap = QLabel("Categoria em destaque"); cap.setObjectName("fieldLabel"); bl.addWidget(cap)
        val = QLabel(summary["top_category"]); val.setObjectName("sectionTitle"); bl.addWidget(val)
        layout.addWidget(box); layout.addStretch()
        self._set_page(scroll, "statistics")

    def show_history(self):
        scroll, layout = self._make_scroll()
        layout.addWidget(PageHeader("Histórico", "Alterações de progresso e status registradas pelo sistema.", "Registro"))
        rows = self.repo.list_history(500)
        table = QTableWidget(len(rows), 3)
        table.setHorizontalHeaderLabels(["Data", "Obra", "Evento"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for r, item in enumerate(rows):
            raw = str(item.get("created_at", ""))
            display = raw[:10]
            try: display = iso_to_br(display) + (" " + raw[11:16] if len(raw) >= 16 else "")
            except Exception: pass
            table.setItem(r, 0, QTableWidgetItem(display))
            table.setItem(r, 1, QTableWidgetItem(item.get("name", "")))
            table.setItem(r, 2, QTableWidgetItem(item.get("description", "")))
        table.setMinimumHeight(450)
        layout.addWidget(table); layout.addStretch()
        self._set_page(scroll, "history")

    def show_goals(self):
        scroll, layout = self._make_scroll()
        layout.addWidget(PageHeader("Metas e desafios", "Metas calculadas automaticamente a partir do seu histórico.", "Planejamento"))
        form = QFrame(); form.setObjectName("panel"); fg = QGridLayout(form); fg.setContentsMargins(14,14,14,14); fg.setHorizontalSpacing(10)
        title = QLineEdit(); title.setPlaceholderText("Ex.: Ler 12 obras no ano"); fg.addWidget(title, 0, 0, 1, 2)
        target = NumericStepper(minimum=1, maximum=10_000_000, value=1); fg.addWidget(target, 0, 2)
        kind = QComboBox(); kind.addItems(list(self.GOAL_TYPES_BY_LABEL)); fg.addWidget(kind, 0, 3)
        start = DateField(); end = DateField(); fg.addWidget(start, 1, 0, 1, 2); fg.addWidget(end, 1, 2, 1, 2)
        add = QPushButton("Adicionar meta"); add.setObjectName("primary"); add.setIcon(icon("plus", color="#17130A"))
        def add_goal():
            try: self.repo.create_goal(title.text(), self.GOAL_TYPES_BY_LABEL[kind.currentText()], target.value(), start.iso_value(), end.iso_value())
            except Exception as exc: QMessageBox.critical(self, "Meta", str(exc)); return
            self._data_changed(); self.show_goals()
        add.clicked.connect(add_goal); fg.addWidget(add, 2, 3)
        layout.addWidget(form)
        for goal in self.repo.list_goals():
            card = QFrame(); card.setObjectName("panel"); cl = QGridLayout(card); cl.setContentsMargins(14,12,14,12); cl.setHorizontalSpacing(10)
            name = QLineEdit(goal["title"]); cl.addWidget(name, 0, 0, 1, 2)
            tgt = NumericStepper(minimum=1, maximum=10_000_000, value=int(goal["target_value"])); cl.addWidget(tgt, 0, 2)
            typ = QComboBox(); typ.addItems(list(self.GOAL_TYPES_BY_LABEL)); typ.setCurrentText(self.GOAL_LABELS.get(goal["goal_type"], "Obras concluídas")); cl.addWidget(typ, 0, 3)
            current = int(goal["current_value"] or 0); target_v = max(1, int(goal["target_value"] or 1))
            bar = QProgressBar(); bar.setRange(0,1000); bar.setValue(min(int(current/target_v*1000),1000)); cl.addWidget(bar,1,0,1,3)
            stat = QLabel(f"{current} / {target_v}"); stat.setObjectName("pending"); cl.addWidget(stat,1,3)
            save = QPushButton("Salvar"); save.setIcon(icon("check", color="#F4EFEA"))
            def save_goal(_=False, g=goal, n=name, t=tgt, ty=typ):
                try: self.repo.update_goal(g["id"], title=n.text(), goal_type=self.GOAL_TYPES_BY_LABEL[ty.currentText()], target_value=t.value(), start_date=g.get("start_date"), end_date=g.get("end_date"))
                except Exception as exc: QMessageBox.critical(self, "Meta", str(exc)); return
                self._data_changed(); self.show_goals()
            save.clicked.connect(save_goal); cl.addWidget(save,2,2)
            delete = QPushButton("Excluir"); delete.setObjectName("dangerButton"); delete.setIcon(icon("trash", color="#FF9A9A"))
            delete.clicked.connect(lambda _=False, gid=goal["id"]: self._delete_goal(gid)); cl.addWidget(delete,2,3)
            layout.addWidget(card)
        layout.addStretch(); self._set_page(scroll, "goals")

    def _delete_goal(self, goal_id):
        self.repo.delete_goal(goal_id); self._data_changed(); self.show_goals()

    def show_backup(self):
        scroll, layout = self._make_scroll()
        layout.addWidget(PageHeader("Backup", "Exporte uma cópia completa com capas ou restaure uma biblioteca.", "Segurança"))
        panel = QFrame(); panel.setObjectName("panel"); pl = QVBoxLayout(panel); pl.setContentsMargins(18,16,18,16)
        export = QPushButton("Exportar backup completo (.zip)"); export.setObjectName("primary"); export.setIcon(icon("backup", color="#17130A")); export.clicked.connect(self._export_backup); pl.addWidget(export)
        import_btn = QPushButton("Restaurar backup completo"); import_btn.setIcon(icon("folder", color="#F4F2ED")); import_btn.clicked.connect(self._import_backup); pl.addWidget(import_btn)
        json_export = QPushButton("Exportar metadados (.json)"); json_export.clicked.connect(self._export_json); pl.addWidget(json_export)
        json_import = QPushButton("Importar metadados (.json)"); json_import.clicked.connect(self._import_json); pl.addWidget(json_import)
        layout.addWidget(panel); layout.addStretch(); self._set_page(scroll, "backup")

    def show_settings(self):
        scroll, layout = self._make_scroll()
        layout.addWidget(PageHeader("Configurações", "Comportamento local, sincronização Google e manutenção.", "Preferências"))
        settings = self.settings_service.load(); google = settings["google"]
        panel = QFrame(); panel.setObjectName("panel"); fg = QGridLayout(panel); fg.setContentsMargins(18,16,18,18); fg.setHorizontalSpacing(10); fg.setVerticalSpacing(8); fg.setColumnStretch(1,1)
        sync = QCheckBox("Ativar sincronização Google"); sync.setChecked(settings["sync_enabled"]); fg.addWidget(sync,0,0,1,3)
        fg.addWidget(QLabel("Pausar automaticamente após (dias sem progresso)"),1,0)
        pause_days = NumericStepper(minimum=0, maximum=3650, value=settings.get("auto_pause_days",30), special_value_text="Desativado"); fg.addWidget(pause_days,1,1)
        cred = QLineEdit(google.get("credentials_file","")); fg.addWidget(QLabel("Credenciais Google"),2,0); fg.addWidget(cred,2,1)
        browse = QPushButton("Selecionar"); browse.clicked.connect(lambda: self._browse_credentials(cred)); fg.addWidget(browse,2,2)
        sheet = QLineEdit(google.get("spreadsheet_name","The Reader Codex")); fg.addWidget(QLabel("Nome da planilha"),3,0); fg.addWidget(sheet,3,1,1,2)
        sheet_id = QLineEdit(google.get("spreadsheet_id","")); fg.addWidget(QLabel("ID da planilha"),4,0); fg.addWidget(sheet_id,4,1,1,2)
        folder = QLineEdit(google.get("drive_folder_id","")); fg.addWidget(QLabel("ID da pasta do Drive"),5,0); fg.addWidget(folder,5,1,1,2)
        buttons = QHBoxLayout(); save = QPushButton("Salvar configurações"); save.setObjectName("primary"); test = QPushButton("Testar conexão"); sync_now = QPushButton("Sincronizar agora")
        buttons.addStretch(); buttons.addWidget(test); buttons.addWidget(sync_now); buttons.addWidget(save); fg.addLayout(buttons,6,0,1,3)
        def save_settings(notify=True):
            payload={"sync_enabled":sync.isChecked(),"profile_name":settings.get("profile_name",""),"auto_pause_days":pause_days.value(),"google":{"credentials_file":cred.text().strip(),"spreadsheet_name":sheet.text().strip() or "The Reader Codex","spreadsheet_id":sheet_id.text().strip(),"drive_folder_id":folder.text().strip()}}
            self.settings_service.save(payload); self._update_sync_status(); self._apply_inactivity_rule()
            if notify: QMessageBox.information(self,"Configurações","Configurações salvas.")
        save.clicked.connect(lambda: save_settings(True))
        test.clicked.connect(lambda: (save_settings(False), self.test_google_connection()))
        sync_now.clicked.connect(lambda: (save_settings(False), self.sync_in_background(True)))
        layout.addWidget(panel)
        data = QFrame(); data.setObjectName("panel"); dl=QHBoxLayout(data); dl.setContentsMargins(14,12,14,12); path=QLabel(f"Dados locais: {DATA_DIR}"); path.setObjectName("muted"); path.setWordWrap(True); dl.addWidget(path,1); open_btn=QPushButton("Abrir pasta"); open_btn.setIcon(icon("folder", color="#F4F2ED")); open_btn.clicked.connect(self.open_data_folder); dl.addWidget(open_btn); layout.addWidget(data)
        pending=QLabel(f"Alterações locais aguardando sincronização: {self.repo.pending_sync_count()}"); pending.setObjectName("dim"); layout.addWidget(pending)
        layout.addStretch(); self._set_page(scroll, "settings")

    def open_new_work(self):
        self.previous_view = self.current_view if self.current_view not in ("work_form", "work_details") else "library"
        page = WorkFormPage(self.repo)
        page.saved.connect(self._work_saved)
        page.cancelled.connect(self._return_previous)
        self._set_page(page, "work_form")

    def open_details(self, work_id):
        if not self.repo.get_by_id(work_id): return
        self.previous_view = self.current_view if self.current_view not in ("work_form", "work_details") else self.previous_view
        self.current_work_id = work_id
        page = WorkDetailsPage(self.repo, work_id)
        page.backRequested.connect(self._return_previous)
        page.editRequested.connect(self.open_edit_work)
        page.dataChanged.connect(self._data_changed)
        self._set_page(page, "work_details")

    def open_edit_work(self, work_id):
        work = self.repo.get_by_id(work_id)
        if not work: return
        page = WorkFormPage(self.repo, work)
        page.saved.connect(lambda wid: self._work_saved(wid, open_details=True))
        page.cancelled.connect(lambda: self.open_details(work_id))
        page.deleted.connect(lambda: (self._data_changed(), self.show_library()))
        self._set_page(page, "work_form")

    def _work_saved(self, work_id, open_details=False):
        self._data_changed()
        if open_details: self.open_details(work_id)
        else: self.show_library()

    def _return_previous(self):
        self.navigate(self.previous_view if self.previous_view in {x[0] for x in self.NAV} | {"settings","backup"} else "library")

    def _toggle_favorite(self, work_id, favorite):
        try: self.repo.set_favorite(work_id, favorite)
        except Exception as exc: QMessageBox.critical(self,"Favorito",str(exc)); return
        self._data_changed(); self._refresh_current()

    def _change_progress(self, work_id, amount):
        try: self.repo.increment_progress(work_id, amount)
        except Exception as exc: QMessageBox.critical(self,"Progresso",str(exc)); return
        self._data_changed(); self._refresh_current()

    def _open_reading_link(self, work_id):
        work=self.repo.get_by_id(work_id)
        if work and work.reading_url: QDesktopServices.openUrl(QUrl(work.reading_url))

    def _refresh_current(self):
        view=self.current_view
        if view=="work_details" and self.current_work_id: self.open_details(self.current_work_id)
        elif view=="work_form": return
        else: self.navigate(view)

    def _global_search(self):
        self.library_filters["search"] = self.global_search.text().strip(); self.show_library()

    def _data_changed(self):
        self._update_sync_status()
        if self.sync_engine.status().get("status") == "ready":
            QTimer.singleShot(2500, lambda: self.sync_in_background(False))

    def _apply_inactivity_rule(self):
        days=self.settings_service.load().get("auto_pause_days",30)
        changed=self.repo.apply_inactivity_rules(days)
        if changed and hasattr(self,"stack"): self._update_sync_status()

    def _startup_backup(self):
        try: self.backup_service.create_automatic_backup()
        except Exception: pass

    def _export_backup(self):
        path,_=QFileDialog.getSaveFileName(self,"Exportar backup","TheReaderCodex-backup.zip","ZIP (*.zip)")
        if path:
            try: self.backup_service.export_full_backup(path); QMessageBox.information(self,"Backup","Backup completo exportado.")
            except Exception as exc: QMessageBox.critical(self,"Backup",str(exc))

    def _import_backup(self):
        path,_=QFileDialog.getOpenFileName(self,"Restaurar backup","","ZIP (*.zip)")
        if not path:return
        if QMessageBox.question(self,"Restaurar backup","A biblioteca atual será substituída. Continuar?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try: self.backup_service.create_automatic_backup(); self.backup_service.import_full_backup(path); self._data_changed(); self.show_library(); QMessageBox.information(self,"Backup","Backup restaurado.")
        except Exception as exc: QMessageBox.critical(self,"Backup",str(exc))

    def _export_json(self):
        path,_=QFileDialog.getSaveFileName(self,"Exportar JSON","TheReaderCodex.json","JSON (*.json)")
        if path:
            try:self.backup_service.export_json(path); QMessageBox.information(self,"Backup","JSON exportado.")
            except Exception as exc:QMessageBox.critical(self,"Backup",str(exc))

    def _import_json(self):
        path,_=QFileDialog.getOpenFileName(self,"Importar JSON","","JSON (*.json)")
        if not path:return
        if QMessageBox.question(self,"Importar JSON","A biblioteca atual será substituída. Continuar?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:self.backup_service.create_automatic_backup(); self.backup_service.import_json(path); self._data_changed(); self.show_library(); QMessageBox.information(self,"Backup","JSON importado.")
        except Exception as exc:QMessageBox.critical(self,"Backup",str(exc))

    def _browse_credentials(self, entry):
        path,_=QFileDialog.getOpenFileName(self,"Credenciais Google","","JSON (*.json)")
        if path: entry.setText(path)

    def open_data_folder(self):
        DATA_DIR.mkdir(parents=True,exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA_DIR)))

    def _update_sync_status(self):
        status=self.sync_engine.status(); pending=status.get("pending",0)
        if status.get("status")=="ready": self.sync_label.setText(f"Google configurado\n{pending} alteração(ões) pendente(s)")
        else: self.sync_label.setText(f"Nuvem não configurada\n{pending} alteração(ões) local(is)")

    def sync_in_background(self, show_dialog=False):
        if self._sync_running:return
        if self.sync_engine.status().get("status")!="ready":
            self._update_sync_status()
            if show_dialog: QMessageBox.information(self,"Sincronização","Configure o Google em Configurações.")
            return
        self._sync_running=True; self.sync_button.setEnabled(False); self.sync_label.setText("Sincronizando...")
        def worker(): self.syncFinished.emit(self.sync_engine.sync(), show_dialog)
        threading.Thread(target=worker,daemon=True).start()

    def _apply_sync_result(self, result, show_dialog):
        self._sync_running=False; self.sync_button.setEnabled(True); self._update_sync_status()
        if result.get("status")=="synced":
            if result.get("downloaded"): self._refresh_current()
            if show_dialog: QMessageBox.information(self,"Sincronização",f"Concluída.\nEnviadas: {result.get('uploaded',0)}\nRecebidas: {result.get('downloaded',0)}")
        elif show_dialog: QMessageBox.critical(self,"Sincronização",result.get("message","Falha na sincronização."))

    def test_google_connection(self):
        def worker():
            try:self.connectionFinished.emit({"ok":True,"info":self.sync_engine.test_connection()})
            except Exception as exc:self.connectionFinished.emit({"ok":False,"message":str(exc)})
        threading.Thread(target=worker,daemon=True).start()

    def _apply_connection_result(self, result):
        self._update_sync_status()
        if result.get("ok"): QMessageBox.information(self,"Google",f"Conexão realizada. Planilha: {result['info'].get('spreadsheet_name','The Reader Codex')}")
        else: QMessageBox.critical(self,"Google",result.get("message","Falha na conexão."))
